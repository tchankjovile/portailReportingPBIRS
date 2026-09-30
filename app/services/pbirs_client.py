import logging
import httpx
from httpx_ntlm import HttpNtlmAuth
from typing import List, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)

# Sample Catalog Seed Data representing actual BICEC Banking Reports
INITIAL_BICEC_CATALOG = [
    {
        "pbirs_id": "bicec-rep-001",
        "name": "Tableau de Bord Exécutif - PNB & Rentabilité",
        "path": "/BICEC/DirectionGenerale/PNB_Rentabilite_Executif",
        "description": "Synthèse consolidée du Produit Net Bancaire, marge nette d'intérêt et coefficient d'exploitation par pôle d'activité.",
        "category": "Direction Générale",
        "department": "Direction Générale",
        "tags": "KPI, Mensuel, PNB, Stratégique",
        "embed_url": "http://pbirs.bicec.local/Reports/powerbi/BICEC/DirectionGenerale/PNB_Rentabilite_Executif",
        "is_featured": True,
    },
    {
        "pbirs_id": "bicec-rep-002",
        "name": "Cartographie des Risques de Crédit & NPL",
        "path": "/BICEC/Risques/Cartographie_Risques_Credit",
        "description": "Suivi du portefeuille de créances douteuses (NPL), provisions COBAC, taux de couverture et engagement par contrepartie.",
        "category": "Gestion des Risques",
        "department": "Gestion des Risques",
        "tags": "Risque, COBAC, NPL, Provisions, Audité",
        "embed_url": "http://pbirs.bicec.local/Reports/powerbi/BICEC/Risques/Cartographie_Risques_Credit",
        "is_featured": True,
    },
    {
        "pbirs_id": "bicec-rep-003",
        "name": "Pilotage de la Performance des Agences",
        "path": "/BICEC/Operations/Performance_Agences_Reseau",
        "description": "Indicateurs commerciaux des agences : ouvertures de comptes, collecte des dépôts, octroi de crédits et objectifs trimestriels.",
        "category": "Opérations Bancaires",
        "department": "Opérations Bancaires",
        "tags": "Agences, Dépôts, Crédits, Réseau, Hebdo",
        "embed_url": "http://pbirs.bicec.local/Reports/powerbi/BICEC/Operations/Performance_Agences_Reseau",
        "is_featured": True,
    },
    {
        "pbirs_id": "bicec-rep-004",
        "name": "Contrôle Budgétaire & Suivi des Charges OPEX",
        "path": "/BICEC/Finance/Suivi_Budget_OPEX",
        "description": "Analyse comparative du réalisé vs budgété par centre de coûts, département et nature de dépenses de fonctionnement.",
        "category": "Finance & Comptabilité",
        "department": "Finance & Comptabilité",
        "tags": "Budget, OPEX, Contrôle, Mensuel",
        "embed_url": "http://pbirs.bicec.local/Reports/powerbi/BICEC/Finance/Suivi_Budget_OPEX",
        "is_featured": False,
    },
    {
        "pbirs_id": "bicec-rep-005",
        "name": "Ratios Réglementaires & Déclarations COBAC",
        "path": "/BICEC/Conformite/Ratios_Reglementaires_COBAC",
        "description": "Ratios de liquidité, division des risques, fonds propres nets et adéquation du capital selon les directives BEAC/COBAC.",
        "category": "Audit & Conformité",
        "department": "Audit & Conformité",
        "tags": "COBAC, BEAC, Liquidité, Conformité",
        "embed_url": "http://pbirs.bicec.local/Reports/powerbi/BICEC/Conformite/Ratios_Reglementaires_COBAC",
        "is_featured": True,
    },
    {
        "pbirs_id": "bicec-rep-006",
        "name": "Suivi des Effectifs & Masse Salariale HR",
        "path": "/BICEC/DRH/Suivi_Effectifs_MasseSalariale",
        "description": "Tableau de bord RH : répartition de la masse salariale, pyramide des âges, mobilités internes et turn-over par agence.",
        "category": "Ressources Humaines",
        "department": "Ressources Humaines",
        "tags": "RH, Masse Salariale, Effectifs, Social",
        "embed_url": "http://pbirs.bicec.local/Reports/powerbi/BICEC/DRH/Suivi_Effectifs_MasseSalariale",
        "is_featured": False,
    },
    {
        "pbirs_id": "bicec-rep-007",
        "name": "Analyse de la Collecte & Dépôts de la Clientèle",
        "path": "/BICEC/Finance/Analyse_Depots_Clientele",
        "description": "Structure des ressources collectées : comptes chèques, comptes d'épargne, DAT et dépôts institutionnels.",
        "category": "Finance & Comptabilité",
        "department": "Finance & Comptabilité",
        "tags": "Dépôts, Épargne, DAT, Liquidité",
        "embed_url": "http://pbirs.bicec.local/Reports/powerbi/BICEC/Finance/Analyse_Depots_Clientele",
        "is_featured": False,
    },
    {
        "pbirs_id": "bicec-rep-008",
        "name": "Journal d'Audit & Suivi des Recommandations",
        "path": "/BICEC/Audit/Suivi_Recommandations_Inspection",
        "description": "État d'avancement des plans d'action issus des missions d'inspection générale et d'audit externe.",
        "category": "Audit & Conformité",
        "department": "Audit & Conformité",
        "tags": "Audit, Inspection, Plan Action",
        "embed_url": "http://pbirs.bicec.local/Reports/powerbi/BICEC/Audit/Suivi_Recommandations_Inspection",
        "is_featured": False,
    }
]

