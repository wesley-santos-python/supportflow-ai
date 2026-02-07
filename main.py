"""
SupportFlow AI - Ponto de entrada da aplicação.

Sistema inteligente de gestão de tickets de suporte com IA generativa.
"""
import flet as ft
from src.ui.dashboard import main_dashboard
from src.data.db import init_db


def main() -> None:
    """Inicializa o banco de dados e executa o dashboard."""
    init_db()
    # view=ft.AppView.FLET_APP → Janela desktop (padrão) 
    # view=ft.AppView.WEB_BROWSER abre no navegador
    ft.app(main_dashboard, view=ft.AppView.FLET_APP)


if __name__ == "__main__":
    main()