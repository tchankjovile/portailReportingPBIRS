"""
admin_service.py
Service d'administration :
  - Connexion SQL Server ReportServer (lecture catalogue, démasquage)
  - Gestion des signalements d'anomalies
  - Stats pour le tableau de bord admin
"""
import logging
import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc
from app.db.models import AnomalyReport, Report, AuditLog
from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Données fictives pour le mode mock (SQL Server non disponible en dev)
# ---------------------------------------------------------------------------
MOCK_REPORTSERVER_CATALOG = [
    {
        "ItemID": "a1b2c3d4-0001-0001-0001-000000000001",
        "Name": "Tableau de Bord Risques Crédit",
        "Path": "/BICEC/Risques/Tableau_Bord_Risques_Credit",
        "Type": 2,
        "Hidden": False,
        "ModifiedDate": "2026-08-15T10:30:00",
        "CreatedBy": "data.analyst@bicec.cm"
    },
    {
        "ItemID": "a1b2c3d4-0002-0002-0002-000000000002",
        "Name": "Rapport NPL Trimestriel",
        "Path": "/BICEC/Risques/Rapport_NPL_Trimestriel",
        "Type": 2,
        "Hidden": True,   # ← Rapport caché dans PBIRS
        "ModifiedDate": "2026-09-01T14:00:00",
        "CreatedBy": "data.analyst@bicec.cm"
    },
    {
        "ItemID": "a1b2c3d4-0003-0003-0003-000000000003",
        "Name": "Performances Agences — Vue Directeur",
        "Path": "/BICEC/Operations/Performances_Agences",
        "Type": 5,  # Power BI
        "Hidden": False,
        "ModifiedDate": "2026-09-10T09:15:00",
        "CreatedBy": "bi.team@bicec.cm"
    },
    {
        "ItemID": "a1b2c3d4-0004-0004-0004-000000000004",
        "Name": "Budget Prévisionnel 2026 — CONFIDENTIEL",
        "Path": "/BICEC/Finance/Budget_Previsionnel_2026",
        "Type": 5,
        "Hidden": True,   # ← Rapport caché dans PBIRS
        "ModifiedDate": "2026-07-20T16:45:00",
        "CreatedBy": "finance.dg@bicec.cm"
    },
    {
        "ItemID": "a1b2c3d4-0005-0005-0005-000000000005",
        "Name": "Suivi Conformité COBAC",
        "Path": "/BICEC/Audit/Suivi_Conformite_COBAC",
        "Type": 2,
        "Hidden": False,
        "ModifiedDate": "2026-09-12T11:00:00",
        "CreatedBy": "audit@bicec.cm"
    },
]

# ---------------------------------------------------------------------------
# Connexion SQL Server
# ---------------------------------------------------------------------------

def _get_sqlserver_connection():
    """
    Retourne une connexion pyodbc vers la base ReportServer SQL Server.
    Détecte automatiquement le driver ODBC le plus adapté disponible sur le système.
    """
    import pyodbc

    server   = settings.REPORTSERVER_SQL_SERVER
    database = settings.REPORTSERVER_DB
    username = settings.REPORTSERVER_SQL_USER
    password = settings.REPORTSERVER_SQL_PASSWORD
    trusted  = settings.REPORTSERVER_TRUSTED_CONN

    # Trouver le meilleur driver ODBC installé
    installed = pyodbc.drivers()
    candidates = [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "ODBC Driver 13 for SQL Server",
        "SQL Server Native Client 11.0",
        "SQL Server"
    ]
    driver = "SQL Server"
    for cand in candidates:
        if cand in installed:
            driver = cand
            break

    logger.info(f"Connexion SQL Server vers {server}/{database} via driver '{driver}'")

    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={server}",
        f"DATABASE={database}",
    ]

    # Tolérer les certificats auto-signés sur ODBC Driver 18 et 17
    if "18" in driver:
        parts.append("TrustServerCertificate=yes")
        parts.append("Encrypt=Optional")
    elif "17" in driver:
        parts.append("TrustServerCertificate=yes")

    if trusted or not username:
        parts.append("Trusted_Connection=yes")
    else:
        parts.append(f"UID={username}")
        parts.append(f"PWD={password}")

    conn_str = ";".join(parts)
    return pyodbc.connect(conn_str, timeout=8)


# ---------------------------------------------------------------------------
# Catalogue ReportServer
# ---------------------------------------------------------------------------

