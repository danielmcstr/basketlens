"""BasketLens — Visão 360º do cliente com MongoDB, Apache Cassandra e Redis."""

from basketlens.config import PROJECT_ROOT, Settings, get_settings
from basketlens.connections import check_all_connections
from basketlens.schemas import initialize_all_schemas

__version__ = "0.1.0"

__all__ = [
    "PROJECT_ROOT",
    "Settings",
    "__version__",
    "check_all_connections",
    "get_settings",
    "initialize_all_schemas",
]
