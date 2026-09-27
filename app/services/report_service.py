import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc, or_, and_
from app.db.models import Report, Favorite, ReportHistory, AuditLog, AnomalyReport
from app.services.pbirs_client import INITIAL_BICEC_CATALOG, PBIRSClient
from app.config import settings

class ReportService:
    """
    Business Logic Service for Report Catalog, DAX Row-Level Security (RLS)
    generation, user favorites, and consultation audit tracking.
    """

    async def sync_catalog_if_empty(self, db: AsyncSession):
        """
        Synchronise le catalogue depuis PBIRS.
        - Si PBIRS_MOCK_MODE=True : insère les données de démo seulement si la DB est vide.
        - Si PBIRS_MOCK_MODE=False : vide et recharge TOUJOURS depuis l'API PBIRS réelle.
        """
        import logging
        logger = logging.getLogger(__name__)

        result = await db.execute(select(func.count(Report.id)))
        count = result.scalar()

        if not settings.PBIRS_MOCK_MODE:
            # --- Mode PBIRS réel : re-sync complet depuis l'API ---
            logger.info("PBIRS_MOCK_MODE=False — Synchronisation depuis l'API PBIRS réelle...")
            client = PBIRSClient()
            pbirs_items = await client.fetch_catalog_items()

            # Vider le catalogue existant (même les anciennes données fictives)
            existing = await db.execute(select(Report))
            for report in existing.scalars().all():
                await db.delete(report)
            await db.commit()

            # Insérer les données fraîches depuis PBIRS
            for item in pbirs_items:
                report = Report(
                    pbirs_id=item["pbirs_id"],
                    name=item["name"],
                    path=item["path"],
                    description=item["description"],
                    category=item["category"],
                    department=item["department"],
                    tags=item["tags"],
                    embed_url=item["embed_url"],
                    is_featured=item.get("is_featured", False)
                )
                db.add(report)
            await db.commit()
            logger.info(f"Catalogue synchronisé : {len(pbirs_items)} rapports chargés depuis PBIRS.")

        elif count == 0:
            # --- Mode Mock : insère les données de démo seulement si DB vide ---
            logger.info("PBIRS_MOCK_MODE=True, DB vide — Insertion des données de démonstration.")
            for item in INITIAL_BICEC_CATALOG:
                report = Report(
                    pbirs_id=item["pbirs_id"],
                    name=item["name"],
                    path=item["path"],
                    description=item["description"],
                    category=item["category"],
                    department=item["department"],
                    tags=item["tags"],
                    embed_url=item["embed_url"],
                    is_featured=item["is_featured"]
                )
                db.add(report)
            await db.commit()


    async def get_all_reports(
        self,
        db: AsyncSession,
        department: Optional[str] = None,
        search_query: Optional[str] = None,
        user_upn: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetches reports with user favorite flags and department filtering."""
        query = select(Report)

        if department and department != "Tous":
            query = query.where(Report.department == department)

        if search_query:
            term = f"%{search_query}%"
            query = query.where(
                or_(
                    Report.name.ilike(term),
                    Report.description.ilike(term),
                    Report.tags.ilike(term),
                    Report.category.ilike(term)
                )
            )

        query = query.order_by(desc(Report.is_featured), Report.name)
        result = await db.execute(query)
        reports = result.scalars().all()

        # Get user favorites set
        user_fav_ids = set()
        if user_upn:
            fav_result = await db.execute(select(Favorite.report_id).where(Favorite.user_upn == user_upn))
            user_fav_ids = set(fav_result.scalars().all())

        output = []
        for r in reports:
            output.append({
                "id": r.id,
                "pbirs_id": r.pbirs_id,
                "name": r.name,
                "path": r.path,
                "description": r.description,
                "category": r.category,
                "department": r.department,
                "tags": r.tags.split(",") if r.tags else [],
                "embed_url": r.embed_url,
                "view_count": r.view_count,
                "is_featured": r.is_featured,
                "is_favorite": r.id in user_fav_ids
            })
        return output

    async def get_report_by_id(self, db: AsyncSession, report_id: int, user_upn: str) -> Optional[Dict[str, Any]]:
        result = await db.execute(select(Report).where(Report.id == report_id))
        r = result.scalar_one_or_none()
        if not r:
            return None

        # Check favorite status
        fav_result = await db.execute(
            select(Favorite).where(and_(Favorite.report_id == report_id, Favorite.user_upn == user_upn))
        )
        is_fav = fav_result.scalar_one_or_none() is not None

        return {
            "id": r.id,
            "pbirs_id": r.pbirs_id,
            "name": r.name,
            "path": r.path,
            "description": r.description,
            "category": r.category,
            "department": r.department,
            "tags": r.tags.split(",") if r.tags else [],
            "embed_url": r.embed_url,
            "view_count": r.view_count,
            "is_featured": r.is_featured,
            "is_favorite": is_fav
        }

    def generate_dax_embed_url(
        self,
        base_embed_url: str,
        user_session: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Construit l'URL d'embed PBIRS sécurisée.
        Le filtre DAX RLS est appliqué directement par PBIRS en fonction
        de l'identité de l'utilisateur transmise via la session Windows.
        Le portail ne fait qu'identifier l'utilisateur — le DAX est défini
        par le concepteur du rapport dans le fichier .pbix.
        """
        clean_url = base_embed_url if base_embed_url else "http://pbirs.bicec.local/Reports/powerbi/BICEC/Demo"
        
        # Paramètres PBIRS standard pour embed propre dans iframe
        params = [
            "rs:Embed=true",
            "rc:Toolbar=false",
        ]

        full_embed_url = f"{clean_url}?{'&'.join(params)}"

        return {
            "full_embed_url": full_embed_url,
            "user_context": {
                "upn": user_session.get("upn"),
                "display_name": user_session.get("display_name"),
                "department": user_session.get("department"),
                "agency": user_session.get("agency"),
                "role": user_session.get("role")
            }
        }

    async def toggle_favorite(self, db: AsyncSession, report_id: int, user_upn: str) -> bool:
        """Toggles favorite bookmark for a report. Returns True if now favorite, False if removed."""
        result = await db.execute(
            select(Favorite).where(and_(Favorite.report_id == report_id, Favorite.user_upn == user_upn))
        )
        existing = result.scalar_one_or_none()
        if existing:
            await db.delete(existing)
            await db.commit()
            return False
        else:
            fav = Favorite(report_id=report_id, user_upn=user_upn)
            db.add(fav)
            await db.commit()
            return True

    async def log_view_event(self, db: AsyncSession, report_id: int, user_upn: str, ip_address: str = "127.0.0.1"):
        """Logs report consultation history and increments total view count."""
        # Increment view count
        result = await db.execute(select(Report).where(Report.id == report_id))
        report = result.scalar_one_or_none()
        if report:
            report.view_count += 1
            
            # Add history entry
            history = ReportHistory(report_id=report_id, user_upn=user_upn)
            db.add(history)

            # Audit log
            audit = AuditLog(
                user_upn=user_upn,
                action="VIEW_REPORT",
                report_id=report_id,
                details=f"Consultation du rapport '{report.name}'",
                ip_address=ip_address
            )
            db.add(audit)
            await db.commit()

    async def get_user_favorites(self, db: AsyncSession, user_upn: str) -> List[Dict[str, Any]]:
        result = await db.execute(
            select(Report)
            .join(Favorite, Favorite.report_id == Report.id)
            .where(Favorite.user_upn == user_upn)
            .order_by(desc(Favorite.added_at))
        )
        reports = result.scalars().all()
        return [
            {
                "id": r.id,
                "pbirs_id": r.pbirs_id,
                "name": r.name,
                "path": r.path,
                "description": r.description,
                "category": r.category,
                "department": r.department,
                "tags": r.tags.split(",") if r.tags else [],
                "embed_url": r.embed_url,
                "view_count": r.view_count,
                "is_featured": r.is_featured,
                "is_favorite": True
            }
            for r in reports
        ]

    async def get_departments_list(self, db: AsyncSession) -> List[str]:
        result = await db.execute(select(Report.department).distinct())
        departments = [row[0] for row in result.all() if row[0]]
        return ["Tous"] + sorted(departments)

    async def submit_anomaly(
        self,
        db: AsyncSession,
        report_id: Optional[int],
        report_name: str,
        report_path: str,
        user_upn: str,
        user_name: str,
        user_dept: str,
        description: str
    ) -> AnomalyReport:
        """Enregistre un signalement d'anomalie soumis par un utilisateur."""
        anomaly = AnomalyReport(
            report_id=report_id,
            report_name=report_name,
            report_path=report_path,
            user_upn=user_upn,
            user_name=user_name,
            user_dept=user_dept,
            description=description,
            status="nouveau"
        )
        db.add(anomaly)
        await db.commit()
        await db.refresh(anomaly)
        return anomaly

report_service = ReportService()
