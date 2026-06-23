"""
Heurística de risco de remetente (anti-fraude / phishing).

Avalia um endereço de e-mail e sinaliza quando ele *parece* golpe — por
exemplo, alguém se passando por um banco usando um provedor gratuito e
números aleatórios (``bancotal22332211@gmail.com``), em vez do domínio
oficial da instituição.

A análise é apenas indicativa (não bloqueia nada) e explica o motivo, para
o operador decidir com contexto.
"""
import re
from typing import Dict, List

# Provedores de e-mail gratuitos: legítimos para pessoas, mas suspeitos quando
# o remetente se apresenta como uma marca/instituição (banco, gov, loja...).
FREE_PROVIDERS = {
    "gmail.com", "googlemail.com", "hotmail.com", "hotmail.com.br", "outlook.com",
    "outlook.com.br", "live.com", "yahoo.com", "yahoo.com.br", "icloud.com",
    "proton.me", "protonmail.com", "aol.com", "bol.com.br", "uol.com.br", "terra.com.br",
}

# Palavras que sugerem que o remetente se passa por marca/instituição.
BRAND_WORDS = (
    "banco", "bank", "caixa", "bradesco", "itau", "santander", "nubank", "inter",
    "bb", "sicoob", "sicredi", "pix", "gov", "receita", "fazenda", "correios",
    "premio", "premios", "sorteio", "ganhador", "seguranca", "segur", "cartao",
    "fatura", "boleto", "cobranca", "mercadopago", "mercadolivre", "picpay",
    "paypal", "apple", "microsoft", "google", "netflix", "amazon", "magalu",
    "americanas", "suporte", "atendimento", "oficial", "verificacao", "verifica",
)

# Extensões de domínio frequentemente usadas em golpes (baratas/descartáveis).
SUSPICIOUS_TLDS = (
    ".xyz", ".top", ".click", ".online", ".site", ".buzz", ".shop", ".club",
    ".work", ".link", ".live", ".rest", ".monster", ".cyou", ".sbs",
)

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", re.IGNORECASE)


def extract_email(sender: str) -> str:
    """Extrai o endereço de e-mail puro de um remetente (com ou sem nome)."""
    if not sender:
        return ""
    bracket = re.search(r"<([^>]+)>", sender)
    candidate = bracket.group(1) if bracket else sender
    found = _EMAIL_RE.search(candidate)
    return (found.group(0) if found else candidate).strip().lower()


def assess_sender(sender: str) -> Dict[str, object]:
    """
    Avalia o risco de um remetente.

    Returns:
        Dicionário com ``level`` ("alto"/"medio"/"ok"), ``reasons`` (lista de
        motivos legíveis) e ``email`` (endereço extraído).
    """
    email = extract_email(sender)
    reasons: List[str] = []

    if "@" not in email:
        return {"level": "ok", "reasons": [], "email": email}

    local, _, domain = email.partition("@")
    haystack = f"{(sender or '').lower()} {local}"

    brand_hit = next((w for w in BRAND_WORDS if w in haystack), None)
    free_provider = domain in FREE_PROVIDERS
    digit_run = bool(re.search(r"\d{3,}", local))
    many_digits = sum(c.isdigit() for c in local) >= 4
    suspicious_tld = any(domain.endswith(tld) for tld in SUSPICIOUS_TLDS)

    if brand_hit and free_provider:
        reasons.append(
            f"Diz ser '{brand_hit}', mas usa um provedor gratuito ({domain}) "
            "em vez do domínio oficial."
        )
    if digit_run or many_digits:
        reasons.append("Números no endereço, típico de conta descartável.")
    if suspicious_tld:
        reasons.append(f"Domínio com extensão pouco confiável ({domain}).")

    # Impersonação de marca + qualquer sinal forte => alto risco.
    if brand_hit and (free_provider or digit_run or suspicious_tld):
        level = "alto"
    elif reasons:
        level = "medio"
    else:
        level = "ok"

    return {"level": level, "reasons": reasons, "email": email}
