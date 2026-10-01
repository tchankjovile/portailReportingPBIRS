from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.auth.security import require_authenticated_user, is_admin
from app.services.report_service import report_service
from app.templates_env import templates

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/{report_id}", response_class=HTMLResponse)
async def view_report(
    request: Request,
    report_id: int,
    db: AsyncSession = Depends(get_db)
):
    user = require_authenticated_user(request)
    report = await report_service.get_report_by_id(db, report_id, user.get("upn"))

    if not report:
        raise HTTPException(status_code=404, detail="Rapport non trouvé")

    admin = is_admin(user)
    is_super = admin

    # Vérification stricte des autorisations PBIRS
    if not is_super and not report_service.can_user_access_report(report, user):
        all_user_reports = await report_service.get_all_reports(db, user_upn=user.get("upn"), user=user)
        user_folders = sorted(list({r["department"] for r in all_user_reports if r.get("department") and r.get("department") != "Général"}))
        return templates.TemplateResponse(
            "pages/403.html",
            {
                "request": request,
                "user": user,
                "report_name": report.get("name"),
                "folder_name": report.get("department"),
                "departments": ["Tous"] + user_folders,
                "active_page": "catalog",
                "is_admin": admin,
            },
            status_code=403
        )

    client_ip = request.client.host if request.client else "127.0.0.1"
    await report_service.log_view_event(db, report_id, user.get("upn"), client_ip)

    # L'URL embed est construite sans DAX personnalisé — le RLS est géré par PBIRS
    rls_data = report_service.generate_dax_embed_url(
        base_embed_url=report["embed_url"],
        user_session=user
    )

    if is_super:
        departments = await report_service.get_departments_list(db)
    else:
        all_user_reports = await report_service.get_all_reports(db, user_upn=user.get("upn"), user=user)
        user_folders = sorted(list({r["department"] for r in all_user_reports if r.get("department") and r.get("department") != "Général"}))
        departments = ["Tous"] + user_folders

    return templates.TemplateResponse(
        "pages/report_view.html",
        {
            "request": request,
            "user": user,
            "report": report,
            "embed_url": rls_data["full_embed_url"],
            "departments": departments,
            "active_page": "catalog",
            "is_admin": admin,
        }
    )


@router.get("/{report_id}/embed-partial", response_class=HTMLResponse)
async def embed_partial(
    request: Request,
    report_id: int,
    db: AsyncSession = Depends(get_db)
):
    user = require_authenticated_user(request)
    report = await report_service.get_report_by_id(db, report_id, user.get("upn"))
    if not report:
        return HTMLResponse("<div class='p-4 text-red-600'>Erreur de chargement du rapport.</div>")

    admin = is_admin(user)
    is_super = admin

    if not is_super and not report_service.can_user_access_report(report, user):
        return HTMLResponse(
            "<div class='p-6 text-center text-red-600 bg-red-50 dark:bg-gray-800 rounded-2xl border border-red-200 dark:border-red-900'>"
            "<p class='font-bold text-base mb-1'>Accès refusé par les politiques de sécurité PBIRS</p>"
            "<p class='text-xs text-gray-500'>Vous ne disposez pas des privilèges nécessaires sur ce dossier pour afficher ce rapport.</p>"
            "</div>",
            status_code=403
        )

    rls_data = report_service.generate_dax_embed_url(
        base_embed_url=report["embed_url"],
        user_session=user
    )

    return templates.TemplateResponse(
        "components/report_embed.html",
        {
            "request": request,
            "report": report,
            "embed_url": rls_data["full_embed_url"],
            "user": user,
            "is_admin": admin,
        }
    )
