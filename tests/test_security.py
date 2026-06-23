"""
Testes para o módulo de segurança (hash de senha e criptografia de segredos).
"""
from src import security


class TestPasswordHashing:
    """Hash e verificação de senhas (bcrypt)."""

    def test_hash_and_verify(self):
        hashed = security.hash_password("minha-senha-123")
        assert hashed != "minha-senha-123"
        assert security.verify_password("minha-senha-123", hashed) is True

    def test_wrong_password_fails(self):
        hashed = security.hash_password("correta")
        assert security.verify_password("errada", hashed) is False

    def test_verify_invalid_hash_is_safe(self):
        assert security.verify_password("x", "não-é-um-hash") is False


class TestSecretEncryption:
    """Criptografia simétrica de segredos (Fernet)."""

    def test_encrypt_decrypt_roundtrip(self):
        token = security.encrypt("senha-de-app-do-email")
        assert token != "senha-de-app-do-email"
        assert security.decrypt(token) == "senha-de-app-do-email"

    def test_empty_values(self):
        assert security.encrypt("") == ""
        assert security.decrypt("") == ""

    def test_decrypt_invalid_token_returns_empty(self):
        assert security.decrypt("token-invalido") == ""
