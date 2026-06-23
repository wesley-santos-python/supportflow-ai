"""
Autenticação baseada em sessão (cookie assinado).

Fornece utilitários para identificar o cliente logado e dependências do
FastAPI para proteger rotas de API. Para páginas HTML, use
:func:`current_user` e redirecione para ``/login`` quando ``None``.
"""
from typing import Optional

from fastapi import HTTPException, Request

from src.data import db
from src.data.models import User

SESSION_KEY = "user_id"


def login_session(request: Request, user_id: int) -> None:
    """Registra o usuário autenticado na sessão."""
    request.session[SESSION_KEY] = user_id


def logout_session(request: Request) -> None:
    """Encerra a sessão do usuário."""
    request.session.pop(SESSION_KEY, None)


def current_user(request: Request) -> Optional[User]:
    """Retorna o usuário logado (ou ``None``)."""
    user_id = request.session.get(SESSION_KEY)
    if not user_id:
        return None
    return db.get_user_by_id(user_id)


def require_api_user(request: Request) -> User:
    """
    Dependência para rotas de API: exige autenticação.

    Raises:
        HTTPException: 401 se não houver usuário logado.
    """
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Não autenticado")
    return user
