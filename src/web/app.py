"""
Aplicação web do SupportFlow AI (FastAPI + HTMX + Tailwind).

Expõe a interface HTML (server-rendered com HTMX) e uma API JSON reutilizável.
"""
import json
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from src.config import settings
from src.core.automation import SupportController
from src.data.db import (
    delete_ticket,
    get_db,
    get_stats,
    get_ticket,
    init_db,
    list_tickets,
    set_status,
)
from src.data.models import CATEGORIAS, STATUSES, URGENCIAS
from src.utils.logger import get_logger

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa o banco ao subir a aplicação."""
    init_db()
    logger.info("SupportFlow AI iniciado")
    yield


app = FastAPI(title="SupportFlow AI", version="2.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@lru_cache
def get_controller() -> SupportController:
    """Instancia (uma única vez) o controlador de sincronização."""
    return SupportController()


def render(request: Request, name: str, **context) -> HTMLResponse:
    """Renderiza um template (assinatura nova do Starlette: request primeiro)."""
    return templates.TemplateResponse(request, name, context)


def _toast(message: str, level: str = "success") -> dict:
    """Header HX-Trigger que dispara um toast e atualiza os KPIs no cliente."""
    return {
        "HX-Trigger": json.dumps(
            {"toast": {"message": message, "level": level}, "refreshKpis": True}
        )
    }


# --------------------------------------------------------------------------- #
# Páginas / fragmentos HTMX
# --------------------------------------------------------------------------- #
@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    """Página principal do dashboard."""
    return render(
        request,
        "index.html",
        stats=get_stats(db),
        tickets=list_tickets(db),
        categorias=("Todos",) + CATEGORIAS,
        urgencias=("Todos",) + URGENCIAS,
        statuses=("Todos",) + STATUSES,
        status_options=STATUSES,
        email_configured=settings.email_configured,
        ai_configured=settings.ai_configured,
    )


@app.get("/tickets", response_class=HTMLResponse)
def tickets_fragment(
    request: Request,
    search: str = Query(""),
    categoria: str = Query("Todos"),
    urgencia: str = Query("Todos"),
    status: str = Query("Todos"),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Retorna apenas a lista de tickets (fragmento HTMX) com filtros aplicados."""
    tickets = list_tickets(
        db, search=search, categoria=categoria, urgencia=urgencia, status=status
    )
    return render(
        request, "partials/ticket_list.html", tickets=tickets, status_options=STATUSES
    )


@app.get("/kpis", response_class=HTMLResponse)
def kpis_fragment(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    """Retorna o painel de KPIs (fragmento HTMX)."""
    return render(request, "partials/kpis.html", stats=get_stats(db))


@app.get("/tickets/{ticket_id}/detail", response_class=HTMLResponse)
def ticket_detail(
    request: Request, ticket_id: int, db: Session = Depends(get_db)
) -> HTMLResponse:
    """Retorna o modal de detalhes de um ticket."""
    ticket = get_ticket(db, ticket_id)
    if not ticket:
        return HTMLResponse("Ticket não encontrado", status_code=404)
    return render(
        request, "partials/ticket_detail.html", ticket=ticket, status_options=STATUSES
    )


@app.post("/sync", response_class=HTMLResponse)
async def sync(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    """Sincroniza e-mails (em threadpool, sem travar o servidor) e devolve a lista."""
    if not (settings.email_configured and settings.ai_configured):
        resp = render(
            request,
            "partials/ticket_list.html",
            tickets=list_tickets(db),
            status_options=STATUSES,
        )
        resp.headers.update(
            _toast("Configure EMAIL_USER, EMAIL_PASS e AI_API_KEY no .env", "error")
        )
        return resp

    try:
        controller = get_controller()
        processed = await run_in_threadpool(controller.run_sync)
        msg, level = f"{processed} e-mail(s) sincronizado(s)", "success"
    except Exception as err:  # noqa: BLE001 - exibimos o erro ao usuário
        logger.error(f"Erro ao sincronizar: {err}")
        msg, level = f"Erro ao sincronizar: {err}", "error"

    resp = render(
        request,
        "partials/ticket_list.html",
        tickets=list_tickets(db),
        status_options=STATUSES,
    )
    resp.headers.update(_toast(msg, level))
    return resp


@app.post("/tickets/{ticket_id}/status", response_class=HTMLResponse)
def update_status(
    request: Request,
    ticket_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Atualiza o status de um ticket e devolve o card atualizado."""
    if status not in STATUSES:
        return HTMLResponse("Status inválido", status_code=400)
    set_status(db, ticket_id, status)
    ticket = get_ticket(db, ticket_id)
    resp = render(
        request, "partials/ticket_card.html", ticket=ticket, status_options=STATUSES
    )
    resp.headers.update(_toast(f"Status alterado para '{status}'"))
    return resp


@app.delete("/tickets/{ticket_id}", response_class=HTMLResponse)
def remove_ticket(ticket_id: int, db: Session = Depends(get_db)) -> Response:
    """Remove um ticket. O card é removido da UI via swap vazio."""
    delete_ticket(db, ticket_id)
    resp = HTMLResponse("")
    resp.headers.update(_toast("Ticket removido"))
    return resp


# --------------------------------------------------------------------------- #
# API JSON reutilizável
# --------------------------------------------------------------------------- #
@app.get("/api/tickets")
def api_tickets(
    search: str = Query(""),
    categoria: str = Query("Todos"),
    urgencia: str = Query("Todos"),
    status: str = Query("Todos"),
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Lista tickets em JSON (filtros + paginação)."""
    tickets = list_tickets(
        db,
        search=search,
        categoria=categoria,
        urgencia=urgencia,
        status=status,
        limit=limit,
        offset=offset,
    )
    return JSONResponse([t.to_dict() for t in tickets])


@app.get("/api/stats")
def api_stats(db: Session = Depends(get_db)) -> JSONResponse:
    """Retorna as métricas agregadas em JSON."""
    return JSONResponse(get_stats(db))


@app.get("/export.json")
def export_json(db: Session = Depends(get_db)) -> JSONResponse:
    """Exporta todos os tickets como JSON (download)."""
    tickets = list_tickets(db, limit=100000)
    return JSONResponse(
        [t.to_dict() for t in tickets],
        headers={"Content-Disposition": "attachment; filename=tickets_export.json"},
    )


@app.get("/health")
def health() -> dict:
    """Health check simples."""
    return {
        "status": "ok",
        "email_configured": settings.email_configured,
        "ai_configured": settings.ai_configured,
    }
