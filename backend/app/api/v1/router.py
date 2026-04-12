"""
Aggregate all v1 routers here. New domains: add `your_module.router` + `include_router`.
"""

from fastapi import APIRouter

from app.api.v1 import (
    analytics,
    auth,
    certificate,
    enroll,
    execution,
    finance_surfaces,
    follow_ups,
    gate_assistant,
    hello,
    lead_pool,
    leads,
    meta,
    other_pages,
    payments,
    pipeline,
    realtime_ws,
    reports,
    retarget,
    settings_pages,
    system,
    team,
    wallet,
    wallet_enhanced,
    workboard,
)

api_router = APIRouter()
api_router.include_router(meta.router, prefix="/meta", tags=["meta"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(hello.router, prefix="/hello", tags=["hello"])
api_router.include_router(leads.router, prefix="/leads", tags=["leads"])
api_router.include_router(team.router, prefix="/team", tags=["team"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(execution.router, prefix="/execution", tags=["execution"])
api_router.include_router(finance_surfaces.router, prefix="/finance", tags=["finance"])
api_router.include_router(other_pages.router, prefix="/other", tags=["other"])
api_router.include_router(settings_pages.router, prefix="/settings", tags=["settings"])
api_router.include_router(wallet.router, prefix="/wallet", tags=["wallet"])
api_router.include_router(lead_pool.router, prefix="/lead-pool", tags=["lead-pool"])
api_router.include_router(retarget.router, prefix="/retarget", tags=["retarget"])
api_router.include_router(follow_ups.router, prefix="/follow-ups", tags=["follow-ups"])
api_router.include_router(workboard.router, prefix="/workboard", tags=["workboard"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(
    gate_assistant.router, prefix="/gate-assistant", tags=["gate-assistant"]
)
api_router.include_router(realtime_ws.router, tags=["realtime"])
api_router.include_router(enroll.router, prefix="/enroll", tags=["enroll"])
# Public watch route — no /enroll prefix so the URL is /api/v1/watch/{token}
api_router.include_router(enroll.watch_router, tags=["watch"])
api_router.include_router(certificate.router, tags=["certificate"])
api_router.include_router(pipeline.router, prefix="/pipeline", tags=["pipeline"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(wallet_enhanced.router, prefix="/wallet", tags=["wallet-enhanced"])
