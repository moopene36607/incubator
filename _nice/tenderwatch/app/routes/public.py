"""Public routes — landing page + heartbeat.

The marketing site lives in a separate Astro project (faster + SEO-friendly).
This is the bare-minimum landing so the FastAPI service has a 200-returning
root path for uptime monitors.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def landing() -> str:
    return (
        "<!doctype html><html lang=zh-Hant><meta charset=utf-8>"
        "<title>tenderwatch — 政府標案 AI 即時警示</title>"
        "<h1>tenderwatch</h1>"
        "<p>台灣政府電子採購網 AI 個人化標案警示。</p>"
        "<p><a href=/healthz>healthz</a></p>"
    )


@router.get("/healthz")
def healthz() -> JSONResponse:
    return JSONResponse({"ok": True})
