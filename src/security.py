"""
Utilitários de segurança: hash de senhas e criptografia de segredos.

- **Senhas de login**: armazenadas como hash bcrypt (irreversível).
- **Senhas de e-mail dos clientes**: precisam ser usadas para conectar ao
  IMAP/SMTP, então são guardadas **criptografadas** (Fernet/AES) e descriptadas
  apenas em memória no momento do uso.

A chave de criptografia é derivada de ``SECRET_KEY`` (variável de ambiente),
garantindo que o mesmo segredo do app protege também os dados sensíveis.
"""
import base64
import hashlib

import bcrypt
from cryptography.fernet import Fernet, InvalidToken

from src import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Senhas de login (bcrypt)
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Gera o hash bcrypt de uma senha."""
    # bcrypt limita a 72 bytes; truncamos defensivamente.
    raw = password.encode("utf-8")[:72]
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verifica se a senha corresponde ao hash bcrypt armazenado."""
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Criptografia de segredos (Fernet)
# ---------------------------------------------------------------------------
def _fernet() -> Fernet:
    """Constrói a instância Fernet a partir da SECRET_KEY do app."""
    secret = config.get("SECRET_KEY") or "dev-insecure-secret-change-me"
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt(plaintext: str) -> str:
    """Criptografa um texto (ex.: senha de e-mail do cliente)."""
    if not plaintext:
        return ""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(token: str) -> str:
    """Descriptografa um texto; retorna string vazia se inválido."""
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):
        logger.warning("Falha ao descriptografar segredo (SECRET_KEY mudou?)")
        return ""
