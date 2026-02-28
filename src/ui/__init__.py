"""
Módulo de interface do SupportFlow AI.

Contém o dashboard principal e componentes reutilizáveis da UI.
"""
from .dashboard import main_dashboard
from .components import urgency_badge, filter_chips

__all__ = [
    'main_dashboard', 
    'urgency_badge',
    'filter_chips'
]
