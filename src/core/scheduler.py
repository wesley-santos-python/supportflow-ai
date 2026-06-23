"""
Agendador de tarefas em background (APScheduler).

Como o SaaS é multi-cliente, as tarefas iteram sobre os clientes que já têm
e-mail configurado, executando o fluxo no contexto de cada um.

Tarefas periódicas:
    - Sincronização de e-mails (intervalo configurável, padrão 2 minutos)
    - Envio de respostas agendadas vencidas
    - Disparo de lembretes vencidos
    - Resumo de e-mails urgentes (preparado para WhatsApp)

O agendador é iniciado junto com a aplicação web e encerrado no shutdown.
"""
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

from src import config
from src.core.automation import SupportController
from src.core.notifications import WhatsAppNotifier
from src.data import db
from src.utils.logger import get_logger

logger = get_logger(__name__)

_scheduler: Optional[BackgroundScheduler] = None


def sync_emails_job() -> None:
    """Tarefa: sincroniza e-mails novos de cada cliente configurado."""
    for user_id in db.users_with_email_configured():
        try:
            processed = SupportController(user_id).run_sync()
            if processed:
                logger.info(f"[scheduler] user={user_id}: {processed} tickets")
        except Exception as e:  # pragma: no cover - protege o loop do scheduler
            logger.error(f"[scheduler] erro na sincronização (user={user_id}): {e}")


def scheduled_replies_job() -> None:
    """Tarefa: envia respostas agendadas vencidas de cada cliente."""
    for user_id in db.users_with_email_configured():
        try:
            sent = SupportController(user_id).process_scheduled_replies()
            if sent:
                logger.info(f"[scheduler] user={user_id}: {sent} respostas enviadas")
        except Exception as e:  # pragma: no cover
            logger.error(f"[scheduler] erro nas respostas agendadas (user={user_id}): {e}")


def reminders_job() -> None:
    """Tarefa: dispara lembretes vencidos (registra e marca como notificado)."""
    try:
        for reminder in db.due_reminders(datetime.now()):
            logger.info(f"🔔 Lembrete (user={reminder.user_id}): {reminder.title}")
            db.mark_reminder_notified(reminder.id)
    except Exception as e:  # pragma: no cover
        logger.error(f"[scheduler] erro nos lembretes: {e}")


def urgent_summary_job() -> None:
    """Tarefa: gera (e, se habilitado, envia) o resumo de urgentes por cliente."""
    for user_id in db.users_with_email_configured():
        try:
            WhatsAppNotifier(user_id).send_urgent_summary()
        except Exception as e:  # pragma: no cover
            logger.error(f"[scheduler] erro no resumo urgente (user={user_id}): {e}")


def start_scheduler() -> BackgroundScheduler:
    """
    Inicia o agendador com as tarefas configuradas.

    Idempotente: chamadas repetidas retornam a instância já em execução.
    """
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler

    interval = config.get_int("SYNC_INTERVAL_MINUTES", 2)
    scheduler = BackgroundScheduler(daemon=True)

    scheduler.add_job(
        sync_emails_job, "interval", minutes=interval, id="sync_emails",
        max_instances=1, coalesce=True, replace_existing=True,
    )
    scheduler.add_job(
        scheduled_replies_job, "interval", minutes=1, id="scheduled_replies",
        max_instances=1, coalesce=True, replace_existing=True,
    )
    scheduler.add_job(
        reminders_job, "interval", minutes=1, id="reminders",
        max_instances=1, coalesce=True, replace_existing=True,
    )
    scheduler.add_job(
        urgent_summary_job, "interval", minutes=max(interval * 5, 10),
        id="urgent_summary", max_instances=1, coalesce=True, replace_existing=True,
    )

    scheduler.start()
    _scheduler = scheduler
    logger.info(f"Scheduler iniciado (sincronização a cada {interval} min)")
    return scheduler


def shutdown_scheduler() -> None:
    """Encerra o agendador, se estiver em execução."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler encerrado")
    _scheduler = None
