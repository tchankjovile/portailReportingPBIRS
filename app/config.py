import os
import json
from typing import List, Dict
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "BICEC Reporting Portal"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Institution Branding
    BANK_NAME: str = "BICEC"
    COLOR_PRIMARY_ORANGE: str = "#E67900"
    COLOR_PRIMARY_CHOCOLATE: str = "#491E06"
    
    # Security & Authentication
    SECRET_KEY: str = "bicec-secret-key-pbirs-reporting-2026-super-secure"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours session
    COOKIE_NAME: str = "bicec_session"
    
    # Active Directory / LDAP Settings
    AD_DOMAIN: str = "bicec.local"
    AD_LDAP_SERVER: str = "ldap://dc01.bicec.local"
    AD_ENABLE_DEV_MOCK: str = "true"
    
    # Administration
    ADMIN_GROUPS: List[str] = ["PBIRS-ADMINS", "Domain Admins", "Administrators"]

    # -----------------------------------------------------------------------
    # Mapping Groupe AD (nom technique) → Département PBIRS (nom affiché)
    # Modifiable dans .env sous forme JSON :
    # AD_GROUP_TO_DEPT_MAP={"GRP-FINANCE": "Finance & Comptabilité", ...}
    # -----------------------------------------------------------------------
    # -----------------------------------------------------------------------
    # Mapping Groupe AD (nom technique) → Département PBIRS (nom affiché)
    # Modifiable dans .env sous forme JSON
    # -----------------------------------------------------------------------
    AD_GROUP_TO_DEPT_MAP: str = json.dumps({
        "GRP_DIRECTION":        "Direction Générale",
        "GRP_DATA_BI":          "Data & Business Intelligence",
        "GRP_FINANCE":          "Finance",
        "GRP_COMPTA":           "Comptabilité",
        "GRP_IT_ADMIN":         "Administration IT",
        "Domain Admins":        "Direction Générale",
        "Administrators":       "Direction Générale",
        "PBIRS-ADMINS":         "Direction Générale"
    })

    # -----------------------------------------------------------------------
    # Hiérarchie des départements PBIRS :
    # Un pôle parent permet de voir son contenu + celui de tous ses sous-pôles.
    # Direction Générale voit tout le catalogue et tous les pôles.
    # -----------------------------------------------------------------------
    DEPT_HIERARCHY: str = json.dumps({
        "Direction Générale":            ["Finance", "Comptabilité", "Data & Business Intelligence", "Administration IT", "01_Conception"],
        "Finance":                       ["Comptabilité"],
        "Comptabilité":                  [],
        "Data & Business Intelligence":   ["01_Conception"],
        "Administration IT":             [],
        "01_Conception":                 []
    })

    # Power BI Report Server Configuration
    PBIRS_SERVER_URL: str = "http://localhost/Reports"
    PBIRS_API_URL: str = "http://localhost/Reports/api/v2.0"
    PBIRS_MOCK_MODE: bool = True
    PBIRS_SERVICE_ACCOUNT: str = ""
    PBIRS_SERVICE_PASSWORD: str = ""
    
    # SQL Server — Base de données ReportServer PBIRS
    REPORTSERVER_SQL_SERVER: str = "172.16.0.4\\SQLEXPRESS01"
    REPORTSERVER_DB: str = "ReportServer"
    REPORTSERVER_TRUSTED_CONN: bool = True   # True = Windows Authentication via session courante
    REPORTSERVER_SQL_USER: str = ""          # Renseigné si SQL Auth (ex: sa)
    REPORTSERVER_SQL_PASSWORD: str = ""
    REPORTSERVER_MOCK_MODE: bool = False     # False = Connexion réelle à la base ReportServer

    # Database locale SQLite
    DATABASE_URL: str = "sqlite+aiosqlite:///./bicec_portal.db"

    def get_group_map(self) -> Dict[str, str]:
        """Retourne le mapping groupe AD → département PBIRS."""
        return json.loads(self.AD_GROUP_TO_DEPT_MAP)

    def get_dept_hierarchy(self) -> Dict[str, List[str]]:
        """Retourne la hiérarchie des départements."""
        return json.loads(self.DEPT_HIERARCHY)

    def get_allowed_departments(self, user_departments: List[str]) -> List[str]:
        """
        Calcule la liste complète des départements visibles par un utilisateur
        en fonction de ses départements directs et de la hiérarchie.
        Direction Générale (ou liste vide dans hierarchy) = accès à tout.
        """
        hierarchy = self.get_dept_hierarchy()
        allowed = set(user_departments)

        # Direction Générale et Data & Business Intelligence ont accès à TOUT
        if "Direction Générale" in user_departments or "Data & Business Intelligence" in user_departments:
            return list(hierarchy.keys())  # Accès total à tous les pôles et rapports

        # Ajouter les sous-départements autorisés pour les autres métiers
        for dept in list(allowed):
            children = hierarchy.get(dept, [])
            allowed.update(children)

        return list(allowed)

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
