"""
Serviço de IA — multi-provedor (Google Gemini ou Anthropic Claude).

Responsável por:
    - Analisar tickets de suporte (urgência, categoria, resumo, resposta)
    - Reescrever/ajustar respostas conforme instruções do operador
    - Gerar um resumo consolidado de e-mails urgentes (ex.: para WhatsApp)
    - Features de marketing/estratégia consumidas pelo Floatech CRM

O provedor é escolhido por ``LLM_PROVIDER`` (``gemini`` | ``claude``).
Claude (Anthropic) costuma render melhor em análise/estratégia — defina
``LLM_PROVIDER=claude`` + ``ANTHROPIC_API_KEY`` para usá-lo. O modelo é
configurável (``GEMINI_MODEL`` / ``CLAUDE_MODEL``; padrão Claude: ``claude-opus-4-8``).
"""
import json
from types import SimpleNamespace
from typing import Dict, List

try:  # SDK do Gemini (opcional em ambiente de testes/CI sem o pacote)
    from google import genai
except ImportError:  # pragma: no cover - resolvido por mock nos testes
    genai = None

try:  # SDK da Anthropic (opcional; só necessário com LLM_PROVIDER=claude)
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None

from src import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AIService:
    """
    Serviço de IA para análise de tickets usando Google Gemini.

    A chave de API e o modelo são resolvidos via :mod:`src.config`, de modo
    que podem ser configurados pela interface web ou por variável de ambiente.

    Attributes:
        client: Cliente da API Google GenAI.
        model: Identificador do modelo Gemini em uso.
    """

    def __init__(self) -> None:
        """Inicializa o cliente do provedor configurado (Gemini ou Claude)."""
        self.provider = (config.get("LLM_PROVIDER", "gemini") or "gemini").lower()
        if self.provider == "claude":
            self.model = config.get("CLAUDE_MODEL", "claude-opus-4-8")
            api_key = config.get("ANTHROPIC_API_KEY")
            if not api_key:
                logger.warning("ANTHROPIC_API_KEY não configurada")
            if anthropic is None:
                logger.error("Pacote 'anthropic' não instalado (pip install anthropic)")
                self.client = None
            else:
                self.client = anthropic.Anthropic(api_key=api_key)
        else:
            self.model = config.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
            api_key = config.get("AI_API_KEY")
            if not api_key:
                logger.warning("AI_API_KEY não configurada")
            if genai is None:
                logger.error("Pacote 'google-genai' não instalado")
                self.client = None
            else:
                self.client = genai.Client(api_key=api_key)
        logger.debug(f"AIService inicializado (provider={self.provider}, modelo={self.model})")

    def _generate(self, prompt: str):
        """Gera texto via provedor configurado. Retorna um objeto com ``.text``.

        Abstrai Gemini vs Claude para que todos os métodos funcionem igual,
        independente do provedor (ver LLM_PROVIDER).
        """
        if self.provider == "claude":
            msg = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(
                getattr(b, "text", "") for b in msg.content
                if getattr(b, "type", None) == "text"
            )
            return SimpleNamespace(text=text)
        # Gemini (padrão)
        return self.client.models.generate_content(model=self.model, contents=prompt)

    def analyze_ticket(
        self,
        email_body: str,
        categories: str = None,
        urgency_criteria: str = None,
    ) -> Dict[str, str]:
        """
        Analisa o corpo de um e-mail e retorna a classificação estruturada.

        Args:
            email_body: Texto do corpo do e-mail a ser analisado.
            categories: Categorias do cliente (lista separada por vírgula).
            urgency_criteria: O que o cliente considera urgente (texto livre).

        Returns:
            Dicionário com ``urgencia``, ``categoria``, ``resumo`` e
            ``resposta_sugerida``. Em caso de falha, retorna um fallback seguro.
        """
        # Limita o corpo para conter custo de tokens em e-mails muito longos.
        email_body = (email_body or "")[:4000]
        cats = categories or "Técnico,Financeiro,Logística,Outros"
        crit = (urgency_criteria or "").strip()
        alta = f", como: {crit}" if crit else ""

        prompt = (
            "Você é um assistente de suporte ao cliente. Leia o e-mail e classifique "
            "pelo CONTEÚDO REAL — nunca por palavras isoladas. Retorne APENAS um JSON "
            "válido com as chaves: 'urgencia' (Alta/Média/Baixa), 'categoria' (escolha "
            f"exatamente uma entre: {cats}), 'resumo' (uma frase objetiva do que o "
            "e-mail realmente trata) e 'resposta_sugerida'.\n\n"
            "Regras de urgência:\n"
            "- E-mails de marketing, promoção, newsletter, cupom, propaganda, "
            "confirmação ou notificação automática NÃO são urgentes (urgencia='Baixa') "
            "e normalmente não exigem ação.\n"
            f"- Só use urgencia='Alta' para um problema real e grave do cliente{alta}.\n"
            "- NÃO invente problemas que não estão escritos no e-mail (ex.: jamais "
            "trate uma oferta de desconto/cupom como cobrança, reclamação ou fraude).\n\n"
            "A 'resposta_sugerida' deve ser em português, amigável, profissional e "
            "objetiva, pronta para enviar; se o e-mail for apenas marketing/automático, "
            "responda algo curto e cortês. Não use placeholders entre colchetes.\n\n"
            f"E-mail:\n{email_body}"
        )

        try:
            response = self._generate(prompt)
            result = json.loads(self._clean_json(response.text))
            logger.debug(f"Análise concluída: urgência={result.get('urgencia')}")
            return result
        except json.JSONDecodeError as e:
            logger.warning(f"JSON inválido da IA, usando fallback: {e}")
            return self._default_response()
        except Exception as e:
            logger.warning(f"Erro na análise IA, usando fallback: {e}")
            return self._default_response()

    def rewrite_response(self, original: str, instruction: str) -> str:
        """
        Reescreve uma resposta seguindo uma instrução do operador.

        Args:
            original: Texto base (ex.: resposta sugerida atual).
            instruction: Como ajustar (ex.: "mais formal", "peça desculpas").

        Returns:
            Novo texto da resposta. Em caso de falha, retorna o original.
        """
        prompt = (
            "Reescreva a resposta de suporte ao cliente abaixo seguindo a "
            f"instrução: '{instruction}'. Mantenha tom profissional e cordial. "
            "Retorne APENAS o texto final, sem comentários.\n\n"
            f"Resposta original:\n{original}"
        )
        try:
            response = self._generate(prompt)
            text = (response.text or "").strip()
            return text or original
        except Exception as e:
            logger.warning(f"Falha ao reescrever resposta: {e}")
            return original

    def summarize_urgent(self, tickets: List[Dict[str, str]]) -> str:
        """
        Gera um resumo consolidado de tickets urgentes.

        Pensado para o envio futuro ao WhatsApp do responsável.

        Args:
            tickets: Lista de dicionários com ``sender``, ``subject``, ``resumo``.

        Returns:
            Texto curto em português, pronto para mensageria.
        """
        if not tickets:
            return "Nenhum e-mail urgente no momento. ✅"

        linhas = "\n".join(
            f"- {t.get('sender', '?')}: {t.get('subject', '(sem assunto)')}"
            for t in tickets
        )
        prompt = (
            "Resuma em até 5 linhas, em português, de forma objetiva e amigável, "
            "os seguintes e-mails urgentes de suporte para enviar ao responsável "
            f"via WhatsApp:\n{linhas}"
        )
        try:
            response = self._generate(prompt)
            text = (response.text or "").strip()
            return text or self._fallback_urgent_summary(tickets)
        except Exception as e:
            logger.warning(f"Falha ao resumir urgentes: {e}")
            return self._fallback_urgent_summary(tickets)

    def qualify_lead(
        self,
        text: str,
        context: str = "",
        categories: str = None,
    ) -> Dict[str, object]:
        """Qualifica um lead a partir da mensagem inicial (para o Floatech CRM).

        Args:
            text: Mensagem/conteúdo do lead.
            context: Contexto extra (ex.: histórico, origem).
            categories: Categorias possíveis (lista separada por vírgula).

        Returns:
            Dict com ``ai_score`` (0..1), ``stage_sugerido``, ``ai_summary``,
            ``categoria`` e ``urgencia``. Fallback seguro em caso de erro.
        """
        cats = categories or "Orçamento,Dúvida,Suporte,Reclamação,Outros"
        material = (f"{context}\n\n{text}" if context else text or "")[:4000]
        prompt = (
            "Você qualifica leads de vendas pelo CONTEÚDO da mensagem. Retorne "
            "APENAS um JSON válido com as chaves: 'ai_score' (número de 0 a 1 "
            "indicando o quão quente/pronto-para-comprar é o lead), 'stage_sugerido' "
            "(exatamente um entre: novo, contatado, proposta), 'ai_summary' (uma "
            f"frase objetiva da intenção), 'categoria' (uma entre: {cats}) e "
            "'urgencia' (Alta/Média/Baixa).\n\n"
            "Regras: lead que pede preço/orçamento/quer comprar = score alto e "
            "stage 'proposta'. Apenas dúvida genérica = score médio, 'novo'. "
            "Spam/sem intenção comercial = score baixo.\n\n"
            f"Mensagem do lead:\n{material}"
        )
        try:
            response = self._generate(prompt)
            result = json.loads(self._clean_json(response.text))
            # Normaliza ai_score para float em [0, 1].
            try:
                result["ai_score"] = max(0.0, min(1.0, float(result.get("ai_score", 0.5))))
            except (TypeError, ValueError):
                result["ai_score"] = 0.5
            return result
        except Exception as e:
            logger.warning(f"Falha ao qualificar lead, usando fallback: {e}")
            return {
                "ai_score": 0.5,
                "stage_sugerido": "novo",
                "ai_summary": "Qualificação pendente",
                "categoria": "Outros",
                "urgencia": "Média",
            }

    def generate_content(
        self,
        kind: str,
        brief: str,
        tone: str = "",
        channel: str = "instagram",
    ) -> Dict[str, object]:
        """Gera conteúdo de marketing (post, anúncio, legenda, resposta).

        Args:
            kind: 'post' | 'ad' | 'caption' | 'reply'.
            brief: Do que se trata / objetivo.
            tone: Tom desejado (ex.: 'descontraído', 'profissional').
            channel: 'instagram' | 'whatsapp' | etc.

        Returns:
            Dict com ``content`` (texto principal) e ``variations`` (lista).
        """
        tipos = {
            "post": "um post para rede social",
            "ad": "um texto de anúncio pago persuasivo",
            "caption": "uma legenda curta e envolvente",
            "reply": "uma resposta cordial para um cliente",
        }
        descricao = tipos.get(kind, "um texto de marketing")
        tom = f" Tom: {tone}." if tone else ""
        prompt = (
            f"Você é redator de marketing da Floatech. Escreva {descricao} para "
            f"{channel}, em português do Brasil.{tom} Gere 3 variações.\n\n"
            "Retorne APENAS um JSON válido com as chaves: 'content' (a melhor "
            "variação, pronta para publicar — pode incluir emojis e hashtags se "
            "fizer sentido para o canal) e 'variations' (array com as 3 opções).\n\n"
            f"Briefing:\n{brief}"
        )
        try:
            response = self._generate(prompt)
            result = json.loads(self._clean_json(response.text))
            if "content" not in result:
                raise ValueError("resposta sem 'content'")
            result.setdefault("variations", [result["content"]])
            return result
        except Exception as e:
            logger.warning(f"Falha ao gerar conteúdo: {e}")
            return {"content": "", "variations": []}

    def analyze_funnel(self, pipeline: Dict[str, int], highlights: List[Dict] = None) -> Dict[str, object]:
        """Analisa o funil de vendas e direciona as próximas decisões.

        É o "copiloto" do CRM: o Gemini lê o estado do pipeline (e alguns leads
        de destaque) e devolve um diagnóstico + ações priorizadas, em vez de
        regras fixas.

        Args:
            pipeline: contagem de deals por stage (novo/contatado/proposta/...).
            highlights: lista opcional de leads quentes [{name, stage, ai_score, ai_summary}].

        Returns:
            Dict com ``diagnostico`` (str), ``foco`` (str) e ``acoes`` (lista de str).
        """
        highlights = highlights or []
        linhas = "\n".join(
            f"- {h.get('name','?')} [{h.get('stage','?')}] score={h.get('ai_score')}: {h.get('ai_summary','')}"
            for h in highlights[:15]
        ) or "(sem leads de destaque)"
        prompt = (
            "Você é o copiloto de vendas da Floatech. Analise o funil abaixo e "
            "direcione as decisões — seja específico e acionável, foque no que mais "
            "move o resultado. Responda no nível de um head de vendas, em português.\n\n"
            f"Contagem por estágio (novo→contatado→proposta→fechado→perdido):\n{json.dumps(pipeline, ensure_ascii=False)}\n\n"
            f"Leads de destaque:\n{linhas}\n\n"
            "Retorne APENAS um JSON válido com as chaves: 'diagnostico' (1-2 frases "
            "sobre a saúde do funil e gargalos), 'foco' (a UMA coisa mais importante "
            "para fazer agora) e 'acoes' (array de 3 a 5 ações concretas e priorizadas, "
            "citando leads/estágios quando fizer sentido)."
        )
        try:
            response = self._generate(prompt)
            result = json.loads(self._clean_json(response.text))
            result.setdefault("diagnostico", "")
            result.setdefault("foco", "")
            if not isinstance(result.get("acoes"), list):
                result["acoes"] = []
            return result
        except Exception as e:
            logger.warning(f"Falha ao analisar funil: {e}")
            return {"diagnostico": "Análise indisponível no momento.", "foco": "", "acoes": []}

    def analyze_conversions(self, metrics: Dict) -> Dict[str, object]:
        """Diz o que converte, o que não converte e quais decisões tomar.

        Recebe métricas já agregadas (conversão por origem, por faixa de score,
        funil, evolução) e o Gemini traduz em leitura de negócio acionável.

        Returns:
            Dict com ``converte`` (lista), ``nao_converte`` (lista),
            ``decisoes`` (lista priorizada) e ``resumo`` (1-2 frases).
        """
        prompt = (
            "Você é analista de growth da Floatech. Com base nas métricas do funil/"
            "marketing abaixo, diga objetivamente O QUE CONVERTE e O QUE NÃO CONVERTE, "
            "e quais decisões tomar para melhorar o resultado. Cite origens, faixas de "
            "score e números quando relevante. Responda em português.\n\n"
            f"Métricas (JSON):\n{json.dumps(metrics, ensure_ascii=False)}\n\n"
            "Retorne APENAS um JSON válido com as chaves: 'resumo' (1-2 frases), "
            "'converte' (array de pontos do que está convertendo bem), 'nao_converte' "
            "(array do que está desperdiçando esforço/verba) e 'decisoes' (array de 3 a "
            "5 ações priorizadas, ex.: realocar verba, pausar origem, focar faixa de score)."
        )
        try:
            response = self._generate(prompt)
            result = json.loads(self._clean_json(response.text))
            for k in ("converte", "nao_converte", "decisoes"):
                if not isinstance(result.get(k), list):
                    result[k] = []
            result.setdefault("resumo", "")
            return result
        except Exception as e:
            logger.warning(f"Falha na análise de conversão: {e}")
            return {"resumo": "Análise indisponível.", "converte": [], "nao_converte": [], "decisoes": []}

    # Persona usada nas features de estratégia (eleva o nível das respostas).
    _SENIOR_PERSONA = (
        "Você é o(a) Social Media Manager SÊNIOR da Floatech, com mais de 10 anos "
        "gerindo mídia orgânica e paga (Meta/Instagram/Google) para negócios que "
        "precisam vender. Pense como quem é cobrado por RESULTADO: priorize o que "
        "move receita, seja específico (datas, horários, formatos, verba), nada de "
        "generalidades. Português do Brasil, tom de calm confidence."
    )

    def compare_competitors(self, our_summary: Dict, competitor_ads: list) -> Dict[str, object]:
        """Lê os MELHORES anúncios de concorrentes, extrai a config vencedora e diz o que fazer.

        Returns:
            Dict com ``melhores_anuncios`` (lista {page, por_que_funciona}),
            ``config_vencedora`` (dict objetivo/formato/gancho/cta/frequencia),
            ``replicar`` (lista) e ``evitar`` (lista).
        """
        ads_txt = "\n".join(
            f"- {a.get('page_name','?')} | roda há ~{a.get('days_running','?')} dias | "
            f"plataformas: {a.get('platforms','?')} | texto: {(a.get('ad_creative_body') or '')[:200]}"
            for a in (competitor_ads or [])[:20]
        ) or "(sem anúncios coletados — analise pela reputação/posicionamento do termo)"
        prompt = (
            f"{self._SENIOR_PERSONA}\n\n"
            "Os anúncios abaixo são de concorrentes (quanto MAIS dias rodando, mais "
            "provável que estejam convertendo — são os 'melhores'). Faça engenharia "
            "reversa da estratégia deles e diga como a Floatech deve agir.\n\n"
            f"Nossa situação (JSON):\n{json.dumps(our_summary, ensure_ascii=False)}\n\n"
            f"Anúncios de concorrentes (ordenados do que roda há mais tempo):\n{ads_txt}\n\n"
            "Retorne APENAS um JSON válido com as chaves: 'melhores_anuncios' (array de "
            "{page, por_que_funciona}); 'config_vencedora' (objeto com objetivo, formato, "
            "gancho, cta, frequencia — o padrão que se repete nos que performam); "
            "'replicar' (array de ações concretas p/ a Floatech) e 'evitar' (array de erros a não cometer)."
        )
        try:
            response = self._generate(prompt)
            result = json.loads(self._clean_json(response.text))
            for k in ("melhores_anuncios", "replicar", "evitar"):
                if not isinstance(result.get(k), list):
                    result[k] = []
            if not isinstance(result.get("config_vencedora"), dict):
                result["config_vencedora"] = {}
            return result
        except Exception as e:
            logger.warning(f"Falha ao comparar concorrentes: {e}")
            return {"melhores_anuncios": [], "config_vencedora": {}, "replicar": [], "evitar": []}

    def best_times(self, platform: str, niche: str = "", context: str = "") -> Dict[str, object]:
        """Melhores horários para postar (recomendação de social media sênior).

        Returns:
            Dict com ``horarios`` (lista {dia, horarios:[...], motivo}) e
            ``proximo`` (sugestão objetiva do próximo melhor slot, ex.: "ter 19:00").
        """
        ctx = f" Contexto: {niche or context}." if (niche or context) else ""
        prompt = (
            f"{self._SENIOR_PERSONA}\n\n"
            f"Recomende os melhores horários para postar no {platform}.{ctx} "
            "Considere comportamento típico do público brasileiro por dia da semana.\n\n"
            "Retorne APENAS um JSON válido com: 'horarios' (array de 3 a 5 {dia, "
            "horarios (array de 'HH:MM'), motivo curto}) e 'proximo' (string com o "
            "melhor próximo slot no formato 'dia HH:MM', ex.: 'terça 19:00')."
        )
        try:
            response = self._generate(prompt)
            result = json.loads(self._clean_json(response.text))
            if not isinstance(result.get("horarios"), list):
                result["horarios"] = []
            result.setdefault("proximo", "")
            return result
        except Exception as e:
            logger.warning(f"Falha ao sugerir horários: {e}")
            return {"horarios": [], "proximo": ""}

    def social_plan(self, context: Dict) -> Dict[str, object]:
        """Plano semanal de social media (sênior): calendário + horários + mídia paga.

        Recebe o contexto do negócio (métricas do funil, plataformas conectadas,
        nicho) e devolve um plano de ação concreto para a semana.

        Returns:
            Dict com ``resumo``, ``foco_semana``, ``calendario`` (lista {dia, canal,
            horario, acao}), ``anuncios`` (lista) e ``metricas_para_observar`` (lista).
        """
        prompt = (
            f"{self._SENIOR_PERSONA}\n\n"
            "Monte o PLANO DA SEMANA de social media + mídia paga para a Floatech, "
            "com base no contexto abaixo. Seja concreto: dias, horários, canais, "
            "formatos e onde colocar verba. O negócio precisa andar.\n\n"
            f"Contexto (JSON):\n{json.dumps(context, ensure_ascii=False)}\n\n"
            "Retorne APENAS um JSON válido com: 'resumo' (1-2 frases), 'foco_semana' "
            "(a prioridade #1), 'calendario' (array de {dia, canal, horario, acao} "
            "cobrindo a semana), 'anuncios' (array de recomendações de campanha paga "
            "com público/verba) e 'metricas_para_observar' (array curto)."
        )
        try:
            response = self._generate(prompt)
            result = json.loads(self._clean_json(response.text))
            for k in ("calendario", "anuncios", "metricas_para_observar"):
                if not isinstance(result.get(k), list):
                    result[k] = []
            result.setdefault("resumo", "")
            result.setdefault("foco_semana", "")
            return result
        except Exception as e:
            logger.warning(f"Falha ao montar plano social: {e}")
            return {"resumo": "Plano indisponível.", "foco_semana": "", "calendario": [], "anuncios": [], "metricas_para_observar": []}

    def keyword_research(self, seed: str, context: str = "") -> Dict[str, object]:
        """Pesquisa de palavras-chave para marketing (direcionada pelo Gemini).

        Sem depender de API paga: o Gemini gera ideias de termos agrupadas por
        intenção, com observação de uso, e sugere o público-alvo. Quando houver
        Google Ads Keyword Planner, ele complementa com volume real (futuro).

        Args:
            seed: termo/tema semente (ex.: "automação para clínicas").
            context: contexto do negócio (ex.: cidade, nicho).

        Returns:
            Dict com ``grupos`` (lista de {tema, palavras:[{termo,intencao,observacao}]})
            e ``publico_sugerido`` (str).
        """
        ctx = f"\nContexto do negócio: {context}" if context else ""
        prompt = (
            "Você é estrategista de marketing de performance da Floatech. A partir "
            "do tema semente, gere uma pesquisa de palavras-chave em português do "
            f"Brasil para anúncios e SEO.{ctx}\n\n"
            f"Tema semente: {seed}\n\n"
            "Retorne APENAS um JSON válido com as chaves: 'grupos' (array de 3 a 5 "
            "objetos {tema, palavras}), onde 'palavras' é um array de 4 a 8 objetos "
            "{termo, intencao (informacional|comercial|transacional|navegacional), "
            "observacao (curta, quando/como usar)}; e 'publico_sugerido' (1-2 frases "
            "descrevendo o público ideal para segmentar com essas palavras)."
        )
        try:
            response = self._generate(prompt)
            result = json.loads(self._clean_json(response.text))
            if not isinstance(result.get("grupos"), list):
                result["grupos"] = []
            result.setdefault("publico_sugerido", "")
            return result
        except Exception as e:
            logger.warning(f"Falha na pesquisa de palavras-chave: {e}")
            return {"grupos": [], "publico_sugerido": ""}

    # ── Construtor de Campanha/Funil (workflow de copy enxuto) ──────────
    # Persona de copywriter direto ao ponto (metodologia do Wesley).
    _COPY_PERSONA = (
        "Você é copywriter sênior de resposta direta (estilo dores→oferta→copy). "
        "Escreve em português do Brasil, humano, direto, SEM clichê de marketing "
        "('transforme sua vida', 'método revolucionário', 'solução definitiva') e "
        "SEM parecer robô. Fala a linguagem que o próprio cliente usaria."
    )

    def client_avatar(self, cliente: str, objetivo: str = "", tentativas: str = "", obstaculo: str = "") -> Dict[str, object]:
        """Passo 1 — descobre dores, medos e desejos do cliente (na linguagem dele)."""
        prompt = (
            f"{self._COPY_PERSONA}\n\n"
            f"Meu cliente é: {cliente}.\n"
            f"Ele quer: {objetivo or '(não informado)'}.\n"
            f"Já tentou: {tentativas or '(não informado)'}.\n"
            f"Não conseguiu porque: {obstaculo or '(não informado)'}.\n\n"
            "Liste as maiores dores, medos e desejos dele EM LINGUAGEM QUE ELE MESMO "
            "USARIA (frases reais, nada genérico). Retorne APENAS um JSON válido com "
            "as chaves: 'dores' (array, até 10), 'medos' (array) e 'desejos' (array)."
        )
        return self._json_call(prompt, {"dores": [], "medos": [], "desejos": []})

    def build_offer(self, cliente: str, produto: str, avatar: Dict = None) -> Dict[str, object]:
        """Passo 2 — monta a oferta a partir das dores."""
        ctx = json.dumps(avatar, ensure_ascii=False) if avatar else "(sem avatar)"
        prompt = (
            f"{self._COPY_PERSONA}\n\n"
            f"Produto/serviço: {produto}. Cliente: {cliente}.\n"
            f"Dores/medos/desejos (JSON): {ctx}\n\n"
            "Com base nessas dores, crie uma oferta. Retorne APENAS um JSON válido com: "
            "'promessa' (promessa principal, 1 frase forte e específica), 'incluido' "
            "(array do que está incluído), 'prova' (como provar que funciona) e "
            "'garantia' (uma garantia concreta)."
        )
        return self._json_call(prompt, {"promessa": "", "incluido": [], "prova": "", "garantia": ""})

    def write_copy(self, kind: str, produto: str, cliente: str, oferta: Dict = None, tom: str = "") -> Dict[str, object]:
        """Passo 3 — escreve a copy (gancho→problema→agitação→solução→prova→oferta→CTA)."""
        tipos = {"anuncio": "um anúncio", "email": "um e-mail", "pagina": "uma página de vendas"}
        desc = tipos.get(kind, "uma copy")
        of = json.dumps(oferta, ensure_ascii=False) if oferta else "(sem oferta)"
        prompt = (
            f"{self._COPY_PERSONA}\n\n"
            f"Escreva {desc}. Produto: {produto}. Cliente: {cliente}. "
            f"Tom: {tom or 'direto, humano, sem parecer robô'}.\n"
            f"Oferta (JSON): {of}\n\n"
            "Estrutura: gancho, problema, agitação, solução, prova, oferta e chamada "
            "pra ação. Retorne APENAS um JSON válido com as chaves: 'gancho', 'problema', "
            "'agitacao', 'solucao', 'prova', 'oferta', 'cta' e 'copy_completa' (o texto "
            "final montado, pronto pra publicar)."
        )
        return self._json_call(prompt, {
            "gancho": "", "problema": "", "agitacao": "", "solucao": "",
            "prova": "", "oferta": "", "cta": "", "copy_completa": "",
        })

    def email_sequence(self, resultado: str, objecao: str = "", produto: str = "", cliente: str = "") -> Dict[str, object]:
        """Passo 4 — 3 e-mails: valor → quebra objeção → oferta com urgência real."""
        prompt = (
            f"{self._COPY_PERSONA}\n\n"
            f"Crie 3 e-mails para leads que querem {resultado}. "
            f"Produto: {produto}. Cliente: {cliente}.\n"
            "E-mail 1 entrega valor. E-mail 2 quebra a objeção de "
            f"'{objecao or 'não confio que funciona'}'. E-mail 3 faz a oferta com "
            "urgência REAL (sem falsa escassez).\n\n"
            "Retorne APENAS um JSON válido com a chave 'emails' (array de 3 objetos "
            "{assunto, corpo})."
        )
        return self._json_call(prompt, {"emails": []})

    def hook_variations(self, gancho: str) -> Dict[str, object]:
        """Passo 5 — reescreve o gancho de 5 formas (curiosidade/medo/resultado/história/provocação)."""
        prompt = (
            f"{self._COPY_PERSONA}\n\n"
            f"Reescreva este gancho de 5 formas: com curiosidade, com medo, com "
            f"resultado rápido, com história e com provocação.\n\nGancho: {gancho}\n\n"
            "Retorne APENAS um JSON válido com a chave 'variacoes' (array de 5 objetos "
            "{tipo, texto})."
        )
        return self._json_call(prompt, {"variacoes": []})

    def humanize(self, texto: str) -> Dict[str, object]:
        """Passo final — troca palavras difíceis, remove clichê, deixa humano."""
        prompt = (
            f"{self._COPY_PERSONA}\n\n"
            "Reescreva o texto abaixo: troque palavras difíceis pelas que você usaria "
            "com um amigo, remova QUALQUER frase genérica (ex.: 'transforme sua vida', "
            "'método revolucionário', 'solução definitiva') e deixe natural e humano. "
            "Mantenha o sentido e a estrutura. Retorne APENAS um JSON válido com a "
            f"chave 'texto' (o texto reescrito).\n\nTexto:\n{texto}"
        )
        return self._json_call(prompt, {"texto": texto})

    def copy_thief(self, material: str, produto: str = "", cliente: str = "") -> Dict[str, object]:
        """Copy Thief — engenharia reversa de uma copy/anúncio que funciona.

        Extrai a "fórmula" (gancho, estrutura, ângulo, gatilhos, CTA) e reescreve
        uma versão ORIGINAL adaptada ao produto/cliente — sem copiar literalmente
        e sem clichê. (Inspiração ética: aprende o padrão, não plagia.)

        Returns:
            Dict com ``analise`` (gancho/estrutura/angulo/gatilhos/cta) e
            ``adaptada`` (a copy nova, pronta pra usar).
        """
        prompt = (
            f"{self._COPY_PERSONA}\n\n"
            "Abaixo está uma copy/anúncio de referência que funciona. Faça "
            "engenharia reversa do que a torna eficaz e crie uma versão ORIGINAL "
            "para o nosso caso — NÃO copie frases literalmente, adapte a fórmula.\n\n"
            f"Produto/serviço: {produto or '(não informado)'}. Cliente: {cliente or '(não informado)'}.\n\n"
            f"Copy de referência:\n\"\"\"\n{(material or '')[:4000]}\n\"\"\"\n\n"
            "Retorne APENAS um JSON válido com: 'analise' (objeto com 'gancho', "
            "'estrutura', 'angulo' (ângulo psicológico), 'gatilhos' (array de "
            "gatilhos mentais usados) e 'cta'); e 'adaptada' (a copy nova, original, "
            "humana, pronta pra publicar)."
        )
        return self._json_call(prompt, {
            "analise": {"gancho": "", "estrutura": "", "angulo": "", "gatilhos": [], "cta": ""},
            "adaptada": "",
        })

    def analyze_sentiment(self, texts: List[str], brand: str = "") -> Dict[str, object]:
        """Social listening: analisa o sentimento de um conjunto de menções/mensagens.

        Returns:
            Dict com ``distribuicao`` ({positivo,neutro,negativo}), ``temas`` (lista),
            ``alertas`` (menções negativas/urgentes que pedem ação), ``recomendacoes``
            e ``resumo``.
        """
        amostra = "\n".join(f"- {t}" for t in (texts or [])[:60]) or "(sem menções)"
        ctx = f" sobre a marca/termo '{brand}'" if brand else ""
        prompt = (
            f"Você é analista de social listening da Floatech. Analise o sentimento "
            f"das menções/mensagens abaixo{ctx}.\n\n{amostra}\n\n"
            "Retorne APENAS um JSON válido com: 'distribuicao' (objeto com inteiros "
            "'positivo','neutro','negativo'), 'temas' (array dos assuntos mais citados), "
            "'alertas' (array de menções negativas/urgentes que exigem resposta), "
            "'recomendacoes' (array de ações) e 'resumo' (1-2 frases)."
        )
        res = self._json_call(prompt, {
            "distribuicao": {"positivo": 0, "neutro": 0, "negativo": 0},
            "temas": [], "alertas": [], "recomendacoes": [], "resumo": "",
        })
        if not isinstance(res.get("distribuicao"), dict):
            res["distribuicao"] = {"positivo": 0, "neutro": 0, "negativo": 0}
        return res

    def _json_call(self, prompt: str, fallback: Dict) -> Dict[str, object]:
        """Helper: chama a IA e faz parse de JSON, com fallback seguro."""
        try:
            response = self._generate(prompt)
            result = json.loads(self._clean_json(response.text))
            for k, v in fallback.items():
                if k not in result:
                    result[k] = v
            return result
        except Exception as e:
            logger.warning(f"Falha em chamada de copy: {e}")
            return dict(fallback)

    @staticmethod
    def _clean_json(raw: str) -> str:
        """Remove cercas de markdown (```json) do texto retornado pela IA."""
        return raw.strip().replace("```json", "").replace("```", "").strip()

    @staticmethod
    def _fallback_urgent_summary(tickets: List[Dict[str, str]]) -> str:
        """Resumo simples (sem IA) usado como fallback."""
        header = f"🚨 {len(tickets)} e-mail(s) urgente(s):"
        body = "\n".join(
            f"• {t.get('subject', '(sem assunto)')} — {t.get('sender', '?')}"
            for t in tickets
        )
        return f"{header}\n{body}"

    @staticmethod
    def _default_response() -> Dict[str, str]:
        """Retorna resposta padrão em caso de falha de análise."""
        return {
            "urgencia": "Média",
            "categoria": "Outros",
            "resumo": "Análise pendente",
            "resposta_sugerida": "Olá, recebemos sua mensagem e em breve responderemos.",
        }
