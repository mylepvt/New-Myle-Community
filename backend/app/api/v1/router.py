"""
Aggregate all v1 routers here. New domains: add `your_module.router` + `include_router`.
"""

from fastapi import APIRouter

from app.api.v1 import auth, hello, leads, meta

api_router = APIRouter()
api_router.include_router(meta.router, prefix="/meta", tags=["meta"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(hello.router, prefix="/hello", tags=["hello"])
api_router.include_router(leads.router, prefix="/leads", tags=["leads"])
