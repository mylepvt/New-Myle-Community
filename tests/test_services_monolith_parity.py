"""Ensure monolith ``services/`` modules are importable and minimally behave (parity smoke)."""

from __future__ import annotations


def test_rule_engine_reexports_pipeline_rules() -> None:
    from app.services import rule_engine

    assert rule_engine.normalize_flow_status("New") == "New Lead"
    assert "Paid" in str(rule_engine.TEAM_ALLOWED_STATUSES)


def test_wallet_ledger_fragment() -> None:
    from app.services import wallet_ledger

    assert "current_owner" in wallet_ledger._POOL_BUYER_CLAIMED
    assert callable(wallet_ledger.sum_pool_spent_for_buyer)


def test_day2_certificate_pdf_bytes() -> None:
    from app.services.day2_certificate_pdf import build_day2_business_certificate_pdf

    pdf = build_day2_business_certificate_pdf("Test User", 3, 10, "2026-01-01")
    assert pdf.startswith(b"%PDF")


def test_scoring_action_points() -> None:
    from app.services import scoring_service

    assert scoring_service.ACTION_POINTS["CONNECTED_CALL"] == 20
    assert "FOLLOWUP_MISSED" in scoring_service.ACTION_POINTS


def test_hierarchy_exports() -> None:
    from app.services import hierarchy_lead_sync

    assert callable(hierarchy_lead_sync.nearest_approved_leader_username)
    assert callable(hierarchy_lead_sync.sync_member_under_parent)
