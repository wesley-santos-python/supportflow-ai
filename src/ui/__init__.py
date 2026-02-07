"""
Módulo de interface do SupportFlow AI.

Contém o dashboard principal e componentes reutilizáveis da UI.
"""
from .dashboard import main_dashboard
from .components import (
    ticket_card, 
    loading_indicator, 
    urgency_badge, 
    detail_modal, 
    filter_chips
)

__all__ = [
    'main_dashboard', 
    'ticket_card', 
    'loading_indicator', 
    'urgency_badge',
    'detail_modal',
    'filter_chips'
]