def get_catalog_from_reportserver() -> List[Dict[str, Any]]:
    """
    Lit la table Catalog de la base ReportServer SQL Server.
    Retourne tous les rapports (visibles ET cachés).
    Prend en compte :
      - Type 13 : Rapports Power BI (.pbix)
      - Type 2  : Rapports paginés (.rdl)
      - Type 5  : Modèles Power BI Desktop
    En cas d'échec de connexion : retourne les données fictives si REPORTSERVER_MOCK_MODE=True.
    """
    if settings.REPORTSERVER_MOCK_MODE:
        logger.info("REPORTSERVER_MOCK_MODE=True — Catalogue fictif retourné.")
        return [item.copy() for item in MOCK_REPORTSERVER_CATALOG]

    try:
        conn = _get_sqlserver_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                CAST(c.ItemID AS VARCHAR(50)) AS ItemID,
                c.Name,
                c.Path,
                c.Type,
                CAST(c.Hidden AS BIT) AS Hidden,
                CONVERT(VARCHAR(30), c.CreationDate, 120) AS CreationDate,
                CONVERT(VARCHAR(30), c.ModifiedDate, 120) AS ModifiedDate,
                (SELECT UserName FROM Users u WHERE u.UserID = c.CreatedByID) AS CreatedBy,
                (
                    SELECT CONVERT(VARCHAR(30), MAX(el.TimeStart), 120)
                    FROM ExecutionLogStorage el 
                    WHERE el.ReportID = c.ItemID AND el.RequestType = 0
                ) AS LastConsultation
            FROM Catalog c
            WHERE c.Type IN (2, 5, 13)
            ORDER BY c.Hidden DESC, c.Path ASC
        """)
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        conn.close()

        results = [dict(zip(columns, row)) for row in rows]
        logger.info(f"ReportServer SQL Server : {len(results)} rapports récupérés.")
        return results
    except Exception as e:
        logger.error(f"Erreur connexion ReportServer SQL Server: {e}")
        if settings.REPORTSERVER_MOCK_MODE:
            return [item.copy() for item in MOCK_REPORTSERVER_CATALOG]
        return []


def unhide_report_in_reportserver(item_id: str) -> bool:
    """
    Démasque un rapport dans la base ReportServer de façon pérenne :
    1. Met Hidden = 0 dans Catalog.
    2. Met à jour ModifiedDate = GETDATE() dans Catalog (réinitialise le compteur d'obsolescence).
    3. Met à jour TimeStart = GETDATE() dans ExecutionLogStorage pour la dernière consultation,
       ce qui empêche la procédure SQL Agent `sp_PurgeMasquageRapportsObsolescents`
       de re-masquer immédiatement le rapport lors de son prochain passage automatique !
    """
    if settings.REPORTSERVER_MOCK_MODE:
        for item in MOCK_REPORTSERVER_CATALOG:
            if item["ItemID"] == item_id:
                item["Hidden"] = False
                logger.info(f"[MOCK] Rapport démasqué : {item['Name']}")
                return True
        return False

    try:
        conn = _get_sqlserver_connection()
        cursor = conn.cursor()

        # 1. Démasquer dans Catalog et actualiser ModifiedDate à NOW
        cursor.execute("""
            UPDATE Catalog 
            SET Hidden = 0,
                ModifiedDate = GETDATE()
            WHERE ItemID = ?
        """, item_id)
        rows_affected = cursor.rowcount

        # 2. Mettre à jour l'entrée ExecutionLogStorage la plus récente pour ce rapport
        # Cela garantit que MAX(TimeStart) >= DATEADD(MONTH, -12, GETDATE())
        try:
            cursor.execute("""
                UPDATE ExecutionLogStorage
                SET TimeStart = GETDATE()
                WHERE ReportID = ?
                  AND RequestType = 0
                  AND TimeStart = (
                      SELECT MAX(sub.TimeStart)
                      FROM ExecutionLogStorage sub
                      WHERE sub.ReportID = ? AND sub.RequestType = 0
                  )
            """, (item_id, item_id))
        except Exception as e_log:
            logger.warning(f"Note: ExecutionLogStorage non mis à jour ({e_log})")

        conn.commit()
        conn.close()
        logger.info(f"Rapport démasqué et réactivé dans ReportServer (ItemID={item_id}), {rows_affected} ligne(s) modifiée(s).")
        return rows_affected > 0
    except Exception as e:
        logger.error(f"Erreur lors du démasquage du rapport {item_id}: {e}")
        return False


# ---------------------------------------------------------------------------
# Gestion des signalements d'anomalies
# ---------------------------------------------------------------------------

async def get_all_anomalies(
    db: AsyncSession,
    status_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Retourne tous les signalements d'anomalies, filtrables par statut."""
    query = select(AnomalyReport).order_by(desc(AnomalyReport.created_at))
    if status_filter and status_filter != "tous":
        query = query.where(AnomalyReport.status == status_filter)
    result = await db.execute(query)
    anomalies = result.scalars().all()
    return [
        {
            "id": a.id,
            "report_id": a.report_id,
            "report_name": a.report_name,
            "report_path": a.report_path,
            "user_upn": a.user_upn,
            "user_name": a.user_name,
            "user_dept": a.user_dept,
            "description": a.description,
            "status": a.status,
            "created_at": a.created_at.strftime("%d/%m/%Y %H:%M") if a.created_at else "",
            "resolved_at": a.resolved_at.strftime("%d/%m/%Y %H:%M") if a.resolved_at else None,
            "resolved_by": a.resolved_by,
            "admin_comment": a.admin_comment,
        }
        for a in anomalies
    ]


async def update_anomaly_status(
    db: AsyncSession,
    anomaly_id: int,
    new_status: str,
    resolver_upn: str,
    admin_comment: Optional[str] = None
) -> bool:
    """Met à jour le statut d'un signalement d'anomalie."""
    result = await db.execute(select(AnomalyReport).where(AnomalyReport.id == anomaly_id))
    anomaly = result.scalar_one_or_none()
    if not anomaly:
        return False

    anomaly.status = new_status
    if new_status == "résolu":
        anomaly.resolved_at = datetime.datetime.utcnow()
        anomaly.resolved_by = resolver_upn
    if admin_comment:
        anomaly.admin_comment = admin_comment

    await db.commit()
    return True


async def delete_report_from_portal(db: AsyncSession, report_id: int, admin_upn: str) -> bool:
    """
    Supprime un rapport de la base locale SQLite du portail.
    N'agit PAS sur la base ReportServer SQL Server.
    Écrit une entrée dans AuditLog.
    """
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        return False

    report_name = report.name
    await db.delete(report)

    audit = AuditLog(
        user_upn=admin_upn,
        action="ADMIN_DELETE_REPORT",
        report_id=report_id,
        details=f"Suppression du rapport '{report_name}' du portail local par l'administrateur.",
    )
    db.add(audit)
    await db.commit()
    logger.info(f"Rapport '{report_name}' (id={report_id}) supprimé du portail par {admin_upn}.")
    return True


# ---------------------------------------------------------------------------
# Statistiques admin dashboard
# ---------------------------------------------------------------------------

async def get_admin_stats(db: AsyncSession) -> Dict[str, Any]:
    """Retourne les KPIs pour le tableau de bord administrateur."""
    # Rapports actifs dans le portail local
    total_reports = (await db.execute(select(func.count(Report.id)))).scalar() or 0

    # Anomalies par statut
    nouveau_count = (
        await db.execute(
            select(func.count(AnomalyReport.id)).where(AnomalyReport.status == "nouveau")
        )
    ).scalar() or 0

    en_traitement_count = (
        await db.execute(
            select(func.count(AnomalyReport.id)).where(AnomalyReport.status == "en_traitement")
        )
    ).scalar() or 0

    resolu_count = (
        await db.execute(
            select(func.count(AnomalyReport.id)).where(AnomalyReport.status == "résolu")
        )
    ).scalar() or 0

    # Consultations sur les 7 derniers jours
    seven_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    views_7d = (
        await db.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.action == "VIEW_REPORT",
                AuditLog.timestamp >= seven_days_ago
            )
        )
    ).scalar() or 0

    # Rapports cachés dans ReportServer
    catalog = get_catalog_from_reportserver()
    hidden_count = sum(1 for item in catalog if item.get("Hidden"))
    total_pbirs = len(catalog)

    return {
        "total_reports_portail": total_reports,
        "total_reports_pbirs": total_pbirs,
        "hidden_reports": hidden_count,
        "anomalies_nouveau": nouveau_count,
        "anomalies_en_traitement": en_traitement_count,
        "anomalies_resolu": resolu_count,
        "anomalies_pending": nouveau_count + en_traitement_count,
        "views_7d": views_7d,
    }


admin_service_instance = None  # Pas de singleton nécessaire, toutes les fonctions sont standalone
