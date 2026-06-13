"""
Serviço de integração com Google Gemini AI.

Responsável por analisar tickets de suporte e classificar urgência,
categoria e gerar respostas sugeridas.
"""
import json
import time
from typing import Dict

from google import genai

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AIService:
    """Serviço de IA para análise de tickets usando Google Gemini."""

    def __init__(self) -> None:
        """Inicializa o cliente com a API key da configuração."""
        if not settings.ai_configured:
            logger.warning("AI_API_KEY não configurada no ambiente")
        self.client = genai.Client(api_key=settings.ai_api_key)
        self.model = settings.ai_model
        logger.debug(f"AIService inicializado (modelo={self.model})")

    def analyze_ticket(self, email_body: str) -> Dict[str, str]:
        """
        Analisa o corpo de um e-mail e retorna a classificação.

        Args:
            email_body: Texto do corpo do e-mail a ser analisado.

        Returns:
            Dicionário com urgencia, categoria, resumo e resposta_sugerida.
        """
        # Trunca o corpo para controlar custo/limite de tokens.
        body = (email_body or "")[: settings.ai_max_body_chars]
        prompt = (
            "Analise este e-mail de suporte e retorne APENAS um JSON válido "
            "com as chaves: 'urgencia' (Alta/Média/Baixa), 'categoria' "
            "(Técnico/Financeiro/Logística/Outros), 'resumo' (uma frase), "
            "'resposta_sugerida' (texto profissional). "
            f"E-mail (delimitado por <<<>>>): <<<{body}>>>"
        )

        last_error: Exception | None = None
        for attempt in range(1, settings.ai_max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model, contents=prompt
                )
                clean_json = (
                    response.text.strip()
                    .replace("```json", "")
                    .replace("```", "")
                    .strip()
                )
                result = json.loads(clean_json)
                logger.debug(f"Análise concluída: urgência={result.get('urgencia')}")
                return result
            except json.JSONDecodeError as e:
                logger.warning(f"JSON inválido da IA (tentativa {attempt}): {e}")
                last_error = e
                break  # Reenviar o mesmo prompt não corrige formato; cai no fallback.
            except Exception as e:
                last_error = e
                logger.warning(f"Erro na análise IA (tentativa {attempt}): {e}")
                if attempt < settings.ai_max_retries:
                    time.sleep(2 ** attempt)  # backoff: 2s, 4s, ...

        logger.warning(f"Usando fallback após falhas: {last_error}")
        return self._default_response()

    def _default_response(self) -> Dict[str, str]:
        """Retorna resposta padrão em caso de falha."""
        return {
            "urgencia": "Média",
            "categoria": "Outros",
            "resumo": "Análise pendente",
            "resposta_sugerida": "Olá, recebemos sua mensagem e em breve responderemos.",
        }
