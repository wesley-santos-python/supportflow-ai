"""
Componentes reutilizáveis da interface do SupportFlow AI.

Este módulo contém componentes Flet padronizados para uso no dashboard.
"""
import flet as ft
from typing import Callable, Any


def urgency_badge(urgency: str) -> ft.Container:
    """
    Cria um badge colorido de urgência.
    
    Args:
        urgency: Nível de urgência ("Alta", "Média" ou "Baixa")
    
    Returns:
        Container com o badge estilizado
    """
    colors = {
        "Alta": ft.Colors.RED_700,
        "Média": ft.Colors.ORANGE_700,
        "Baixa": ft.Colors.GREEN_700
    }
    
    return ft.Container(
        content=ft.Text(urgency or "Baixa", size=9, weight="bold"),
        bgcolor=colors.get(urgency, ft.Colors.GREEN_700),
        padding=ft.padding.symmetric(horizontal=10, vertical=2),
        border_radius=15
    )


def ticket_card(ticket: Any, on_click: Callable) -> ft.Container:
    """
    Cria um card de ticket estilizado.
    
    Args:
        ticket: Objeto Ticket com os dados do ticket
        on_click: Função callback chamada ao clicar no card
    
    Returns:
        Container com o card do ticket
    """
    # Captura ticket por valor para evitar problema de closure em loops
    def handle_click(e, t=ticket):
        on_click(t)
    
    return ft.Container(
        bgcolor="#1e1f22",
        padding=15,
        border_radius=12,
        on_click=handle_click,
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.EMAIL_OUTLINED, color=ft.Colors.BLUE_400, size=20),
                ft.Text(ticket.subject, weight="bold", size=15, expand=True),
                urgency_badge(ticket.urgencia)
            ]),
            ft.Text(
                f"De: {ticket.sender}", 
                size=11, 
                italic=True, 
                color=ft.Colors.GREY_500
            ),
            ft.Text(
                ticket.resumo or "Análise Pendente...", 
                size=13, 
                color=ft.Colors.GREY_300, 
                max_lines=2
            ),
            ft.Row([
                ft.Row([
                    ft.Icon(ft.Icons.FOLDER_OPEN_SHARP, size=14, color="#f3d17b"),
                    ft.Text(ticket.categoria or "Geral", size=11, color="#f3d17b"),
                ], spacing=5),
                ft.Text(
                    ticket.created_at.strftime("%d/%m %H:%M") if ticket.created_at else "", 
                    size=10, 
                    color=ft.Colors.GREY_600
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        ], spacing=8)
    )


def loading_indicator() -> ft.ProgressBar:
    """
    Cria um indicador de carregamento padrão.
    
    Returns:
        ProgressBar estilizada
    """
    return ft.ProgressBar(visible=False, color=ft.Colors.BLUE_ACCENT)


def detail_modal(ticket: Any, page: ft.Page) -> ft.AlertDialog:
    """
    Cria um modal de detalhes do ticket.
    
    Args:
        ticket: Objeto Ticket com os dados
        page: Página Flet para controle do modal
    
    Returns:
        AlertDialog com detalhes do ticket
    """
    def close_dlg(e):
        dlg.open = False
        page.update()
    
    dlg = ft.AlertDialog(
        title=ft.Text("Sugestão de Resposta da IA"),
        content=ft.Column([
            ft.Text("Resumo:", weight="bold", color=ft.Colors.BLUE_400),
            ft.Text(ticket.resumo or "Análise ainda não concluída"),
            ft.Divider(color=ft.Colors.GREY_800),
            ft.Text("Sugestão:", weight="bold", color=ft.Colors.GREEN_400),
            ft.TextField(
                value=ticket.resposta_sugerida or "Aguardando processamento...", 
                multiline=True, 
                min_lines=5
            ),
        ], tight=True, width=450),
        actions=[
            ft.TextButton("Copiar", on_click=lambda _: page.set_clipboard(ticket.resposta_sugerida)),
            ft.ElevatedButton("Enviar Email", bgcolor=ft.Colors.BLUE_700, color="white"),
            ft.TextButton("Fechar", on_click=close_dlg),
        ],
    )
    
    return dlg


def filter_chips(on_filter: Callable) -> ft.Row:
    """
    Cria chips de filtro de categoria.
    
    Args:
        on_filter: Função callback chamada ao selecionar filtro
    
    Returns:
        Row com os chips de filtro
    """
    return ft.Row([
        ft.Chip(label=ft.Text("Todos"), on_click=lambda _: on_filter("Todos")),
        ft.Chip(label=ft.Text("Financeiro"), on_click=lambda _: on_filter("Financeiro")),
        ft.Chip(label=ft.Text("Técnico"), on_click=lambda _: on_filter("Técnico")),
        ft.Chip(label=ft.Text("Logística"), on_click=lambda _: on_filter("Logística")),
    ], spacing=10)
