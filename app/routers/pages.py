from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.auth.security import require_authenticated_user, is_admin
from app.services.report_service import report_service
from app.templates_env import templates
from app.config import settings

router = APIRouter(tags=["Pages"])


def _redirect_login():
    return RedirectResponse(url="/login", status_code=302)


@router.get("/", response_class=HTMLResponse)
async def home_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    user = require_authenticated_user(request)
    admin = is_admin(user)
    is_super = admin
    
    await report_service.sync_catalog_if_empty(db)

    # Récupérer les rapports autorisés pour cet utilisateur
    reports = await report_service.get_all_reports(
        db,
        user_upn=user.get("upn"),
        user=user
    )

    # Les dossiers visibles dans la sidebar et les filtres sont UNIQUEMENT les dossiers PBIRS autorisés
    if is_super:
        visible_depts = await report_service.get_departments_list(db)
    else:
        user_folders = sorted(list({r["department"] for r in reports if r.get("department") and r.get("department") != "Général"}))
        visible_depts = ["Tous"] + user_folders

    favorites = await report_service.get_user_favorites(db, user.get("upn"))
    visible_report_ids = {r["id"] for r in reports}
    favorites = [f for f in favorites if f.get("id") in visible_report_ids]
    featured_reports = [r for r in reports if r.get("is_featured")]

    return templates.TemplateResponse(
        "pages/dashboard.html",
        {
            "request": request,
            "user": user,
            "reports": reports,
            "featured_reports": featured_reports,
            "favorites": favorites,
            "departments": visible_depts,
            "active_page": "dashboard",
            "is_admin": admin,
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
    admin = is_admin(user)
    is_super = admin

    await report_service.sync_catalog_if_empty(db)

    # Récupérer d'abord tous les rapports autorisés pour l'utilisateur
    all_user_reports = await report_service.get_all_reports(
        db,
        user_upn=user.get("upn"),
        user=user
    )

    if is_super:
        visible_depts = await report_service.get_departments_list(db)
    else:
        user_folders = sorted(list({r["department"] for r in all_user_reports if r.get("department") and r.get("department") != "Général"}))
        visible_depts = ["Tous"] + user_folders

    # Si un utilisateur non-admin tente de filtrer sur un dossier auquel il n'a pas accès
    if not is_super and dept != "Tous" and dept not in visible_depts:
        reports = []
    else:
        reports = await report_service.get_all_reports(
            db,
            department=dept,
            search_query=q,
            user_upn=user.get("upn"),
            user=user
        )

    return templates.TemplateResponse(
        "pages/catalog.html",
        {
            "request": request,
            "user": user,
            "reports": reports,
            "departments": visible_depts,
            "selected_dept": dept,
            "search_query": q,
            "active_page": "catalog",
            "is_admin": admin,
        }
    )


@router.get("/favorites", response_class=HTMLResponse)
async def favorites_page(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    user = require_authenticated_user(request)
    admin = is_admin(user)
    is_super = admin

    all_user_reports = await report_service.get_all_reports(
        db,
        user_upn=user.get("upn"),
        user=user
    )

    if is_super:
        visible_depts = await report_service.get_departments_list(db)
    else:
        user_folders = sorted(list({r["department"] for r in all_user_reports if r.get("department") and r.get("department") != "Général"}))
        visible_depts = ["Tous"] + user_folders

    favorites = await report_service.get_user_favorites(db, user.get("upn"))
    visible_report_ids = {r["id"] for r in all_user_reports}
    favorites = [f for f in favorites if f.get("id") in visible_report_ids]

    return templates.TemplateResponse(
        "pages/favorites.html",
        {
            "request": request,
            "user": user,
            "favorites": favorites,
            "departments": visible_depts,
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

