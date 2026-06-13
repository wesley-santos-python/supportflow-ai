"""
Testes para o módulo ai_engine.
"""
import pytest
from unittest.mock import patch, MagicMock


class TestAIService:
    """Testes para a classe AIService."""
    
    def test_analyze_ticket_success(self):
        """Testa análise de ticket com resposta válida da IA."""
        # Importamos aqui para evitar carregar .env em ambiente de teste
        with patch.dict('os.environ', {'AI_API_KEY': 'test_key'}):
            with patch('src.core.ai_engine.genai') as mock_genai:
                # Configura o mock
                mock_client = MagicMock()
                mock_genai.Client.return_value = mock_client
                mock_client.models.generate_content.return_value.text = '''
                {"urgencia": "Alta", "categoria": "Técnico", "resumo": "Problema de conexão", "resposta_sugerida": "Olá, vamos resolver seu problema."}
                '''
                
                from src.core.ai_engine import AIService
                service = AIService()
                result = service.analyze_ticket("Não consigo conectar no sistema")
                
                assert result["urgencia"] == "Alta"
                assert result["categoria"] == "Técnico"
                assert "conexão" in result["resumo"]

    def test_analyze_ticket_with_json_markdown(self):
        """Testa limpeza de markdown do JSON retornado pela IA."""
        with patch.dict('os.environ', {'AI_API_KEY': 'test_key'}):
            with patch('src.core.ai_engine.genai') as mock_genai:
                mock_client = MagicMock()
                mock_genai.Client.return_value = mock_client
                # Simula resposta com markdown
                mock_client.models.generate_content.return_value.text = '''```json
                {"urgencia": "Baixa", "categoria": "Financeiro", "resumo": "Dúvida sobre fatura", "resposta_sugerida": "Sua fatura está disponível."}
                ```'''
                
                from src.core.ai_engine import AIService
                service = AIService()
                result = service.analyze_ticket("Qual o valor da minha fatura?")
                
                assert result["urgencia"] == "Baixa"
                assert result["categoria"] == "Financeiro"

    def test_analyze_ticket_fallback_on_error(self):
        """Testa fallback quando a IA falha."""
        with patch.dict('os.environ', {'AI_API_KEY': 'test_key'}):
            with patch('src.core.ai_engine.genai') as mock_genai, \
                 patch('src.core.ai_engine.time.sleep'):  # evita esperar o backoff
                mock_client = MagicMock()
                mock_genai.Client.return_value = mock_client
                # Simula erro da API
                mock_client.models.generate_content.side_effect = Exception("API Error")

                from src.core.ai_engine import AIService
                service = AIService()
                result = service.analyze_ticket("Qualquer texto")
                
                # Deve retornar valores default
                assert result["urgencia"] == "Média"
                assert result["categoria"] == "Outros"
                assert result["resumo"] == "Análise pendente"

    def test_analyze_ticket_invalid_json_fallback(self):
        """Testa fallback quando IA retorna JSON inválido."""
        with patch.dict('os.environ', {'AI_API_KEY': 'test_key'}):
            with patch('src.core.ai_engine.genai') as mock_genai:
                mock_client = MagicMock()
                mock_genai.Client.return_value = mock_client
                # Simula JSON inválido
                mock_client.models.generate_content.return_value.text = "resposta sem formato json"
                
                from src.core.ai_engine import AIService
                service = AIService()
                result = service.analyze_ticket("Teste")
                
                # Deve retornar valores default
                assert result["urgencia"] == "Média"
