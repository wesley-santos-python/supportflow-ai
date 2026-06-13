"""
SupportFlow AI - Ponto de entrada da aplicação web.

Sistema inteligente de gestão de tickets de suporte com IA generativa.
Inicia o servidor FastAPI (interface web HTMX + API JSON).
"""
import uvicorn

from src.config import settings


def main() -> None:
    """Sobe o servidor web (interface + API)."""
    uvicorn.run(
        "src.web.app:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
