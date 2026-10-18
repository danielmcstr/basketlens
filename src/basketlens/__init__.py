"""BasketLens — Visão 360º do cliente com MongoDB, Apache Cassandra e Redis."""

from basketlens.config import PROJECT_ROOT, Settings, get_settings

__version__ = "0.1.0"

__all__ = [
    "PROJECT_ROOT",
    "Settings",
    "__version__",
    "get_settings",
]
