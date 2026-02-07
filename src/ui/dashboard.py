"""
Dashboard principal do SupportFlow AI.

Interface gráfica moderna com Flet para visualização e gestão de tickets.
"""
import flet as ft
import pyperclip
import json
from datetime import datetime
from typing import Optional

from src.data.db import SessionLocal
from src.data.models import Ticket
from src.core.automation import SupportController
from src.ui.components import filter_chips, urgency_badge
from src.utils.logger import get_logger
from sqlalchemy import case

logger = get_logger(__name__)


def main_dashboard(page: ft.Page) -> None:
    """
    Função principal do dashboard.
    
    Args:
        page: Página Flet para renderização da UI.
    """
    # Configuração da página
    page.title = "SupportFlow AI - Gestão Inteligente"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#111214"
    page.padding = 30

    # Inicialização de componentes
    controller = SupportController()
    list_view = ft.ListView(expand=True, spacing=15)
    
    # Loading overlay com animação
    loading_overlay = ft.Container(
        content=ft.Column([
            ft.ProgressRing(width=50, height=50, stroke_width=4, color=ft.Colors.BLUE_400),
            ft.Text("Sincronizando e-mails...", size=16, color=ft.Colors.GREY_400),
            ft.Text("Analisando com IA...", size=12, color=ft.Colors.GREY_600),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15),
        alignment=ft.Alignment(0.0, 0.0),  # Centro
        bgcolor=ft.Colors.with_opacity(0.9, "#111214"),
        visible=False,
        expand=True,
    )

    def show_details(ticket: Ticket) -> None:
        """Exibe modal com detalhes do ticket."""
        logger.info(f"Abrindo detalhes do ticket: {ticket.subject}")
        
        def close_dlg(e):
            dlg.open = False
            page.update()

        def copy_to_clipboard(e):
            pyperclip.copy(ticket.resposta_sugerida or "")
            snack = ft.SnackBar(content=ft.Text("✓ Mensagem copiada!"), open=True)
            page.overlay.append(snack)
            page.update()
        
        def send_email_placeholder(e):
            snack = ft.SnackBar(content=ft.Text("Funcionalidade de envio em desenvolvimento..."), open=True)
            page.overlay.append(snack)
            page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Sugestão de Resposta da IA"),
            content=ft.Column([
                ft.Text("Resumo:", weight="bold", color=ft.Colors.BLUE_400),
                ft.Text(ticket.resumo or "Análise ainda não concluída"),
                ft.Divider(color=ft.Colors.GREY_800),
                ft.Text("Sugestão:", weight="bold", color=ft.Colors.GREEN_400),
                ft.TextField(
                    value=ticket.resposta_sugerida or "Aguardando processamento...", 
                    multiline=True, 
                    min_lines=5,
                    read_only=True,
                    selection_color=ft.Colors.BLUE_200,
                ),
            ], tight=True, width=450, scroll=ft.ScrollMode.AUTO),
            actions=[
                ft.TextButton("Copiar Texto", on_click=copy_to_clipboard),
                ft.ElevatedButton("Enviar Email", bgcolor=ft.Colors.BLUE_700, color="white", on_click=send_email_placeholder),
                ft.TextButton("Fechar", on_click=close_dlg),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def create_ticket_card(ticket: Ticket) -> ft.Container:
        """Cria um card de ticket com evento de clique."""
        badge_color = {
            "Alta": ft.Colors.RED_700,
            "Média": ft.Colors.ORANGE_700,
            "Baixa": ft.Colors.GREEN_700
        }.get(ticket.urgencia, ft.Colors.GREEN_700)
        
        def on_card_click(e, t=ticket):
            show_details(t)
        
        return ft.Container(
            bgcolor="#1e1f22",
            padding=15,
            border_radius=12,
            ink=True,
            on_click=on_card_click,
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.EMAIL_OUTLINED, color=ft.Colors.BLUE_400, size=20),
                    ft.Text(ticket.subject, weight="bold", size=15, expand=True),
                    ft.Container(
                        content=ft.Text(ticket.urgencia or "Baixa", size=9, weight="bold"),
                        bgcolor=badge_color,
                        padding=ft.padding.symmetric(horizontal=10, vertical=2),
                        border_radius=15
                    )
                ]),
                ft.Text(f"De: {ticket.sender}", size=11, italic=True, color=ft.Colors.GREY_500),
                ft.Text(ticket.resumo or "Análise Pendente...", size=13, color=ft.Colors.GREY_300, max_lines=2),
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

    def load_tickets(filtro: str = "Todos") -> None:
        """Carrega tickets do banco de dados com filtro opcional."""
        db = SessionLocal()
        try:
            query = db.query(Ticket)
            if filtro != "Todos":
                query = query.filter(Ticket.categoria.ilike(f"%{filtro}%"))
            
            ordem = case(
                (Ticket.urgencia == "Alta", 1), 
                (Ticket.urgencia == "Média", 2), 
                else_=3
            )
            tickets = query.order_by(ordem, Ticket.created_at.desc()).all()
            
            list_view.controls.clear()
            for t in tickets:
                list_view.controls.append(create_ticket_card(t))
            
            logger.debug(f"Carregados {len(tickets)} tickets (filtro: {filtro})")
        finally:
            db.close()
        page.update()

    def sync_emails(e) -> None:
        """Sincroniza e-mails e atualiza a lista de tickets."""
        loading_overlay.visible = True
        page.update()
        try:
            processed = controller.run_sync()
            load_tickets()
            # Mostra notificação de sucesso
            snack = ft.SnackBar(content=ft.Text(f"✓ {processed} tickets sincronizados!"), open=True)
            page.overlay.append(snack)
            logger.info(f"Sincronização via UI: {processed} tickets")
        except Exception as err:
            logger.error(f"Erro ao sincronizar: {err}")
            snack = ft.SnackBar(content=ft.Text(f"Erro: {err}"), open=True, bgcolor=ft.Colors.RED_700)
            page.overlay.append(snack)
        finally:
            loading_overlay.visible = False
            page.update()

    def export_json(e) -> None:
        """Exporta todos os tickets como JSON."""
        db = SessionLocal()
        try:
            tickets = db.query(Ticket).all()
            data = []
            for t in tickets:
                data.append({
                    "id": t.id,
                    "uid": t.uid,
                    "sender": t.sender,
                    "subject": t.subject,
                    "body": t.body,
                    "urgencia": t.urgencia,
                    "categoria": t.categoria,
                    "resumo": t.resumo,
                    "resposta_sugerida": t.resposta_sugerida,
                    "status": t.status,
                    "created_at": t.created_at.isoformat() if t.created_at else None
                })
            
            # Salva arquivo JSON
            filename = f"tickets_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            snack = ft.SnackBar(content=ft.Text(f"✓ Exportado: {filename} ({len(data)} tickets)"), open=True)
            page.overlay.append(snack)
            logger.info(f"Exportados {len(data)} tickets para {filename}")
        except Exception as err:
            logger.error(f"Erro ao exportar: {err}")
            snack = ft.SnackBar(content=ft.Text(f"Erro: {err}"), open=True, bgcolor=ft.Colors.RED_700)
            page.overlay.append(snack)
        finally:
            db.close()
        page.update()

    # Montagem da UI com Stack para overlay
    content_column = ft.Column([
        ft.Row([
            ft.Text("Tickets Analisados por IA", size=30, weight="bold", expand=True),
            ft.ElevatedButton("Exportar JSON", icon=ft.Icons.DOWNLOAD, on_click=export_json, bgcolor=ft.Colors.GREEN_700),
            ft.ElevatedButton("Sincronizar", icon=ft.Icons.SYNC, on_click=sync_emails),
        ]),
        filter_chips(load_tickets),
        ft.Divider(height=20, color=ft.Colors.GREY_900),
        list_view
    ], expand=True)
    
    page.add(
        ft.Stack([
            content_column,
            loading_overlay,
        ], expand=True)
    )
    
    load_tickets()