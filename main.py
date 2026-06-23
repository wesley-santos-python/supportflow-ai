"""
SupportFlow AI — Ponto de entrada da aplicação web (SaaS).

Sistema inteligente de gestão de tickets de suporte com IA generativa.
Sobe o servidor web (FastAPI/Uvicorn). A interface fica disponível no
navegador em http://127.0.0.1:8000

Uso:
    python main.py
    # ou, para produção/reload:
    uvicorn src.web.app:app --host 0.0.0.0 --port 8000
"""
import os

import uvicorn


def main() -> None:
    """Inicia o servidor web do SupportFlow AI."""
    # 0.0.0.0 é necessário em ambientes de container (Railway/Docker), que
    # injetam a porta via variável PORT.
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("src.web.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
