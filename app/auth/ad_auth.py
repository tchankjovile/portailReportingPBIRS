import logging
from typing import Dict, Any, Optional
from app.config import settings

logger = logging.getLogger(__name__)

# Pre-defined AD Corporate Profiles for BICEC Reporting Personas
DEMO_AD_USERS = {
    "e.tchana": {
        "upn": "e.tchana@bicec.cm",
        "username": "e.tchana",
        "display_name": "Emmanuel TCHANA",
        "title": "Analyste Senior Risques & Crédits",
        "department": "Gestion des Risques",
        "email": "e.tchana@bicec.cm",
        "agency": "Agence Centrale Douala",
        "role": "Analyste Risques",
        "groups": ["BICEC-RISK-ANALYSTS", "BICEC-HEAD-OFFICE", "PBIRS-POWER-USERS"],
        "dax_security_key": "DOUALA_RISK_DIV",
    },
    "m.eboko": {
        "upn": "m.eboko@bicec.cm",
        "username": "m.eboko",
        "display_name": "Marie-Claire EBOKO",
        "title": "Directrice du Contrôle de Gestion",
        "department": "Finance & Comptabilité",
        "email": "m.eboko@bicec.cm",
        "agency": "Siège Yaoundé",
        "role": "Directrice Finance",
        "groups": ["BICEC-FINANCE-EXECS", "BICEC-MANAGEMENT", "PBIRS-ADMINS"],
        "dax_security_key": "ALL_BRANCHES_FINANCE",
    },
    "a.ngassam": {
        "upn": "a.ngassam@bicec.cm",
        "username": "a.ngassam",
        "display_name": "Alain NGASSAM",
        "title": "Chef d'Agence Bafoussam",
        "department": "Opérations Bancaires",
        "email": "a.ngassam@bicec.cm",
        "agency": "Agence Bafoussam",
        "role": "Chef d'Agence",
        "groups": ["BICEC-BRANCH-MANAGERS", "BICEC-WEST-REGION"],
        "dax_security_key": "AGENCY_BAFOUSSAM_004",
    },
    "s.kengne": {
        "upn": "s.kengne@bicec.cm",
        "username": "s.kengne",
        "display_name": "Solange KENGNE",
        "title": "Auditeur Interne Principal",
        "department": "Audit & Conformité",
        "email": "s.kengne@bicec.cm",
        "agency": "Siège Douala",
        "role": "Auditeur Interne",
        "groups": ["BICEC-AUDIT-TEAM", "BICEC-COMPLIANCE"],
        "dax_security_key": "GLOBAL_AUDIT_READ",
    }
}

class ActiveDirectoryClient:
    """
    Active Directory Authentication and User Directory Resolver.
    Supports live LDAP authentication against domain controller or mock AD verification.
    """

    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        # Clean username (strip domain if provided)
        clean_user = username.split("\\")[-1].split("@")[0].lower()

        # If live LDAP is disabled or running in mock mode:
        if settings.AD_ENABLE_DEV_MOCK.lower() == "true":
            if clean_user in DEMO_AD_USERS:
                user_info = DEMO_AD_USERS[clean_user].copy()
                user_info["is_authenticated"] = True
                return user_info
            
            # Fallback for any custom username entered
            return {
                "upn": f"{clean_user}@bicec.cm",
                "username": clean_user,
                "display_name": clean_user.capitalize() + " (AD User)",
                "title": "Utilisateur Active Directory",
                "department": "Direction Générale",
                "email": f"{clean_user}@bicec.cm",
                "agency": "Siège Social",
                "role": "Utilisateur Métier",
                "groups": ["BICEC-EMPLOYEES", "PBIRS-VIEWERS"],
                "dax_security_key": "STANDARD_USER",
                "is_authenticated": True
            }

        # Live LDAP binding logic against Active Directory Domain Controller
        try:
            from ldap3 import Server, Connection, SIMPLE, SYNC, ALL
            server = Server(settings.AD_LDAP_SERVER, get_info=ALL)
            user_dn = f"{clean_user}@{settings.AD_DOMAIN}"
            conn = Connection(server, user=user_dn, password=password, authentication=SIMPLE, check_names=True, lazy=False)
            
            if conn.bind():
                conn.unbind()
                return DEMO_AD_USERS.get(clean_user, {
                    "upn": user_dn,
                    "username": clean_user,
                    "display_name": clean_user.upper(),
                    "title": "Employé BICEC",
                    "department": "Général",
                    "email": user_dn,
                    "agency": "BICEC",
                    "role": "Employé",
                    "groups": ["BICEC-USERS"],
                    "dax_security_key": "DEFAULT",
                    "is_authenticated": True
                })
        except Exception as e:
            logger.error(f"Active Directory LDAP bind failed: {e}")
            
        return None

ad_client = ActiveDirectoryClient()
