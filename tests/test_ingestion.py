"""Integration tests for Phase 2 Polars out-of-core ingestion and EDA/ingestion notebooks."""

from __future__ import annotations

import json

from basketlens import PROJECT_ROOT
from basketlens.connections import (
    cassandra_session_scope,
    get_mongo_client,
    get_mongo_db,
    get_redis_client,
)
from basketlens.ingestion import ingest_redis_state
from basketlens.schemas.mongo_schema import HOUSEHOLDS_COLLECTION


def test_out_of_core_polars_rule_enforced_in_loaders() -> None:
    """Verify ingestion loaders use scan_csv / read_csv_batched and never pl.read_csv(."""
    for rel_path in (
        "src/basketlens/ingestion/mongo_loader.py",
        "src/basketlens/ingestion/cassandra_loader.py",
        "src/basketlens/ingestion/redis_loader.py",
    ):
        source = (PROJECT_ROOT / rel_path).read_text(encoding="utf-8")
        assert "pl.read_csv(" not in source, f"Forbidden eager pl.read_csv found in {rel_path}"
        assert "pl.scan_csv(" in source


def test_mongodb_households_2500_documents_and_john_smith_208() -> None:
    """Verify 2,500 documents (801 with demographics, 1,699 without) and household #208."""
    client = get_mongo_client()
    try:
        db = get_mongo_db(client=client)
        coll = db[HOUSEHOLDS_COLLECTION]

        assert coll.count_documents({}) == 2500
        assert coll.count_documents({"demographics": {"$exists": True}}) == 801
        assert coll.count_documents({"demographics": {"$exists": False}}) == 1699

        doc208 = coll.find_one({"household_key": 208})
        assert doc208 is not None
        assert "demographics" in doc208
        for field in (
            "classification_1",
            "classification_2",
            "classification_3",
            "homeowner_desc",
            "classification_4",
            "classification_5",
            "kid_category_desc",
        ):
            assert field in doc208["demographics"]

        summary = doc208["behavior_summary"]
        for field in (
            "total_spend",
            "total_baskets",
            "avg_basket_value",
            "avg_weekly_spend",
            "first_day",
            "last_day",
            "top_departments",
            "top_commodities",
            "updated_at",
        ):
            assert field in summary

        assert summary["total_spend"] > 0
        assert summary["total_baskets"] == 140
        assert doc208["campaigns_received"] == [8, 13, 17, 18, 22, 26, 29, 30]

        recent_baskets = doc208["recent_baskets"]
        assert 1 <= len(recent_baskets) <= 5
        last_basket = recent_baskets[-1]
        assert last_basket["day"] == 701
        assert len(last_basket["items"]) > 0
        assert "department" in last_basket["items"][0]
        assert "commodity_desc" in last_basket["items"][0]
    finally:
        client.close()


def test_cassandra_four_tables_populated_and_ordered_for_208() -> None:
    """Verify Cassandra tables return ordered recent transactions for #208 without ALLOW FILTERING."""
    with cassandra_session_scope(keyspace="basketlens") as session:
        rows = list(
            session.execute(
                "SELECT week_no, day, basket_id, product_id, quantity, sales_value "
                "FROM transactions_by_household WHERE household_key = 208 LIMIT 10"
            )
        )
        assert len(rows) == 10
        pairs = [(r.week_no, r.day) for r in rows]
        assert pairs == sorted(pairs, reverse=True)
        assert rows[0].day == 701

        prod_rows = list(
            session.execute(
                "SELECT day, basket_id, quantity, sales_value "
                "FROM transactions_by_household_product "
                "WHERE household_key = 208 AND product_id = 1017772"
            )
        )
        assert len(prod_rows) >= 1

        sales_row = session.execute(
            "SELECT product_id, week_no, total_units, total_sales, total_baskets "
            "FROM sales_by_product_week WHERE product_id = 72717"
        ).one()
        assert sales_row is not None
        assert sales_row.week_no == 40

        causal_row = session.execute(
            "SELECT store_id, week_no, product_id, display_type, mailer_page "
            "FROM causal_promotions_by_store_week LIMIT 1"
        ).one()
        assert causal_row is not None
        assert isinstance(causal_row.display_type, str)
        assert isinstance(causal_row.mailer_page, str)


def test_redis_active_campaigns_and_ttl_for_reference_day_650() -> None:
    """Verify Campaign 22 is active with TTL <= 30s on Day 650 and Campaign 18 is excluded."""
    res = ingest_redis_state(reference_day=650, seconds_per_day=5)
    assert 22 in res["active_campaigns"]
    assert 18 not in res["active_campaigns"]

    redis_client = get_redis_client()
    try:
        ttl_22 = redis_client.ttl("campanha:22")
        assert 0 < ttl_22 <= 30
        assert redis_client.exists("campanha:18") == 0
        assert "22" in redis_client.smembers("household:208:campaigns")
        assert "51800000050" in redis_client.smembers("household:208:coupons")
        assert redis_client.hget("cupom:51800000050", "campaign") == "22"
    finally:
        redis_client.close()


def test_notebooks_01_and_02_executed_with_outputs() -> None:
    """Verify notebooks 01 and 02 exist and contain executed code cell outputs."""
    for nb_name in ("01_eda_and_data_quality.ipynb", "02_full_ingestion_setup.ipynb"):
        nb_path = PROJECT_ROOT / "notebooks" / nb_name
        assert nb_path.is_file(), f"Missing notebook {nb_path}"
        nb_data = json.loads(nb_path.read_text(encoding="utf-8"))
        code_cells = [c for c in nb_data.get("cells", []) if c.get("cell_type") == "code"]
        assert len(code_cells) >= 3
        for cell in code_cells:
            assert cell.get("execution_count") is not None
            assert len(cell.get("outputs", [])) > 0
