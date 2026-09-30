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
        user_upn: Optional[str] = None,
        allowed_departments: Optional[List[str]] = None,
        user: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Fetches reports with user favorite flags, PBIRS security policies and department access control."""
        query = select(Report)

        # Filtre par département sélectionné par l'utilisateur dans l'interface
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

        # Vérification des droits PBIRS de l'utilisateur
        is_super = False
        user_groups = []
        user_name = ""
        if user:
            from app.auth.security import is_admin
            is_super = is_admin(user) or user.get("department") in ["Direction Générale", "Data & Business Intelligence"]
            user_groups = [g.upper().strip() for g in user.get("groups", [])]
            user_name = user.get("username", "").upper().strip()

        output = []
        for r in reports:
            # Si l'utilisateur n'a pas les droits totaux, filtrer selon ses permissions PBIRS
            if user and not is_super:
                has_access = False
                tags_str = r.tags or ""
                
                # 1. Vérifier si un groupe AD de l'utilisateur a été autorisé dans PBIRS (Explorateur, etc.)
                if "ALLOWED:" in tags_str:
                    allowed_part = tags_str.split("ALLOWED:", 1)[1]
                    allowed_principals = [x.strip().upper() for x in allowed_part.split(",") if x.strip()]
                    if any(g in allowed_principals for g in user_groups):
                        has_access = True
                    elif user_name and user_name in allowed_principals:
                        has_access = True

                # 2. Vérifier si le département du rapport fait partie des départements autorisés
                if not has_access and allowed_departments:
                    if r.department in allowed_departments:
                        has_access = True

                # Si l'utilisateur n'a aucun droit sur ce rapport/dossier, on l'exclut
                if not has_access:
                    continue

            # Nettoyer les tags pour ne pas afficher la chaîne interne ALLOWED dans les badges de l'UI
            display_tags = []
            if r.tags:
                clean_tag_str = r.tags.split("ALLOWED:")[0].strip().rstrip("|").strip()
                display_tags = [t.strip() for t in clean_tag_str.split(",") if t.strip()]

            output.append({
                "id": r.id,
                "pbirs_id": r.pbirs_id,
                "name": r.name,
                "path": r.path,
                "description": r.description,
                "category": r.category,
                "department": r.department,
                "tags": display_tags,
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
        db_departments = [row[0] for row in result.all() if row[0]]
        # Inclure les pôles & métiers officiels définis dans la hiérarchie BICEC
        hierarchy_depts = [k for k in settings.get_dept_hierarchy().keys() if k != "Général"]
        all_departments = sorted(list(set(db_departments + hierarchy_depts)))
        return ["Tous"] + all_departments

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
