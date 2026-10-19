"""Polyglot database connection factories for MongoDB, Apache Cassandra, and Redis."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import redis
from cassandra.cluster import Cluster, NoHostAvailable, Session
from cassandra.policies import DCAwareRoundRobinPolicy, ExponentialReconnectionPolicy
from pymongo import MongoClient
from pymongo.database import Database

from basketlens.config import Settings, get_settings


def get_mongo_client(
    settings: Settings | None = None,
    **kwargs: Any,
) -> MongoClient[dict[str, Any]]:
    """Create and return a configured MongoClient instance."""
    cfg = settings or get_settings()
    options: dict[str, Any] = {
        "serverSelectionTimeoutMS": 5000,
        "connectTimeoutMS": 5000,
    }
    options.update(kwargs)
    return MongoClient(cfg.effective_mongo_uri, **options)


def get_mongo_db(
    settings: Settings | None = None,
    client: MongoClient[dict[str, Any]] | None = None,
) -> Database[dict[str, Any]]:
    """Return the target MongoDB database instance (defaults to `basketlens`)."""
    cfg = settings or get_settings()
    mongo_client = client or get_mongo_client(settings=cfg)
    return mongo_client[cfg.mongo_db]


def get_cassandra_cluster_and_session(
    settings: Settings | None = None,
    keyspace: str | None = None,
    max_retries: int = 5,
    retry_delay: float = 2.0,
) -> tuple[Cluster, Session]:
    """Connect to the Cassandra cluster with retry/backoff and return (cluster, session)."""
    cfg = settings or get_settings()
    last_error: Exception | None = None
    delay = retry_delay

    for attempt in range(1, max_retries + 1):
        cluster: Cluster | None = None
        try:
            cluster = Cluster(
                contact_points=[cfg.cassandra_host],
                port=cfg.cassandra_port,
                load_balancing_policy=DCAwareRoundRobinPolicy(local_dc="datacenter1"),
                reconnection_policy=ExponentialReconnectionPolicy(1.0, 60.0),
                connect_timeout=10,
            )
            session = cluster.connect(keyspace) if keyspace else cluster.connect()
            session.default_timeout = 30.0
            return cluster, session
        except (NoHostAvailable, OSError, Exception) as exc:
            last_error = exc
            if cluster is not None:
                try:
                    cluster.shutdown()
                except Exception:
                    pass
            if attempt < max_retries:
                time.sleep(delay)
                delay *= 1.5

    raise RuntimeError(
        f"Failed to connect to Cassandra at {cfg.cassandra_host}:{cfg.cassandra_port} "
        f"after {max_retries} attempts: {last_error}"
    ) from last_error


@contextmanager
def cassandra_session_scope(
    settings: Settings | None = None,
    keyspace: str | None = None,
) -> Iterator[Session]:
    """Context manager yielding a Cassandra session and cleanly shutting down the cluster."""
    cluster, session = get_cassandra_cluster_and_session(settings=settings, keyspace=keyspace)
    try:
        yield session
    finally:
        cluster.shutdown()


def get_redis_client(
    settings: Settings | None = None,
    decode_responses: bool = True,
    **kwargs: Any,
) -> redis.Redis:
    """Create and return a configured Redis client instance."""
    cfg = settings or get_settings()
    options: dict[str, Any] = {
        "host": cfg.redis_host,
        "port": cfg.redis_port,
        "db": cfg.redis_db,
        "decode_responses": decode_responses,
        "socket_connect_timeout": 5,
    }
    options.update(kwargs)
    return redis.Redis(**options)


def check_all_connections(settings: Settings | None = None) -> dict[str, bool]:
    """Execute a ping/heartbeat against MongoDB, Cassandra, and Redis.

    Database Interaction:
        ┌───► [MongoDB :27017]   ── admin.command("ping") ─────────► True
        ├───► [Cassandra :9042]  ── SELECT release_version (local) ► True
        └───► [Redis :6379]      ── PING ──────────────────────────► True
    """
    cfg = settings or get_settings()
    status: dict[str, bool] = {
        "mongodb": False,
        "cassandra": False,
        "redis": False,
    }

    mongo_client: MongoClient[dict[str, Any]] | None = None
    try:
        mongo_client = get_mongo_client(settings=cfg)
        ping_result = mongo_client.admin.command("ping")
        status["mongodb"] = bool(ping_result.get("ok") == 1)
    except Exception:
        status["mongodb"] = False
    finally:
        if mongo_client is not None:
            mongo_client.close()

    cluster: Cluster | None = None
    try:
        cluster, session = get_cassandra_cluster_and_session(
            settings=cfg,
            max_retries=3,
            retry_delay=1.0,
        )
        row = session.execute("SELECT release_version FROM system.local").one()
        status["cassandra"] = bool(row is not None and getattr(row, "release_version", None))
    except Exception:
        status["cassandra"] = False
    finally:
        if cluster is not None:
            cluster.shutdown()

    redis_client: redis.Redis | None = None
    try:
        redis_client = get_redis_client(settings=cfg)
        status["redis"] = bool(redis_client.ping())
    except Exception:
        status["redis"] = False
    finally:
        if redis_client is not None:
            redis_client.close()

    return status


__all__ = [
    "cassandra_session_scope",
    "check_all_connections",
    "get_cassandra_cluster_and_session",
    "get_mongo_client",
    "get_mongo_db",
    "get_redis_client",
]

