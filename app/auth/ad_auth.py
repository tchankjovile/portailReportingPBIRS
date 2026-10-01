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

        # Live Windows Native Authentication against Active Directory
        try:
            import win32security
            
            # LogonUser vérifie les credentials directement via l'OS Windows
            token = win32security.LogonUser(
                clean_user,
                settings.AD_DOMAIN,
                password,
                win32security.LOGON32_LOGON_NETWORK,
                win32security.LOGON32_PROVIDER_DEFAULT
            )
            
            # Récupérer les groupes AD réels :
            # 1. Directement depuis le jeton de sécurité Windows de l'utilisateur (méthode la plus fiable)
            ad_groups = _get_groups_from_token(token)
            
            # 2. Compléter via win32net si disponible
            if not ad_groups:
                ad_groups = _get_user_ad_groups(clean_user, settings.AD_DOMAIN)
            
            logger.info(f"Groupes AD réels détectés pour '{clean_user}' : {ad_groups}")

            # Identifier le groupe métier principal en ignorant les groupes techniques Windows par défaut
            ignored_groups = {
                "DOMAIN USERS", "UTILISATEURS DU DOMAINE", "EVERYONE", "TOUT LE MONDE",
                "USERS", "UTILISATEURS", "AUTHENTICATED USERS", "UTILISATEURS AUTHENTIFIES"
            }
            business_groups = [
                g.split("\\")[-1].strip()
                for g in ad_groups
                if g.split("\\")[-1].strip().upper() not in ignored_groups
            ]
            primary_ad_group = business_groups[0] if business_groups else (ad_groups[0].split("\\")[-1].strip() if ad_groups else "Utilisateur")

            logger.info(f"Groupe AD principal attribué pour '{clean_user}' : {primary_ad_group}")

            # Construire le profil utilisateur
            user_dn = f"{clean_user}@{settings.AD_DOMAIN}"
            base_profile = DEMO_AD_USERS.get(clean_user, {
                "upn": user_dn,
                "username": clean_user,
                "display_name": clean_user.upper(),
                "title": f"Groupe AD : {primary_ad_group}",
                "email": user_dn,
                "agency": "BICEC",
                "role": "Collaborateur",
                "dax_security_key": "DEFAULT",
            })
            
            # Mettre à jour avec les informations dynamiques réelles de l'AD (sans table de correspondance)
            base_profile.update({
                "department": primary_ad_group,
                "ad_group": primary_ad_group,
                "groups": ad_groups,
                "is_authenticated": True
            })
            return base_profile

        except Exception as e:
            logger.error(f"Active Directory native logon failed: {e}")
            
        return None


def _get_groups_from_token(token) -> List[str]:
    """
    Extrait tous les groupes de sécurité Windows directement depuis le Token Handle
    retourné par LogonUser. Fonctionne sur serveur membre sans accès administrateur SAM.
    """
    groups = []
    try:
        import win32security
        token_groups = win32security.GetTokenInformation(token, win32security.TokenGroups)
        for sid, _ in token_groups:
            try:
                name, domain, _ = win32security.LookupAccountSid(None, sid)
                if name and name not in groups:
                    groups.append(name)
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Erreur extraction groupes du token: {e}")
    return groups


def _get_user_ad_groups(username: str, domain: str) -> List[str]:
    """
    Récupère les groupes AD via win32net en interrogeant le Domain Controller.
    """
    try:
        import win32net
        groups = []
        
        # Interroger le DC du domaine
        try:
            dc = win32net.NetGetDCName(None, domain)
            domain_groups, _, _ = win32net.NetUserGetGroups(dc, username)
            groups.extend([g[0] for g in domain_groups if g[0] not in groups])
        except Exception:
            pass
        
        # Groupes locaux
        try:
            local_groups, _, _ = win32net.NetUserGetLocalGroups(None, username, 0)
            groups.extend([g for g in local_groups if g not in groups])
        except Exception:
            pass
        
        return groups
    except Exception as e:
        logger.warning(f"win32net get groups failed: {e}")
        return []


# Singleton utilisé par les routers
ad_client = ActiveDirectoryClient()
