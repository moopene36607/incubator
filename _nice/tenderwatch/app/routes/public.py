"""Public marketing + legal routes.

Pages here are reachable WITHOUT login. They power the marketing funnel
(landing → pricing → checkout) and the legally-required documents
(ToS / Privacy / Refund) cited from every footer.

Templates live under app/templates/marketing/ and app/templates/legal/ and
extend marketing_base.html (which has no logged-in nav).
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def landing(request: Request):
    return templates.TemplateResponse(request, "marketing/landing.html", {})


@router.get("/pricing")
def pricing(request: Request):
    return templates.TemplateResponse(request, "marketing/pricing.html", {})


@router.get("/faq")
def faq(request: Request):
    return templates.TemplateResponse(request, "marketing/faq.html", {})


@router.get("/tos")
def tos(request: Request):
    return templates.TemplateResponse(request, "legal/tos.html", {})


@router.get("/privacy")
def privacy(request: Request):
    return templates.TemplateResponse(request, "legal/privacy.html", {})


@router.get("/refund")
def refund(request: Request):
    return templates.TemplateResponse(request, "legal/refund.html", {})


@router.get("/healthz")
def healthz() -> JSONResponse:
    return JSONResponse({"ok": True})
