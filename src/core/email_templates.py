"""
Renderização do e-mail de resposta em HTML.

Oferece 3 padrões visuais (``moderno``, ``classico``, ``minimalista``), todos
com cabeçalho (logo ou nome da empresa), corpo e rodapé com as informações de
contato configuradas pelo cliente. Estilos são inline (requisito de e-mail).

A mesma função alimenta tanto a pré-visualização na tela de configurações
quanto o envio real — garantindo que o preview seja fiel.
"""
import html
from typing import Dict

TEMPLATE_NAMES = ("moderno", "classico", "minimalista")

_TEAL = "#00B8A9"
_INK = "#14161A"
_MUTED = "#6b7280"
_LINE = "#e6e0d2"

# Chaves de marca lidas da configuração do cliente.
_BRANDING_KEYS = (
    "EMAIL_FORMAT", "EMAIL_TEMPLATE", "EMAIL_HEADER", "COMPANY_NAME",
    "COMPANY_LOGO_URL", "COMPANY_EMAIL", "COMPANY_PHONE", "COMPANY_SITE",
    "COMPANY_ADDRESS",
)


def branding_from_cfg(cfg) -> Dict[str, str]:
    """Extrai os campos de marca de uma configuração (UserConfig/config)."""
    return {k: (cfg.get(k) or "") for k in _BRANDING_KEYS}


def _esc(text: str) -> str:
    return html.escape(text or "")


def _logo_or_name(b: Dict[str, str], color: str) -> str:
    """Logo (se houver URL) ou o nome da empresa como título do cabeçalho."""
    logo = b.get("COMPANY_LOGO_URL")
    if logo:
        return (f'<img src="{_esc(logo)}" alt="{_esc(b.get("COMPANY_NAME"))}" '
                f'style="max-height:46px;max-width:220px;display:block">')
    name = b.get("COMPANY_NAME") or "Suporte"
    return f'<span style="font-size:20px;font-weight:700;color:{color}">{_esc(name)}</span>'


def _body_html(body: str) -> str:
    paragraphs = [p.strip() for p in (body or "").split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [(body or "").strip()]
    return "".join(
        f'<p style="margin:0 0 14px;font-size:15px;line-height:1.65;color:{_INK}">'
        f'{_esc(p).replace(chr(10), "<br>")}</p>'
        for p in paragraphs if p
    )


def _contact_line(b: Dict[str, str]) -> str:
    bits = []
    if b.get("COMPANY_PHONE"):
        bits.append(_esc(b["COMPANY_PHONE"]))
    if b.get("COMPANY_EMAIL"):
        bits.append(_esc(b["COMPANY_EMAIL"]))
    if b.get("COMPANY_SITE"):
        bits.append(_esc(b["COMPANY_SITE"]))
    return " &nbsp;·&nbsp; ".join(bits)


def _footer_inner(b: Dict[str, str]) -> str:
    name = _esc(b.get("COMPANY_NAME") or "")
    contact = _contact_line(b)
    address = _esc(b.get("COMPANY_ADDRESS") or "")
    lines = []
    if name:
        lines.append(f'<div style="font-weight:600;color:{_INK}">{name}</div>')
    if contact:
        lines.append(f'<div>{contact}</div>')
    if address:
        lines.append(f'<div>{address}</div>')
    return "".join(lines) or '<div>Enviado pela nossa central de suporte.</div>'


def _wrap(content: str, bg: str = "#f3f0e8") -> str:
    return (
        f'<!DOCTYPE html><html><body style="margin:0;padding:24px;background:{bg};'
        f'font-family:Arial,Helvetica,sans-serif">'
        f'<div style="max-width:600px;margin:0 auto">{content}</div></body></html>'
    )


def _moderno(body: str, b: Dict[str, str]) -> str:
    header_extra = (f'<div style="color:rgba(255,255,255,.85);font-size:13px;margin-top:4px">'
                    f'{_esc(b.get("EMAIL_HEADER"))}</div>') if b.get("EMAIL_HEADER") else ""
    return _wrap(
        f'<div style="background:#fff;border-radius:14px;overflow:hidden;'
        f'box-shadow:0 6px 24px rgba(20,22,26,.08)">'
        f'<div style="background:{_TEAL};padding:22px 28px">'
        f'{_logo_or_name(b, "#ffffff")}{header_extra}</div>'
        f'<div style="padding:28px">{_body_html(body)}</div>'
        f'<div style="padding:18px 28px;background:#fafafa;border-top:1px solid {_LINE};'
        f'font-size:12px;line-height:1.7;color:{_MUTED}">{_footer_inner(b)}</div>'
        f'</div>'
    )


def _classico(body: str, b: Dict[str, str]) -> str:
    tagline = (f'<div style="font-size:13px;color:{_MUTED};font-style:italic;margin-top:2px">'
               f'{_esc(b.get("EMAIL_HEADER"))}</div>') if b.get("EMAIL_HEADER") else ""
    return _wrap(
        f'<div style="background:#fff;padding:32px 36px;border:1px solid {_LINE};'
        f'font-family:Georgia,\'Times New Roman\',serif">'
        f'<div style="text-align:center;padding-bottom:16px;border-bottom:2px solid {_INK}">'
        f'{_logo_or_name(b, _INK)}{tagline}</div>'
        f'<div style="padding:24px 0">{_body_html(body)}</div>'
        f'<div style="padding-top:16px;border-top:1px solid {_LINE};font-size:12px;'
        f'line-height:1.7;color:{_MUTED};text-align:center">{_footer_inner(b)}</div>'
        f'</div>',
        bg="#ffffff",
    )


def _minimalista(body: str, b: Dict[str, str]) -> str:
    tagline = (f' — <span style="color:{_MUTED}">{_esc(b.get("EMAIL_HEADER"))}</span>'
               if b.get("EMAIL_HEADER") else "")
    return _wrap(
        f'<div style="padding:8px 4px">'
        f'<div style="margin-bottom:20px">{_logo_or_name(b, _INK)}{tagline}</div>'
        f'{_body_html(body)}'
        f'<div style="margin-top:24px;padding-top:14px;border-top:1px solid {_LINE};'
        f'font-size:12px;line-height:1.7;color:{_MUTED}">{_footer_inner(b)}</div>'
        f'</div>',
        bg="#ffffff",
    )


_RENDERERS = {"moderno": _moderno, "classico": _classico, "minimalista": _minimalista}


def render_email(body: str, branding: Dict[str, str]) -> str:
    """Renderiza o corpo em HTML usando o template escolhido na configuração."""
    template = (branding.get("EMAIL_TEMPLATE") or "moderno").lower()
    return _RENDERERS.get(template, _moderno)(body, branding)
