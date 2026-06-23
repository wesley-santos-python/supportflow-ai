"""
Rotas de autenticação: cadastro, login e logout.
"""
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src import security
from src.data import db
from src.web import auth

router = APIRouter()


def _templates():
    """Acesso tardio aos templates (evita import circular com app)."""
    from src.web.app import templates

    return templates


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, erro: str = "", ok: str = ""):
    """Exibe a tela de login."""
    if auth.current_user(request):
        return RedirectResponse("/", status_code=303)
    return _templates().TemplateResponse(
        request, "login.html", {"erro": erro, "ok": ok}
    )


@router.post("/login")
def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    """Processa o login do cliente."""
    user = db.get_user_by_email(email)
    if not user or not security.verify_password(password, user.password_hash):
        return _templates().TemplateResponse(
            request, "login.html", {"erro": "E-mail ou senha inválidos."}
        )
    auth.login_session(request, user.id)
    return RedirectResponse("/", status_code=303)


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, erro: str = ""):
    """Exibe a tela de cadastro."""
    if auth.current_user(request):
        return RedirectResponse("/", status_code=303)
    return _templates().TemplateResponse(request, "register.html", {"erro": erro})


@router.post("/register")
def register_submit(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    """Cria uma nova conta de cliente."""
    if len(password) < 6:
        return _templates().TemplateResponse(
            request, "register.html", {"erro": "A senha deve ter ao menos 6 caracteres."}
        )
    if db.get_user_by_email(email):
        return _templates().TemplateResponse(
            request, "register.html", {"erro": "Este e-mail já está cadastrado."}
        )

    user_id = db.create_user(name, email, security.hash_password(password))
    if not user_id:
        return _templates().TemplateResponse(
            request, "register.html", {"erro": "Não foi possível criar a conta."}
        )

    auth.login_session(request, user_id)
    return RedirectResponse("/", status_code=303)


@router.get("/logout")
def logout(request: Request):
    """Encerra a sessão e volta ao login."""
    auth.logout_session(request)
    return RedirectResponse("/login", status_code=303)
