"""
admin.py — Routes de l'interface d'administration PBIRS BICEC
Toutes les routes sont protégées par require_admin() (groupe PBIRS-ADMINS).
"""
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.auth.security import require_admin, is_admin
from app.services.admin_service import (
    get_catalog_from_reportserver,
    unhide_report_in_reportserver,
    get_all_anomalies,
    update_anomaly_status,
    delete_report_from_portal,
    get_admin_stats,
)
from app.services.report_service import report_service
from app.templates_env import templates

router = APIRouter(prefix="/admin", tags=["Administration"])


@router.get("", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Tableau de bord administrateur avec KPIs."""
    user = require_admin(request)
    stats = await get_admin_stats(db)
    # Derniers signalements (5 plus récents, non résolus en priorité)
    recent_anomalies = await get_all_anomalies(db, status_filter=None)
    recent_anomalies = recent_anomalies[:5]
    departments = await report_service.get_departments_list(db)

    return templates.TemplateResponse(
        "pages/admin_dashboard.html",
        {
            "request": request,
            "user": user,
            "stats": stats,
            "recent_anomalies": recent_anomalies,
            "departments": departments,
            "active_page": "admin",
            "is_admin": True,
        }
    )


@router.get("/catalog", response_class=HTMLResponse)
async def admin_catalog(
    request: Request,
    filter_hidden: str = "tous",
    db: AsyncSession = Depends(get_db)
):
    """Vue du catalogue ReportServer — affiche les rapports visibles ET cachés."""
    user = require_admin(request)
    catalog_items = get_catalog_from_reportserver()
    departments = await report_service.get_departments_list(db)

    # Filtrage par état
    if filter_hidden == "caches":
        catalog_items = [i for i in catalog_items if i.get("Hidden")]
    elif filter_hidden == "visibles":
        catalog_items = [i for i in catalog_items if not i.get("Hidden")]

    # Rapports présents dans le portail local (pour le bouton "Supprimer du portail")
    all_portal_reports = await report_service.get_all_reports(db)
    portal_paths = {r["path"]: r["id"] for r in all_portal_reports}

    return templates.TemplateResponse(
        "pages/admin_catalog.html",
        {
            "request": request,
            "user": user,
            "catalog_items": catalog_items,
            "portal_paths": portal_paths,
            "filter_hidden": filter_hidden,
            "departments": departments,
            "active_page": "admin",
            "is_admin": True,
        }
    )


@router.post("/catalog/{item_id}/unhide", response_class=HTMLResponse)
async def unhide_catalog_item(
    request: Request,
    item_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Démasque un rapport dans la base ReportServer (Hidden → 0)."""
    user = require_admin(request)
    success = unhide_report_in_reportserver(item_id)
    if success:
        return HTMLResponse(f"""
        <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-700 border border-emerald-200">
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
            VISIBLE
        </span>
        <span class="text-xs text-emerald-600 ml-2 font-medium">✓ Démasqué avec succès</span>
        """)
    else:
        return HTMLResponse(f"""
        <span class="text-xs text-red-600 font-medium">✗ Erreur lors du démasquage</span>
        """)


@router.post("/reports/{report_id}/delete", response_class=HTMLResponse)
async def delete_portal_report(
    request: Request,
    report_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Supprime un rapport de la base locale SQLite du portail."""
    user = require_admin(request)
    success = await delete_report_from_portal(db, report_id, user.get("upn"))
    if success:
        return HTMLResponse(f"""
        <tr id="report-row-{report_id}" class="opacity-50">
            <td colspan="5" class="text-center py-3 text-sm text-gray-500 italic">
                Rapport supprimé du portail.
            </td>
        </tr>
        """)
    else:
        raise HTTPException(status_code=404, detail="Rapport non trouvé")


@router.get("/anomalies", response_class=HTMLResponse)
async def admin_anomalies(
    request: Request,
    status_filter: str = "tous",
    db: AsyncSession = Depends(get_db)
):
    """Gestion des signalements d'anomalies soumis par les utilisateurs."""
    user = require_admin(request)
    anomalies = await get_all_anomalies(db, status_filter=status_filter)
    stats = await get_admin_stats(db)
    departments = await report_service.get_departments_list(db)

    return templates.TemplateResponse(
        "pages/admin_anomalies.html",
        {
            "request": request,
            "user": user,
            "anomalies": anomalies,
            "status_filter": status_filter,
            "stats": stats,
            "departments": departments,
            "active_page": "admin",
            "is_admin": True,
        }
    )


@router.post("/anomalies/{anomaly_id}/status", response_class=HTMLResponse)
async def update_anomaly(
    request: Request,
    anomaly_id: int,
    new_status: str = Form(...),
    admin_comment: str = Form(""),
    db: AsyncSession = Depends(get_db)
):
    """Met à jour le statut d'un signalement d'anomalie."""
    user = require_admin(request)

    valid_statuses = ["nouveau", "en_traitement", "résolu"]
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Statut invalide")

    success = await update_anomaly_status(
        db=db,
        anomaly_id=anomaly_id,
        new_status=new_status,
        resolver_upn=user.get("upn", ""),
        admin_comment=admin_comment.strip() or None
    )

    status_labels = {
        "nouveau": ("bg-red-100 text-red-700 border-red-200", "🔴 Nouveau"),
        "en_traitement": ("bg-amber-100 text-amber-700 border-amber-200", "🟡 En traitement"),
        "résolu": ("bg-emerald-100 text-emerald-700 border-emerald-200", "🟢 Résolu"),
    }
    css, label = status_labels.get(new_status, ("bg-gray-100 text-gray-700 border-gray-200", new_status))

    return HTMLResponse(f"""
    <div class="flex items-center gap-2">
        <span class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold border {css}">
            {label}
        </span>
        <span class="text-xs text-gray-500">Mis à jour</span>
    </div>
    """)
