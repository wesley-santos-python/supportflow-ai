"""
Componentes reutilizáveis da interface do SupportFlow AI.

Este módulo contém componentes Flet padronizados para uso no dashboard.
"""
import flet as ft
from typing import Callable


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
