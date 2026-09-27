from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.auth.security import require_authenticated_user, is_admin
from app.services.report_service import report_service
from app.templates_env import templates

router = APIRouter(tags=["Pages"])


def _redirect_login():
    return RedirectResponse(url="/login", status_code=302)


@router.get("/", response_class=HTMLResponse)
async def home_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    user = require_authenticated_user(request)
    await report_service.sync_catalog_if_empty(db)
    reports = await report_service.get_all_reports(db, user_upn=user.get("upn"))
    favorites = await report_service.get_user_favorites(db, user.get("upn"))
    departments = await report_service.get_departments_list(db)
    featured_reports = [r for r in reports if r.get("is_featured")]

    return templates.TemplateResponse(
        "pages/dashboard.html",
        {
            "request": request,
            "user": user,
            "reports": reports,
            "featured_reports": featured_reports,
            "favorites": favorites,
            "departments": departments,
            "active_page": "dashboard",
            "is_admin": is_admin(user),
        }
    )


@router.get("/catalog", response_class=HTMLResponse)
async def catalog_page(
    request: Request,
    dept: str = Query("Tous"),
    q: str = Query(""),
    db: AsyncSession = Depends(get_db)
):
    user = require_authenticated_user(request)
    await report_service.sync_catalog_if_empty(db)
    reports = await report_service.get_all_reports(db, department=dept, search_query=q, user_upn=user.get("upn"))
    departments = await report_service.get_departments_list(db)

    return templates.TemplateResponse(
        "pages/catalog.html",
        {
            "request": request,
            "user": user,
            "reports": reports,
            "departments": departments,
            "selected_dept": dept,
            "search_query": q,
            "active_page": "catalog",
            "is_admin": is_admin(user),
        }
    )


@router.get("/favorites", response_class=HTMLResponse)
async def favorites_page(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    user = require_authenticated_user(request)
    favorites = await report_service.get_user_favorites(db, user.get("upn"))
    departments = await report_service.get_departments_list(db)

    return templates.TemplateResponse(
        "pages/favorites.html",
        {
            "request": request,
            "user": user,
            "favorites": favorites,
            "departments": departments,
            "active_page": "favorites",
            "is_admin": is_admin(user),
        }
    )


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    # Si déjà connecté, rediriger vers l'accueil
    from app.auth.security import get_current_user_from_request
    from app.auth.ad_auth import DEMO_AD_USERS
    user = get_current_user_from_request(request)
    if user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(
        "pages/login.html",
        {"request": request, "user": None, "demo_users": DEMO_AD_USERS}
    )

