"""Roteador de IA serviço-a-serviço — consumido pelo Floatech CRM.

Expõe a inteligência do SupportFlow AI (Gemini) como API máquina→máquina,
autenticada por chave de serviço (``FLOATECH_SERVICE_API_KEY``). Reaproveita
o ``AIService`` existente. Ver ``API_CONTRACT.md`` no repo floatech-crm.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from src.core.ai_engine import AIService
from src.utils.logger import get_logger
from src.web.auth import require_service_key

router = APIRouter()
logger = get_logger(__name__)


class QualifyLeadRequest(BaseModel):
    text: str
    context: Optional[str] = ""
    categories: Optional[str] = None


class GenerateContentRequest(BaseModel):
    kind: str  # post | ad | caption | reply
    brief: str
    tone: Optional[str] = ""
    channel: Optional[str] = "instagram"


class AnalyzeFunnelRequest(BaseModel):
    pipeline: dict
    highlights: Optional[List[dict]] = None


class KeywordResearchRequest(BaseModel):
    seed: str
    context: Optional[str] = ""


class AnalyzeConversionsRequest(BaseModel):
    metrics: dict


class CompareCompetitorsRequest(BaseModel):
    our_summary: dict
    competitor_ads: Optional[List[dict]] = None


class BestTimesRequest(BaseModel):
    platform: str
    niche: Optional[str] = ""
    context: Optional[str] = ""


class SocialPlanRequest(BaseModel):
    context: dict


# ── Construtor de Campanha/Funil ──────────────────────────────────────
class AvatarRequest(BaseModel):
    cliente: str
    objetivo: Optional[str] = ""
    tentativas: Optional[str] = ""
    obstaculo: Optional[str] = ""


class OfferRequest(BaseModel):
    cliente: str
    produto: str
    avatar: Optional[dict] = None


class CopyRequest(BaseModel):
    kind: str  # anuncio | email | pagina
    produto: str
    cliente: str
    oferta: Optional[dict] = None
    tom: Optional[str] = ""


class EmailSeqRequest(BaseModel):
    resultado: str
    objecao: Optional[str] = ""
    produto: Optional[str] = ""
    cliente: Optional[str] = ""


class HooksRequest(BaseModel):
    gancho: str


class HumanizeRequest(BaseModel):
    texto: str


class SentimentRequest(BaseModel):
    texts: List[str]
    brand: Optional[str] = ""


class CopyThiefRequest(BaseModel):
    material: str
    produto: Optional[str] = ""
    cliente: Optional[str] = ""


@router.post("/qualify-lead", dependencies=[Depends(require_service_key)])
async def qualify_lead(payload: QualifyLeadRequest):
    """Qualifica um lead: retorna ai_score, stage sugerido e resumo."""
    ai = AIService()
    result = await run_in_threadpool(
        ai.qualify_lead, payload.text, payload.context or "", payload.categories
    )
    return result


@router.post("/generate-content", dependencies=[Depends(require_service_key)])
async def generate_content(payload: GenerateContentRequest):
    """Gera conteúdo de marketing (post/anúncio/legenda/resposta)."""
    ai = AIService()
    result = await run_in_threadpool(
        ai.generate_content,
        payload.kind,
        payload.brief,
        payload.tone or "",
        payload.channel or "instagram",
    )
    return result


@router.post("/analyze-funnel", dependencies=[Depends(require_service_key)])
async def analyze_funnel(payload: AnalyzeFunnelRequest):
    """Copiloto: analisa o funil e direciona as próximas decisões (Gemini)."""
    ai = AIService()
    result = await run_in_threadpool(
        ai.analyze_funnel, payload.pipeline, payload.highlights or []
    )
    return result


@router.post("/keyword-research", dependencies=[Depends(require_service_key)])
async def keyword_research(payload: KeywordResearchRequest):
    """Pesquisa de palavras-chave para marketing (Gemini)."""
    ai = AIService()
    result = await run_in_threadpool(ai.keyword_research, payload.seed, payload.context or "")
    return result


@router.post("/analyze-conversions", dependencies=[Depends(require_service_key)])
async def analyze_conversions(payload: AnalyzeConversionsRequest):
    """Diz o que converte, o que não e quais decisões tomar (Gemini)."""
    ai = AIService()
    result = await run_in_threadpool(ai.analyze_conversions, payload.metrics)
    return result


@router.post("/compare-competitors", dependencies=[Depends(require_service_key)])
async def compare_competitors(payload: CompareCompetitorsRequest):
    """Engenharia reversa dos melhores anúncios de concorrentes (Gemini)."""
    ai = AIService()
    result = await run_in_threadpool(
        ai.compare_competitors, payload.our_summary, payload.competitor_ads or []
    )
    return result


@router.post("/best-times", dependencies=[Depends(require_service_key)])
async def best_times(payload: BestTimesRequest):
    """Melhores horários para postar (social media sênior, via Gemini)."""
    ai = AIService()
    result = await run_in_threadpool(ai.best_times, payload.platform, payload.niche or "", payload.context or "")
    return result


@router.post("/social-plan", dependencies=[Depends(require_service_key)])
async def social_plan(payload: SocialPlanRequest):
    """Plano semanal de social media + mídia paga (sênior, via Gemini)."""
    ai = AIService()
    result = await run_in_threadpool(ai.social_plan, payload.context)
    return result


# ── Construtor de Campanha/Funil (workflow passo a passo) ─────────────
@router.post("/avatar", dependencies=[Depends(require_service_key)])
async def avatar(payload: AvatarRequest):
    """Passo 1: dores/medos/desejos do cliente."""
    ai = AIService()
    return await run_in_threadpool(
        ai.client_avatar, payload.cliente, payload.objetivo or "", payload.tentativas or "", payload.obstaculo or ""
    )


@router.post("/offer", dependencies=[Depends(require_service_key)])
async def offer(payload: OfferRequest):
    """Passo 2: monta a oferta."""
    ai = AIService()
    return await run_in_threadpool(ai.build_offer, payload.cliente, payload.produto, payload.avatar)


@router.post("/copy", dependencies=[Depends(require_service_key)])
async def copy(payload: CopyRequest):
    """Passo 3: escreve a copy (gancho→CTA)."""
    ai = AIService()
    return await run_in_threadpool(
        ai.write_copy, payload.kind, payload.produto, payload.cliente, payload.oferta, payload.tom or ""
    )


@router.post("/emails", dependencies=[Depends(require_service_key)])
async def emails(payload: EmailSeqRequest):
    """Passo 4: sequência de 3 e-mails."""
    ai = AIService()
    return await run_in_threadpool(
        ai.email_sequence, payload.resultado, payload.objecao or "", payload.produto or "", payload.cliente or ""
    )


@router.post("/hooks", dependencies=[Depends(require_service_key)])
async def hooks(payload: HooksRequest):
    """Passo 5: 5 variações do gancho."""
    ai = AIService()
    return await run_in_threadpool(ai.hook_variations, payload.gancho)


@router.post("/humanize", dependencies=[Depends(require_service_key)])
async def humanize(payload: HumanizeRequest):
    """Passo final: humaniza/remove clichê."""
    ai = AIService()
    return await run_in_threadpool(ai.humanize, payload.texto)


@router.post("/sentiment", dependencies=[Depends(require_service_key)])
async def sentiment(payload: SentimentRequest):
    """Social listening: sentimento + temas + alertas de um conjunto de menções."""
    ai = AIService()
    return await run_in_threadpool(ai.analyze_sentiment, payload.texts, payload.brand or "")


@router.post("/copy-thief", dependencies=[Depends(require_service_key)])
async def copy_thief(payload: CopyThiefRequest):
    """Copy Thief: engenharia reversa de uma copy + versão original adaptada."""
    ai = AIService()
    return await run_in_threadpool(ai.copy_thief, payload.material, payload.produto or "", payload.cliente or "")
