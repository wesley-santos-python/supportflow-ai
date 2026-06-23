"""
Serviço de integração com Google Gemini AI.

Responsável por:
    - Analisar tickets de suporte (urgência, categoria, resumo, resposta)
    - Reescrever/ajustar respostas conforme instruções do operador
    - Gerar um resumo consolidado de e-mails urgentes (ex.: para WhatsApp)

O modelo é configurável (padrão: ``gemini-3.1-flash-lite``).
"""
import json
from typing import Dict, List

try:  # SDK do Gemini (opcional em ambiente de testes/CI sem o pacote)
    from google import genai
except ImportError:  # pragma: no cover - resolvido por mock nos testes
    genai = None

from src import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AIService:
    """
    Serviço de IA para análise de tickets usando Google Gemini.

    A chave de API e o modelo são resolvidos via :mod:`src.config`, de modo
    que podem ser configurados pela interface web ou por variável de ambiente.

    Attributes:
        client: Cliente da API Google GenAI.
        model: Identificador do modelo Gemini em uso.
    """

    def __init__(self) -> None:
        """Inicializa o cliente com a API key resolvida pela configuração."""
        api_key = config.get("AI_API_KEY")
        if not api_key:
            logger.warning("AI_API_KEY não configurada")
        self.model = config.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
        if genai is None:
            logger.error("Pacote 'google-genai' não instalado")
            self.client = None
        else:
            self.client = genai.Client(api_key=api_key)
        logger.debug(f"AIService inicializado (modelo={self.model})")

    def analyze_ticket(self, email_body: str) -> Dict[str, str]:
        """
        Analisa o corpo de um e-mail e retorna a classificação estruturada.

        Args:
            email_body: Texto do corpo do e-mail a ser analisado.

        Returns:
            Dicionário com ``urgencia``, ``categoria``, ``resumo`` e
            ``resposta_sugerida``. Em caso de falha, retorna um fallback seguro.
        """
        prompt = (
            "Você é um assistente de suporte ao cliente. Analise este e-mail e "
            "retorne APENAS um JSON válido com as chaves: 'urgencia' "
            "(Alta/Média/Baixa), 'categoria' (Técnico/Financeiro/Logística/"
            "Outros), 'resumo' (uma frase objetiva) e 'resposta_sugerida'. "
            "A 'resposta_sugerida' deve ser em português, pronta para enviar ao "
            "cliente: amigável, profissional e objetiva — reconhece o problema, "
            "dá um próximo passo claro e encerra de forma cordial. Não use "
            "placeholders entre colchetes nem deixe campos a preencher. "
            f"E-mail: {email_body}"
        )

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
            )
            result = json.loads(self._clean_json(response.text))
            logger.debug(f"Análise concluída: urgência={result.get('urgencia')}")
            return result
        except json.JSONDecodeError as e:
            logger.warning(f"JSON inválido da IA, usando fallback: {e}")
            return self._default_response()
        except Exception as e:
            logger.warning(f"Erro na análise IA, usando fallback: {e}")
            return self._default_response()

    def rewrite_response(self, original: str, instruction: str) -> str:
        """
        Reescreve uma resposta seguindo uma instrução do operador.

        Args:
            original: Texto base (ex.: resposta sugerida atual).
            instruction: Como ajustar (ex.: "mais formal", "peça desculpas").

        Returns:
            Novo texto da resposta. Em caso de falha, retorna o original.
        """
        prompt = (
            "Reescreva a resposta de suporte ao cliente abaixo seguindo a "
            f"instrução: '{instruction}'. Mantenha tom profissional e cordial. "
            "Retorne APENAS o texto final, sem comentários.\n\n"
            f"Resposta original:\n{original}"
        )
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
            )
            text = (response.text or "").strip()
            return text or original
        except Exception as e:
            logger.warning(f"Falha ao reescrever resposta: {e}")
            return original

    def summarize_urgent(self, tickets: List[Dict[str, str]]) -> str:
        """
        Gera um resumo consolidado de tickets urgentes.

        Pensado para o envio futuro ao WhatsApp do responsável.

        Args:
            tickets: Lista de dicionários com ``sender``, ``subject``, ``resumo``.

        Returns:
            Texto curto em português, pronto para mensageria.
        """
        if not tickets:
            return "Nenhum e-mail urgente no momento. ✅"

        linhas = "\n".join(
            f"- {t.get('sender', '?')}: {t.get('subject', '(sem assunto)')}"
            for t in tickets
        )
        prompt = (
            "Resuma em até 5 linhas, em português, de forma objetiva e amigável, "
            "os seguintes e-mails urgentes de suporte para enviar ao responsável "
            f"via WhatsApp:\n{linhas}"
        )
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
            )
            text = (response.text or "").strip()
            return text or self._fallback_urgent_summary(tickets)
        except Exception as e:
            logger.warning(f"Falha ao resumir urgentes: {e}")
            return self._fallback_urgent_summary(tickets)

    @staticmethod
    def _clean_json(raw: str) -> str:
        """Remove cercas de markdown (```json) do texto retornado pela IA."""
        return raw.strip().replace("```json", "").replace("```", "").strip()

    @staticmethod
    def _fallback_urgent_summary(tickets: List[Dict[str, str]]) -> str:
        """Resumo simples (sem IA) usado como fallback."""
        header = f"🚨 {len(tickets)} e-mail(s) urgente(s):"
        body = "\n".join(
            f"• {t.get('subject', '(sem assunto)')} — {t.get('sender', '?')}"
            for t in tickets
        )
        return f"{header}\n{body}"

    @staticmethod
    def _default_response() -> Dict[str, str]:
        """Retorna resposta padrão em caso de falha de análise."""
        return {
            "urgencia": "Média",
            "categoria": "Outros",
            "resumo": "Análise pendente",
            "resposta_sugerida": "Olá, recebemos sua mensagem e em breve responderemos.",
        }
