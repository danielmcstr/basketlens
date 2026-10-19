"""Idempotent Apache Cassandra keyspace and query-driven CQL table provisioning."""

from __future__ import annotations

from cassandra.cluster import Session

from basketlens.config import get_settings
from basketlens.connections import get_cassandra_cluster_and_session

CASSANDRA_TABLES: tuple[str, ...] = (
    "transactions_by_household",
    "transactions_by_household_product",
    "sales_by_product_week",
    "causal_promotions_by_store_week",
)


def get_keyspace_ddl(keyspace: str = "basketlens", replication_factor: int = 1) -> str:
    """Return CQL DDL statement for creating the BasketLens keyspace idempotently."""
    return (
        f"CREATE KEYSPACE IF NOT EXISTS {keyspace} "
        f"WITH replication = {{'class': 'SimpleStrategy', 'replication_factor': {replication_factor}}};"
    )


def get_table_ddls(keyspace: str = "basketlens") -> dict[str, str]:
    """Return CQL DDL statements for the 4 query-driven tables in the target keyspace."""
    return {
        "transactions_by_household": f"""
            CREATE TABLE IF NOT EXISTS {keyspace}.transactions_by_household (
                household_key int,
                week_no int,
                day int,
                basket_id bigint,
                product_id int,
                quantity int,
                sales_value decimal,
                store_id int,
                trans_time int,
                retail_disc decimal,
                coupon_disc decimal,
                coupon_match_disc decimal,
                PRIMARY KEY ((household_key), week_no, day, basket_id, product_id)
            ) WITH CLUSTERING ORDER BY (week_no DESC, day DESC, basket_id DESC, product_id ASC);
        """,
        "transactions_by_household_product": f"""
            CREATE TABLE IF NOT EXISTS {keyspace}.transactions_by_household_product (
                household_key int,
                product_id int,
                day int,
                basket_id bigint,
                week_no int,
                quantity int,
                sales_value decimal,
                store_id int,
                retail_disc decimal,
                coupon_disc decimal,
                coupon_match_disc decimal,
                PRIMARY KEY ((household_key, product_id), day, basket_id)
            ) WITH CLUSTERING ORDER BY (day DESC, basket_id DESC);
        """,
        "sales_by_product_week": f"""
            CREATE TABLE IF NOT EXISTS {keyspace}.sales_by_product_week (
                product_id int,
                week_no int,
                total_units bigint,
                total_sales decimal,
                total_baskets bigint,
                PRIMARY KEY ((product_id), week_no)
            ) WITH CLUSTERING ORDER BY (week_no DESC);
        """,
        "causal_promotions_by_store_week": f"""
            CREATE TABLE IF NOT EXISTS {keyspace}.causal_promotions_by_store_week (
                store_id int,
                week_no int,
                product_id int,
                display_type text,
                mailer_page text,
                PRIMARY KEY ((store_id, week_no), product_id)
            ) WITH CLUSTERING ORDER BY (product_id ASC);
        """,
    }


def list_cassandra_tables(session: Session, keyspace: str = "basketlens") -> list[str]:
    """Query `system_schema.tables` and return sorted table names in the given keyspace."""
    rows = session.execute(
        "SELECT table_name FROM system_schema.tables WHERE keyspace_name = %s",
        (keyspace,),
    )
    return sorted(row.table_name for row in rows)


def ensure_cassandra_schema(
    session: Session | None = None,
    keyspace: str | None = None,
    replication_factor: int = 1,
) -> list[str]:
    """Create the `basketlens` keyspace and all 4 query-driven tables idempotently."""
    cfg = get_settings()
    target_keyspace = keyspace or cfg.cassandra_keyspace
    owns_cluster = session is None
    cluster = None

    try:
        if session is None:
            cluster, session = get_cassandra_cluster_and_session(settings=cfg)

        session.execute(
            get_keyspace_ddl(keyspace=target_keyspace, replication_factor=replication_factor)
        )
        session.set_keyspace(target_keyspace)

        for ddl in get_table_ddls(keyspace=target_keyspace).values():
            session.execute(ddl)

        return list_cassandra_tables(session, keyspace=target_keyspace)
    finally:
        if owns_cluster and cluster is not None:
            cluster.shutdown()


__all__ = [
    "CASSANDRA_TABLES",
    "ensure_cassandra_schema",
    "get_keyspace_ddl",
    "get_table_ddls",
    "list_cassandra_tables",
]
