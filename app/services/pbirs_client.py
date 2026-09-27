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
    Récupère le catalogue avec authentification NTLM (Windows).
    Fallback automatique sur les données de démo en cas d'échec.
    """

    async def fetch_catalog_items(self) -> List[Dict[str, Any]]:
        """Récupère les éléments du catalogue PBIRS. Retourne les données mock si PBIRS_MOCK_MODE=True."""

        # --- Mode Mock : retourne les données de démo sans connexion réseau ---
        if settings.PBIRS_MOCK_MODE:
            logger.info("PBIRS_MOCK_MODE actif — utilisation des données de démonstration.")
            return INITIAL_BICEC_CATALOG

        # --- Connexion réelle au serveur PBIRS avec authentification NTLM ---
        try:
            ntlm_credential = f"{settings.AD_DOMAIN}\\{settings.PBIRS_SERVICE_ACCOUNT}"
            auth = HttpNtlmAuth(ntlm_credential, settings.PBIRS_SERVICE_PASSWORD)

            logger.info(f"Connexion PBIRS → {settings.PBIRS_API_URL} (compte: {ntlm_credential})")

            async with httpx.AsyncClient(
                auth=auth,
                timeout=15.0,
                verify=False,
                follow_redirects=True,
            ) as client:
                response = await client.get(f"{settings.PBIRS_API_URL}/CatalogItems")

                if response.status_code == 401:
                    logger.error(
                        "PBIRS a refusé l'authentification (401). "
                        "Vérifiez AD_DOMAIN, PBIRS_SERVICE_ACCOUNT et PBIRS_SERVICE_PASSWORD dans .env"
                    )
                    return INITIAL_BICEC_CATALOG

                response.raise_for_status()
                items = response.json().get("value", [])
                logger.info(f"PBIRS — {len(items)} éléments récupérés depuis le catalogue.")

                reports = []
                for item in items:
                    item_type = item.get("Type", "")
                    if item_type not in ["PowerBIReport", "Report"]:
                        continue
                    path = item.get("Path", "")
                    path_parts = path.split("/")
                    category = path_parts[2] if len(path_parts) > 2 else "Général"
                    reports.append({
                        "pbirs_id": item.get("Id"),
                        "name": item.get("Name"),
                        "path": path,
                        "description": item.get("Description") or "Rapport Power BI Report Server",
                        "category": category,
                        "department": category,
                        "tags": f"PowerBI, {item_type}, Auto-Synced",
                        "embed_url": f"{settings.PBIRS_SERVER_URL}/powerbi{path}",
                        "is_featured": False,
                    })

                logger.info(f"PBIRS — {len(reports)} rapports filtrés.")
                return reports if reports else INITIAL_BICEC_CATALOG

        except httpx.ConnectError as e:
            logger.warning(f"Impossible de joindre PBIRS ({settings.PBIRS_API_URL}). Service démarré ? Erreur: {e}")
        except httpx.TimeoutException as e:
            logger.warning(f"Délai dépassé pour PBIRS. Erreur: {e}")
        except Exception as e:
            logger.error(f"Erreur inattendue PBIRS: {type(e).__name__}: {e}")

        logger.info("Fallback sur les données de démonstration BICEC.")
        return INITIAL_BICEC_CATALOG


# Instance singleton utilisée par les services
pbirs_client = PBIRSClient()
