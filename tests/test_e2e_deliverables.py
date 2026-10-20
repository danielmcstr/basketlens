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
    """Verify `README.md` documents high-level context, bridges to docs, setup, Web UIs, notebooks, and CONTRIBUTING."""
    readme_path = PROJECT_ROOT / "README.md"
    assert readme_path.is_file(), "Missing README.md"
    content = readme_path.read_text(encoding="utf-8")

    for expected in (
        "docs/ARCHITECTURE.md",
        "docs/BUSINESS_ANSWERS.md",
        "CONTRIBUTING.md",
        "LICENSE",
        "docker compose up -d",
        "http://localhost:8081",
        "http://localhost:3000",
        "http://localhost:8082",
        "check_all_connections()",
        "initialize_all_schemas()",
        "run_full_ingestion()",
        "prepare_replay_baseline()",
        "replay_day(654)",
        "build_360_view()",
        "get_household_profile_and_recent_history()",
        "get_active_campaigns_for_household()",
        "get_avg_weekly_spend_by_demographic()",
        "get_product_causal_promotion_lift()",
        "01_eda_and_data_quality.ipynb",
        "02_full_ingestion_setup.ipynb",
        "03_event_replay_streaming.ipynb",
        "04_polyglot_360_analytics.ipynb",
        "dunnhumby",
    ):
        assert expected in content, f"Missing '{expected}' in README.md"


def test_governance_and_license_files_exist_and_match_spec() -> None:
    """Verify `CONTRIBUTING.md` and `LICENSE` exist, and `pyproject.toml` declares non-commercial educational license."""
    contrib_path = PROJECT_ROOT / "CONTRIBUTING.md"
    assert contrib_path.is_file(), "Missing CONTRIBUTING.md"
    contrib_content = contrib_path.read_text(encoding="utf-8")
    for token in (
        ".venv/bin/pytest -v",
        "src/basketlens/",
        "Zero Full-Dataset In-Memory",
        "ALLOW FILTERING",
        "EXPRESS_IXSCAN",
        "TTL",
    ):
        assert token in contrib_content, f"Missing '{token}' in CONTRIBUTING.md"

    license_path = PROJECT_ROOT / "LICENSE"
    assert license_path.is_file(), "Missing LICENSE"
    license_content = license_path.read_text(encoding="utf-8")
    for token in (
        "TERMOS DE USO E LICENÇA DE USO NÃO-COMERCIAL",
        "https://www.dunnhumby.com/source-files/",
        "EXPRESSAMENTE PROIBIDA",
    ):
        assert token in license_content, f"Missing '{token}' in LICENSE"

    pyproject_content = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "Academic and Educational Use Only (Non-Commercial)" in pyproject_content
    assert '"MIT"' not in pyproject_content

    arch_content = (PROJECT_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    assert "```mermaid" not in arch_content, "Redundant mermaid block should be removed from docs/ARCHITECTURE.md"


def test_standardized_drawio_architecture_svgs_exist_and_are_valid() -> None:
    """Verify all 4 Draw.io architecture diagrams exist as .drawio.svg, contain mxCells, and are referenced."""
    import xml.etree.ElementTree as ET

    arch_content = (PROJECT_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    diagram_stems = (
        "arch-polyglot-overview",
        "arch-operational-modes",
        "arch-neo4j-graph",
        "arch-kubernetes-production",
    )
    for stem in diagram_stems:
        drawio_svg = PROJECT_ROOT / "docs" / "assets" / f"{stem}.drawio.svg"
        assert drawio_svg.is_file(), f"Missing Draw.io SVG: {drawio_svg.name}"
        raw = drawio_svg.read_text(encoding="utf-8")
        assert "mxfile" in raw, f"Missing Draw.io mxfile metadata in {drawio_svg.name}"

        root = ET.fromstring(raw)
        assert root.tag.endswith("svg"), f"Invalid root tag in {drawio_svg.name}"
        assert f"assets/{stem}.drawio.svg" in arch_content, f"{stem}.drawio.svg not embedded in docs/ARCHITECTURE.md"

        mx_content = root.attrib.get("content", "")
        mx_root = ET.fromstring(mx_content)
        vertices = mx_root.findall('.//mxCell[@vertex="1"]')
        edges = mx_root.findall('.//mxCell[@edge="1"]')
        assert len(vertices) >= 10, f"Insufficient Draw.io vertices in {stem}.drawio.svg"
        assert len(edges) >= 5, f"Insufficient Draw.io edges in {stem}.drawio.svg"


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