class PBIRSClient:
    """
    HTTP Client pour l'API REST Power BI Report Server v2.0.
    Utilise l'authentification Windows SSPI native via requests-negotiate-sspi.
    Même méthode que PowerShell -UseDefaultCredentials. Fallback auto sur démo.
    """

    def _fetch_catalog_sync(self) -> List[Dict[str, Any]]:
        """
        Appel synchrone à l'API PBIRS avec la session Windows courante (SSPI).
        Utilise /PowerBIReports et /Reports pour récupérer TOUS les rapports
        dans tous les sous-dossiers (pas seulement le niveau racine).
        """
        try:
            from requests_negotiate_sspi import HttpNegotiateAuth
            import requests

            logger.info(f"Connexion PBIRS (SSPI session Windows) → {settings.PBIRS_API_URL}")

            session = requests.Session()
            session.auth = HttpNegotiateAuth()
            session.verify = False
            session.timeout = 15

            all_items = []

            # Endpoint 1 : Rapports Power BI (.pbix) — tous dossiers confondus
            resp_pbi = session.get(f"{settings.PBIRS_API_URL}/PowerBIReports")
            if resp_pbi.status_code == 200:
                pbi_reports = resp_pbi.json().get("value", [])
                for r in pbi_reports:
                    r["Type"] = "PowerBIReport"
                all_items.extend(pbi_reports)
                logger.info(f"PBIRS — {len(pbi_reports)} rapports PowerBI (.pbix) trouvés.")
            else:
                logger.warning(f"PBIRS /PowerBIReports → {resp_pbi.status_code}")

            # Endpoint 2 : Rapports paginés (.rdl) — tous dossiers confondus
            resp_rdl = session.get(f"{settings.PBIRS_API_URL}/Reports")
            if resp_rdl.status_code == 200:
                rdl_reports = resp_rdl.json().get("value", [])
                for r in rdl_reports:
                    r["Type"] = "Report"
                all_items.extend(rdl_reports)
                logger.info(f"PBIRS — {len(rdl_reports)} rapports paginés (.rdl) trouvés.")
            else:
                logger.warning(f"PBIRS /Reports → {resp_rdl.status_code}")

            if not all_items:
                logger.info("PBIRS connecté mais aucun rapport publié pour l'instant.")

            # Récupération des politiques de sécurité PBIRS (qui a le droit d'accès)
            folder_policies_cache = {}

            for item in all_items:
                item_id = item.get("Id", "")
                item_path = item.get("Path", "")
                principals = set()

                # 1. Vérifier si le rapport a ses propres Policies
                try:
                    p_resp = session.get(f"{settings.PBIRS_API_URL}/CatalogItems({item_id})/Policies", timeout=4)
                    if p_resp.status_code == 200:
                        p_data = p_resp.json()
                        inherit = p_data.get("InheritParentPolicy", True)
                        for pol in p_data.get("Policies", []):
                            gun = pol.get("GroupUserName", "")
                            cname = gun.split("\\")[-1].strip().upper()
                            if cname:
                                principals.add(cname)
                        if not inherit and principals:
                            item["allowed_principals"] = list(principals)
                            continue
                except Exception:
                    pass

                # 2. Si le rapport hérite, interroger les Policies de son dossier parent
                clean_parts = [p for p in item_path.strip("/").split("/") if p]
                if len(clean_parts) > 1:
                    parent_folder = clean_parts[0]
                    if parent_folder in folder_policies_cache:
                        principals.update(folder_policies_cache[parent_folder])
                    else:
                        try:
                            f_resp = session.get(f"{settings.PBIRS_API_URL}/Folders(Path='/{parent_folder}')/Policies", timeout=4)
                            if f_resp.status_code == 200:
                                f_data = f_resp.json()
                                f_principals = set()
                                for pol in f_data.get("Policies", []):
                                    gun = pol.get("GroupUserName", "")
                                    cname = gun.split("\\")[-1].strip().upper()
                                    if cname:
                                        f_principals.add(cname)
                                folder_policies_cache[parent_folder] = list(f_principals)
                                principals.update(f_principals)
                        except Exception:
                            folder_policies_cache[parent_folder] = []

                # 3. Interroger la racine "/" si besoin
                if "/" not in folder_policies_cache:
                    try:
                        r_resp = session.get(f"{settings.PBIRS_API_URL}/Folders(Path='/')/Policies", timeout=4)
                        if r_resp.status_code == 200:
                            r_data = r_resp.json()
                            r_principals = set()
                            for pol in r_data.get("Policies", []):
                                gun = pol.get("GroupUserName", "")
                                cname = gun.split("\\")[-1].strip().upper()
                                if cname:
                                    r_principals.add(cname)
                            folder_policies_cache["/"] = list(r_principals)
                    except Exception:
                        folder_policies_cache["/"] = []

                principals.update(folder_policies_cache.get("/", []))
                item["allowed_principals"] = list(principals)
                logger.info(f"Sécurité PBIRS pour '{item.get('Name')}' : autorisés = {list(principals)}")

            logger.info(f"PBIRS SSPI — {len(all_items)} rapports au total avec politiques de sécurité.")
            return all_items

        except ImportError:
            logger.error("Module 'requests-negotiate-sspi' manquant. pip install requests requests-negotiate-sspi")
            return []
        except Exception as e:
            logger.error(f"Erreur PBIRS SSPI: {type(e).__name__}: {e}")
            return []

    async def fetch_catalog_items(self) -> List[Dict[str, Any]]:
        """Récupère les éléments du catalogue PBIRS. Retourne les données mock si PBIRS_MOCK_MODE=True."""

        # --- Mode Mock : retourne les données de démo sans connexion réseau ---
        if settings.PBIRS_MOCK_MODE:
            logger.info("PBIRS_MOCK_MODE actif — utilisation des données de démonstration.")
            return INITIAL_BICEC_CATALOG

        # --- Connexion réelle via Windows SSPI (thread executor) ---
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            items = await loop.run_in_executor(None, self._fetch_catalog_sync)

            if not items:
                logger.info("Fallback sur les données de démonstration BICEC.")
                return INITIAL_BICEC_CATALOG

            # Interroger la base ReportServer SQL Server pour identifier les rapports masqués (Hidden = 1)
            hidden_item_ids = set()
            try:
                if not settings.REPORTSERVER_MOCK_MODE:
                    from app.services.admin_service import _get_sqlserver_connection
                    conn = _get_sqlserver_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT LOWER(CAST(ItemID AS VARCHAR(50))) FROM Catalog WHERE Hidden = 1")
                    for row in cursor.fetchall():
                        if row[0]:
                            hidden_item_ids.add(row[0].strip().lower())
                    conn.close()
                    logger.info(f"ReportServer SQL Server : {len(hidden_item_ids)} rapport(s) masqué(s) (Hidden=1) détecté(s).")
            except Exception as e_sql:
                logger.warning(f"Vérification SQL Server des rapports masqués : {e_sql}")

            reports = []
            for item in items:
                item_type = item.get("Type", "")
                if item_type not in ["PowerBIReport", "Report"]:
                    continue

                item_id_clean = str(item.get("Id", "")).strip().lower()

                # Ignorer les rapports masqués :
                # - Soit marqué Hidden=True par l'API PBIRS
                # - Soit marqué Hidden=1 dans la base SQL Server ReportServer (obsolescence 12 mois)
                if item.get("Hidden") is True or item_id_clean in hidden_item_ids:
                    logger.info(f"Rapport masqué / obsolète exclu du catalogue portail : {item.get('Name')} (ID={item_id_clean})")
                    continue

                path = item.get("Path", "")
                
                # Extraire le dossier parent comme Département/Pôle
                clean_parts = [p for p in path.strip("/").split("/") if p]
                if len(clean_parts) > 1:
                    category = clean_parts[0]  # Nom du dossier parent dans PBIRS
                else:
                    category = "Général"       # Rapport situé à la racine

                # Grouper les entités AD autorisées par PBIRS
                allowed_principals = item.get("allowed_principals", [])
                allowed_tag = f" | ALLOWED:{','.join(allowed_principals)}" if allowed_principals else ""

                reports.append({
                    "pbirs_id": item.get("Id"),
                    "name": item.get("Name"),
                    "path": path,
                    "description": item.get("Description") or "Rapport Power BI Report Server",
                    "category": category,
                    "department": category,
                    "tags": f"PowerBI, {item_type}, Auto-Synced{allowed_tag}",
                    "embed_url": f"{settings.PBIRS_SERVER_URL}/powerbi{path}",
                    "is_featured": False,
                })

            logger.info(f"PBIRS SSPI — {len(reports)} rapports Power BI visibles synchronisés.")
            return reports if reports else INITIAL_BICEC_CATALOG

        except Exception as e:
            logger.error(f"Erreur inattendue lors de la récupération PBIRS: {type(e).__name__}: {e}")

        logger.info("Fallback sur les données de démonstration BICEC.")
        return INITIAL_BICEC_CATALOG


# Instance singleton utilisée par les services
pbirs_client = PBIRSClient()
