"""End-to-end verification tests for Phase 4 documentation, notebooks, and rubric deliverables."""

from __future__ import annotations

import json

from basketlens import PROJECT_ROOT


def test_architecture_doc_contains_all_required_sections() -> None:
    """Verify `docs/ARCHITECTURE.md` exists and covers diagrams, modeling, CAP, Neo4j, and K8s."""
    arch_path = PROJECT_ROOT / "docs" / "ARCHITECTURE.md"
    assert arch_path.is_file(), "Missing docs/ARCHITECTURE.md"
    content = arch_path.read_text(encoding="utf-8")

    required_keywords = (
        "Modo A",
        "Modo B",
        "households",
        "Subset Pattern",
        "Extended Reference Pattern",
        "transactions_by_household",
        "transactions_by_household_product",
        "sales_by_product_week",
        "causal_promotions_by_store_week",
        "ALLOW FILTERING",
        "Cache-Aside",
        "TTL",
        "CAP",
        "QUORUM",
        "Neo4j",
        "BOUGHT_WITH",
        "Kubernetes",
        "K8ssandra",
    )
    for kw in required_keywords:
        assert kw in content, f"Missing required architectural topic '{kw}' in docs/ARCHITECTURE.md"


def test_business_answers_doc_contains_empirical_evidence_for_all_questions() -> None:
    """Verify `docs/BUSINESS_ANSWERS.md` covers Questions 1, 2, 3 and Trade Marketing bonus."""
    ans_path = PROJECT_ROOT / "docs" / "BUSINESS_ANSWERS.md"
    assert ans_path.is_file(), "Missing docs/BUSINESS_ANSWERS.md"
    content = ans_path.read_text(encoding="utf-8")

    required_evidence = (
        "208",
        "EXPRESS_IXSCAN",
        "idx_household_key_unique",
        "Campanha 22",
        "51800000050",
        "41531980403",
        "classification_1",
        "classification_3",
        "Age Group1",
        "Age Group4",
        "Level1",
        "Level12",
        "801",
        "72717",
        "862349",
    )
    for token in required_evidence:
        assert token in content, f"Missing empirical evidence '{token}' in docs/BUSINESS_ANSWERS.md"


def test_readme_documents_setup_web_uis_notebooks_and_citation() -> None:
    """Verify `README.md` documents context, 8 CSVs, links to docs, ASCII function diagrams, Web UIs, and citation."""
    readme_path = PROJECT_ROOT / "README.md"
    assert readme_path.is_file(), "Missing README.md"
    content = readme_path.read_text(encoding="utf-8")

    for expected in (
        "docs/assets/arch-polyglot-overview.svg",
        "docs/ARCHITECTURE.md",
        "docs/BUSINESS_ANSWERS.md",
        "causal_data.csv",
        "transaction_data.csv",
        "hh_demographic.csv",
        "check_all_connections()",
        "initialize_all_schemas()",
        "run_full_ingestion(",
        "prepare_replay_baseline(",
        "replay_day(",
        "build_360_view(",
        "get_active_campaigns_for_household(",
        "get_avg_weekly_spend_by_demographic(",
        "get_product_causal_promotion_lift(",
        "docker compose up -d",
        "http://localhost:8081",
        "http://localhost:3000",
        "http://localhost:8082",
        "01_eda_and_data_quality.ipynb",
        "02_full_ingestion_setup.ipynb",
        "03_event_replay_streaming.ipynb",
        "04_polyglot_360_analytics.ipynb",
        "pytest",
        "dunnhumby",
        "https://www.dunnhumby.com/source-files/",
    ):
        assert expected in content, f"Missing '{expected}' in README.md"


