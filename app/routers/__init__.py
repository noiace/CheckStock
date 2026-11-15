from .warehouses import warehouses_router
from .stocks import stocks_router
from .receipts import receipts_router
from .fbs import fbs_router
from .fbo import fbo_router
from .transfers import transfers_router
from .movements import movements_router

__all__ = [
    "warehouses_router",
    "stocks_router",
    "receipts_router",
    "fbs_router",
    "fbo_router",
    "transfers_router",
    "movements_router",
]
