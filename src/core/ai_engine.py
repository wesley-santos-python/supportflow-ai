"""
Serviço de integração com Google Gemini AI.

Responsável por analisar tickets de suporte e classificar urgência,
categoria e gerar respostas sugeridas.
"""
import os
import json
from typing import Dict

from google import genai
from dotenv import load_dotenv

from src.utils.logger import get_logger
from src.exceptions import AIAnalysisError

load_dotenv()
logger = get_logger(__name__)


class AIService:
    """
    Serviço de IA para análise de tickets usando Google Gemini.
    
    Attributes:
        client: Cliente da API Google GenAI.
    """
    
    def __init__(self) -> None:
        """Inicializa o cliente com a API key do ambiente."""
        api_key = os.getenv("AI_API_KEY")
        if not api_key:
            logger.warning("AI_API_KEY não configurada no ambiente")
        self.client = genai.Client(api_key=api_key)
        logger.debug("AIService inicializado")

    def analyze_ticket(self, email_body: str) -> Dict[str, str]:
        """
        Analisa o corpo de um e-mail e retorna classificação.
        
        Args:
            email_body: Texto do corpo do e-mail a ser analisado.
        
        Returns:
            Dicionário com urgencia, categoria, resumo e resposta_sugerida.
        
        Raises:
            AIAnalysisError: Se a análise falhar após fallback.
        """
        prompt = (
            "Analise este e-mail de suporte e retorne APENAS um JSON válido "
            "com as chaves: 'urgencia' (Alta/Média/Baixa), 'categoria' "
            "(Técnico/Financeiro/Logística/Outros), 'resumo' (uma frase), "
            f"'resposta_sugerida' (texto profissional). E-mail: {email_body}"
        )
        
        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash-lite", 
                contents=prompt
            )
            clean_json = response.text.strip().replace('```json', '').replace('```', '').strip()
            result = json.loads(clean_json)
            logger.debug(f"Análise concluída: urgência={result.get('urgencia')}")
            return result
        except json.JSONDecodeError as e:
            logger.warning(f"JSON inválido da IA, usando fallback: {e}")
            return self._default_response()
        except Exception as e:
            logger.warning(f"Erro na análise IA, usando fallback: {e}")
            return self._default_response()
    
    def _default_response(self) -> Dict[str, str]:
        """Retorna resposta padrão em caso de falha."""
        return {
            "urgencia": "Média", 
            "categoria": "Outros", 
            "resumo": "Análise pendente", 
            "resposta_sugerida": "Olá, recebemos sua mensagem e em breve responderemos."
        }