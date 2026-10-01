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
    get_anomaly_by_id,
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
    """Tableau de bord administrateur avec KPIs et alertes d'anomalies."""
    user = require_admin(request)
    stats = await get_admin_stats(db)
    
    # Récupérer les signalements et prioriser les nouveaux et en traitement
    all_anomalies = await get_all_anomalies(db, status_filter=None)
    priority_order = {"nouveau": 0, "en_traitement": 1, "résolu": 2}
    all_anomalies.sort(key=lambda a: (priority_order.get(a.get("status", ""), 3)))
    recent_anomalies = all_anomalies[:5]

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
    """Démasque un rapport dans la base ReportServer (Hidden → 0) de façon pérenne."""
    user = require_admin(request)
    success = unhide_report_in_reportserver(item_id)
    if success:
        # Re-synchroniser immédiatement le catalogue du portail
        try:
            await report_service.sync_catalog_if_empty(db)
        except Exception as e:
            pass

        return HTMLResponse(f"""
        <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-700 border border-emerald-200">
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
            VISIBLE
        </span>
        <span class="text-xs text-emerald-600 ml-2 font-medium">✓ Démasqué & réactivé (+12 mois)</span>
        """)
    else:
        return HTMLResponse(f"""
        <span class="text-xs text-red-600 font-medium">✗ Erreur lors du démasquage</span>
        """)