def test_standardized_drawio_architecture_svgs_exist_and_are_valid() -> None:
    """Verify all 4 Draw.io architecture SVGs exist in `docs/assets/`, contain mxfile metadata, and are referenced."""
    import xml.etree.ElementTree as ET

    arch_content = (PROJECT_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    svg_names = (
        "arch-polyglot-overview.svg",
        "arch-operational-modes.svg",
        "arch-neo4j-graph.svg",
        "arch-kubernetes-production.svg",
    )
    for svg_name in svg_names:
        svg_path = PROJECT_ROOT / "docs" / "assets" / svg_name
        assert svg_path.is_file(), f"Missing architecture SVG: {svg_name}"
        raw = svg_path.read_text(encoding="utf-8")
        assert "mxfile" in raw, f"Missing Draw.io mxfile metadata in {svg_name}"
        root = ET.fromstring(raw)
        assert root.tag.endswith("svg"), f"Invalid root tag in {svg_name}"
        assert f"assets/{svg_name}" in arch_content, f"{svg_name} not embedded in docs/ARCHITECTURE.md"


def test_python_library_docstrings_and_notebooks_contain_ascii_db_diagrams() -> None:
    """Verify public `basketlens` functions and all 4 notebooks include ASCII database interaction diagrams."""
    from basketlens import check_all_connections, initialize_all_schemas
    from basketlens.ingestion import ingest_redis_state, run_full_ingestion
    from basketlens.queries import (
        benchmark_cache_aside_latency,
        build_360_view,
        get_active_campaigns_for_household,
        get_avg_weekly_spend_by_demographic,
        get_household_product_history,
        get_household_profile_and_recent_history,
        get_product_causal_promotion_lift,
        get_store_weekly_showcase,
    )
    from basketlens.replay import prepare_replay_baseline, replay_day, replay_range, restore_full_historical_state
    from basketlens.schemas.mongo_schema import explain_query

    for fn in (
        check_all_connections,
        initialize_all_schemas,
        explain_query,
        run_full_ingestion,
        ingest_redis_state,
        prepare_replay_baseline,
        replay_day,
        replay_range,
        restore_full_historical_state,
        build_360_view,
        benchmark_cache_aside_latency,
        get_household_profile_and_recent_history,
        get_household_product_history,
        get_active_campaigns_for_household,
        get_avg_weekly_spend_by_demographic,
        get_product_causal_promotion_lift,
        get_store_weekly_showcase,
    ):
        doc = fn.__doc__ or ""
        assert "Database Interaction:" in doc and "──►" in doc, f"Missing ASCII DB diagram in docstring of {fn.__name__}"

    for nb_name in (
        "01_eda_and_data_quality.ipynb",
        "02_full_ingestion_setup.ipynb",
        "03_event_replay_streaming.ipynb",
        "04_polyglot_360_analytics.ipynb",
    ):
        nb_text = (PROJECT_ROOT / "notebooks" / nb_name).read_text(encoding="utf-8")
        assert "──►" in nb_text, f"Missing ASCII database diagram in {nb_name}"


def test_all_four_notebooks_and_reference_pdf_exist_and_are_valid() -> None:
    """Verify the official PDF guide and all 4 executed Jupyter notebooks exist."""
    pdf_path = PROJECT_ROOT / "docs" / "dunnhumby_The-Complete-Journey-User-Guide.pdf"
    assert pdf_path.is_file() and pdf_path.stat().st_size > 100_000

    for nb_name in (
        "01_eda_and_data_quality.ipynb",
        "02_full_ingestion_setup.ipynb",
        "03_event_replay_streaming.ipynb",
        "04_polyglot_360_analytics.ipynb",
    ):
        nb_path = PROJECT_ROOT / "notebooks" / nb_name
        assert nb_path.is_file(), f"Missing notebook {nb_name}"
        nb_json = json.loads(nb_path.read_text(encoding="utf-8"))
        code_cells = [c for c in nb_json.get("cells", []) if c.get("cell_type") == "code"]
        assert len(code_cells) >= 3
        for cell in code_cells:
            assert cell.get("execution_count") is not None, f"Unexecuted cell in {nb_name}"
            assert len(cell.get("outputs", [])) > 0, f"Empty output in {nb_name}"
