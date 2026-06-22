"""
Agendador de tarefas em background (APScheduler).

Tarefas periódicas:
    - Sincronização de e-mails (intervalo configurável, padrão 2 minutos)
    - Envio de respostas agendadas que venceram
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
    """Tarefa: sincroniza e-mails novos via IA."""
    try:
        processed = SupportController().run_sync()
        if processed:
            logger.info(f"[scheduler] {processed} tickets sincronizados")
    except Exception as e:  # pragma: no cover - proteção do loop do scheduler
        logger.error(f"[scheduler] erro na sincronização: {e}")


def scheduled_replies_job() -> None:
    """Tarefa: envia respostas agendadas que já venceram."""
    try:
        sent = SupportController().process_scheduled_replies()
        if sent:
            logger.info(f"[scheduler] {sent} respostas agendadas enviadas")
    except Exception as e:  # pragma: no cover
        logger.error(f"[scheduler] erro nas respostas agendadas: {e}")


def reminders_job() -> None:
    """Tarefa: dispara lembretes vencidos (registra e marca como notificado)."""
    try:
        for reminder in db.due_reminders(datetime.now()):
            logger.info(f"🔔 Lembrete: {reminder.title}")
            db.mark_reminder_notified(reminder.id)
    except Exception as e:  # pragma: no cover
        logger.error(f"[scheduler] erro nos lembretes: {e}")


def urgent_summary_job() -> None:
    """Tarefa: gera (e, se habilitado, envia) o resumo de e-mails urgentes."""
    try:
        WhatsAppNotifier().send_urgent_summary()
    except Exception as e:  # pragma: no cover
        logger.error(f"[scheduler] erro no resumo urgente: {e}")


def start_scheduler() -> BackgroundScheduler:
    """
    Inicia o agendador com as tarefas configuradas.

    Idempotente: chamadas repetidas retornam a instância já em execução.

    Returns:
        A instância do :class:`BackgroundScheduler` em execução.
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
