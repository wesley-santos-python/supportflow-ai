"""
Aplicação web (FastAPI) do SupportFlow AI.

Responsável por:
    - Inicializar banco de dados e agendador no startup
    - Encerrar o agendador no shutdown
    - Montar arquivos estáticos e templates
    - Registrar os roteadores de páginas e de API
"""
import os
import time
from contextlib import asynccontextmanager

# Fuso horário da aplicação (datas dos tickets, logs). Brasil por padrão;
# sobrescreva com a variável de ambiente TZ se precisar de outro fuso.
os.environ.setdefault("TZ", "America/Sao_Paulo")
try:
    time.tzset()
except (AttributeError, OSError):  # tzset não existe no Windows
    pass

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware

from src import config
from src.core.scheduler import shutdown_scheduler, start_scheduler
from src.data.db import init_db
from src.utils.logger import get_logger

logger = get_logger(__name__)

_BASE_DIR = os.path.dirname(__file__)
_TEMPLATES_DIR = os.path.join(_BASE_DIR, "templates")
_STATIC_DIR = os.path.join(_BASE_DIR, "static")

# Instância de templates compartilhada por todos os roteadores.
templates = Jinja2Templates(directory=_TEMPLATES_DIR)


def _brt(value) -> str:
    """Formata um timestamp (armazenado em UTC) no horário de Brasília."""
    from datetime import datetime, timedelta, timezone

    if not value:
        return ""
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("America/Sao_Paulo")
    except Exception:  # pragma: no cover - fallback fixo UTC-3
        tz = timezone(timedelta(hours=-3))

    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    elif isinstance(value, datetime):
        dt = value
    else:
        return str(value)

    if dt.tzinfo is None:  # naive = UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz).strftime("%d/%m/%Y %H:%M")


def _inject_globals() -> None:
    """Disponibiliza variáveis de marca globalmente nos templates."""
    templates.env.globals["company_name"] = config.get("COMPANY_NAME", "Floatech")
    templates.env.globals["app_name"] = config.get("APP_NAME", "SupportFlow AI")
    templates.env.filters["brt"] = _brt


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida da aplicação: prepara recursos e libera no encerramento."""
    init_db()
    _inject_globals()
    start_scheduler()
    logger.info("SupportFlow AI iniciado")
    yield
    shutdown_scheduler()


def create_app() -> FastAPI:
    """Cria e configura a instância FastAPI."""
    app = FastAPI(
        title="SupportFlow AI",
        description="SaaS de gestão inteligente de tickets de suporte — by Floatech",
        version="2.0.0",
        lifespan=lifespan,
    )

    # Sessão assinada (cookie) para autenticação multi-cliente.
    app.add_middleware(
        SessionMiddleware,
        secret_key=config.get("SECRET_KEY", "dev-insecure-secret-change-me"),
        max_age=60 * 60 * 24 * 7,  # 7 dias
        same_site="lax",
    )

    # Compressão das respostas (HTML/JSON/CSS) — páginas mais leves e rápidas.
    app.add_middleware(GZipMiddleware, minimum_size=600)

    @app.middleware("http")
    async def _cache_static(request, call_next):
        """Cache no navegador para os arquivos estáticos (acelera e economiza banda)."""
        response = await call_next(request)
        if request.url.path.startswith("/static/"):
            # Fresco por 5 min; depois serve do cache enquanto revalida (ETag).
            response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=86400"
        return response

    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        """Health-check leve para o Railway/monitoramento (sem autenticação)."""
        return {"status": "ok", "app": app.title, "version": app.version}

    # Import tardio evita ciclos durante a montagem.
    from src.web.routes import api, auth_routes, pages

    app.include_router(auth_routes.router)
    app.include_router(pages.router)
    app.include_router(api.router, prefix="/api")

    return app


app = create_app()