@router.post("/sync", response_class=HTMLResponse)
async def admin_sync_catalog(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Force une re-synchronisation complète du catalogue depuis PBIRS et ReportServer."""
    user = require_admin(request)
    try:
        await report_service.sync_catalog_if_empty(db)
        return HTMLResponse("""
        <span class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-emerald-100 text-emerald-700 border border-emerald-200">
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
            Catalogue synchronisé
        </span>
        """)
    except Exception as e:
        return HTMLResponse(f"""
        <span class="text-xs text-red-600 font-medium">Erreur synchronisation : {e}</span>
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
    """Met à jour le statut d'un signalement d'anomalie et réaffiche la carte mise à jour."""
    user = require_admin(request)

    clean_status = new_status.strip().lower()
    valid_statuses = ["nouveau", "en_traitement", "résolu"]
    if clean_status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Statut invalide")

    resolver_name = user.get("display_name") or user.get("upn", "")

    await update_anomaly_status(
        db=db,
        anomaly_id=anomaly_id,
        new_status=clean_status,
        resolver_upn=resolver_name,
        admin_comment=admin_comment.strip() or None
    )

    anomaly = await get_anomaly_by_id(db, anomaly_id)
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomalie introuvable")

    stats = await get_admin_stats(db)

    # Styles et icônes
    status_classes = {
        'nouveau': 'bg-red-100 text-red-700 border-red-200',
        'en_traitement': 'bg-amber-100 text-amber-700 border-amber-200',
        'résolu': 'bg-emerald-100 text-emerald-700 border-emerald-200'
    }
    status_icons = {'nouveau': '🔴', 'en_traitement': '🟡', 'résolu': '🟢'}
    badge_css = status_classes.get(anomaly['status'], 'bg-gray-100 text-gray-700 border-gray-200')
    badge_icon = status_icons.get(anomaly['status'], '⚪')
    status_title = anomaly['status'].capitalize().replace('_', ' ')

    resolved_meta = ""
    if anomaly['status'] == 'résolu' and anomaly.get('resolved_by'):
        resolved_meta = f'<span class="text-[11px] text-emerald-600 font-semibold">· Résolu par {anomaly["resolved_by"]} le {anomaly.get("resolved_at", "")}</span>'

    admin_comment_html = ""
    if anomaly.get('admin_comment'):
        admin_comment_html = f'''
        <div class="mt-2 p-2.5 bg-blue-50 dark:bg-blue-950/30 rounded-lg border border-blue-100 dark:border-blue-900">
            <p class="text-xs text-blue-700 dark:text-blue-300"><span class="font-semibold">Note admin :</span> {anomaly["admin_comment"]}</p>
        </div>
        '''

    actions_html = '''
        <span class="inline-flex items-center gap-1 text-xs text-emerald-600 font-bold px-2.5 py-1 bg-emerald-50 rounded-lg border border-emerald-200">
            ✓ Clôturé
        </span>
    ''' if anomaly['status'] == 'résolu' else f'''
        <button @click="formOpen = !formOpen"
                class="px-3 py-1.5 rounded-lg text-xs font-bold bg-bicec-orange text-white hover:bg-bicec-orange-hover transition-colors whitespace-nowrap">
            Traiter
        </button>
    '''

    oob_counter = ""
    if stats.get("anomalies_pending", 0) > 0:
        oob_counter = f'''
        <div id="anomalies-pending-counter" hx-swap-oob="true">
            <div class="flex items-center gap-2 px-4 py-2 bg-red-50 dark:bg-red-950/30 rounded-xl border border-red-200 dark:border-red-900">
                <span class="w-2 h-2 rounded-full bg-red-500 animate-pulse"></span>
                <span class="text-sm font-bold text-red-700 dark:text-red-400">{stats["anomalies_pending"]} signalement(s) en attente</span>
            </div>
        </div>
        '''
    else:
        oob_counter = '''
        <div id="anomalies-pending-counter" hx-swap-oob="true"></div>
        '''

    return HTMLResponse(f"""
    <div id="anomaly-item-{anomaly['id']}" class="p-5 hover:bg-gray-50 dark:hover:bg-gray-700/40 transition-colors" x-data="{{ expanded: false, formOpen: false }}">
        <div class="flex items-start justify-between gap-4">
            <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 flex-wrap mb-1">
                    <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold border {badge_css}">
                        {badge_icon} {status_title}
                    </span>
                    <span class="text-xs font-mono text-gray-400">#{anomaly['id']}</span>
                </div>
                <h3 class="font-semibold text-sm text-gray-900 dark:text-white truncate">
                    📊 {anomaly['report_name']}
                </h3>
                <p class="text-sm text-gray-600 dark:text-gray-400 mt-1 leading-relaxed">
                    {anomaly['description']}
                </p>
                <div class="flex items-center gap-3 mt-2 flex-wrap">
                    <span class="text-[11px] text-gray-400">
                        👤 <span class="font-medium text-gray-600 dark:text-gray-300">{anomaly['user_name']}</span>
                    </span>
                    <span class="text-[11px] text-gray-400">· {anomaly['user_dept']}</span>
                    <span class="text-[11px] text-gray-400">· {anomaly['created_at']}</span>
                    {resolved_meta}
                </div>
                {admin_comment_html}
            </div>
            <div class="flex-shrink-0 flex flex-col gap-2">
                {actions_html}
            </div>
        </div>
    </div>
    {oob_counter}
    """)


@router.post("/anomalies/{anomaly_id}/quick-status", response_class=HTMLResponse)
async def quick_status_anomaly(
    request: Request,
    anomaly_id: int,
    new_status: str,
    db: AsyncSession = Depends(get_db)
):
    """Met à jour le statut en un clic depuis le dashboard."""
    user = require_admin(request)
    valid_statuses = ["nouveau", "en_traitement", "résolu"]
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Statut invalide")

    await update_anomaly_status(
        db=db,
        anomaly_id=anomaly_id,
        new_status=new_status,
        resolver_upn=user.get("upn", ""),
        admin_comment=None
    )

    status_labels = {
        "nouveau": ("bg-red-100 text-red-700 border-red-200", "🔴 Nouveau"),
        "en_traitement": ("bg-amber-100 text-amber-700 border-amber-200", "🟡 En traitement"),
        "résolu": ("bg-emerald-100 text-emerald-700 border-emerald-200", "🟢 Résolu"),
    }
    css, label = status_labels.get(new_status, ("bg-gray-100 text-gray-700 border-gray-200", new_status))

    return HTMLResponse(f"""
    <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold border {css} shadow-sm animate-pulse">
        {label}
    </span>
    """)
