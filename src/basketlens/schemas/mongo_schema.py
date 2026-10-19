"""Idempotent MongoDB collection and index provisioning for `households`."""

from __future__ import annotations

from typing import Any

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.collection import Collection
from pymongo.database import Database

from basketlens.connections import get_mongo_client, get_mongo_db

HOUSEHOLDS_COLLECTION = "households"

HOUSEHOLD_INDEX_MODELS: tuple[IndexModel, ...] = (
    IndexModel(
        [("household_key", ASCENDING)],
        name="idx_household_key_unique",
        unique=True,
    ),
    IndexModel(
        [
            ("demographics.classification_1", ASCENDING),
            ("demographics.classification_3", ASCENDING),
        ],
        name="idx_demographics_class1_class3",
    ),
    IndexModel(
        [("behavior_summary.avg_weekly_spend", DESCENDING)],
        name="idx_behavior_avg_weekly_spend_desc",
    ),
)


def ensure_mongo_indexes(db: Database[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Create and verify required indexes on the `households` collection idempotently."""
    owns_client = db is None
    client = None
    try:
        if db is None:
            client = get_mongo_client()
            db = get_mongo_db(client=client)
        collection = db[HOUSEHOLDS_COLLECTION]
        collection.create_indexes(list(HOUSEHOLD_INDEX_MODELS))
        return collection.index_information()
    finally:
        if owns_client and client is not None:
            client.close()


def explain_query(
    collection: Collection[dict[str, Any]],
    filter_doc: dict[str, Any],
    sort_spec: list[tuple[str, int]] | None = None,
) -> dict[str, Any]:
    """Execute `explain('executionStats')` for a query on the given MongoDB collection."""
    command_spec: dict[str, Any] = {
        "find": collection.name,
        "filter": filter_doc,
    }
    if sort_spec:
        command_spec["sort"] = dict(sort_spec)

    return collection.database.command(
        "explain",
        command_spec,
        verbosity="executionStats",
    )


__all__ = [
    "HOUSEHOLDS_COLLECTION",
    "HOUSEHOLD_INDEX_MODELS",
    "ensure_mongo_indexes",
    "explain_query",
]
