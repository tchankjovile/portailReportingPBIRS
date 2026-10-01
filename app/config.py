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
    
    # -----------------------------------------------------------------------
    # Groupes Active Directory disposant des droits Administrateur / Super-Utilisateur
    # (Accès complet aux rapports, démasquage, anomalies, console admin)
    # Configurable dans le fichier .env sous forme de liste séparée par des virgules :
    # ADMIN_GROUPS=PBIRS-ADMINS,Domain Admins,Administrators,GRP_DATA_BI,GRP_DIRECTION,GRP_DATA_ENGINEERS
    # -----------------------------------------------------------------------
    ADMIN_GROUPS: str = "PBIRS-ADMINS,Domain Admins,Administrators,GRP_DATA_BI,GRP_DIRECTION,GRP_DATA_ENGINEERS"

    def get_admin_groups(self) -> List[str]:
        """Retourne la liste normalisée des groupes AD ayant les droits administrateurs / pleins pouvoirs."""
        if isinstance(self.ADMIN_GROUPS, list):
            return [g.split("\\")[-1].strip().upper() for g in self.ADMIN_GROUPS]
        return [g.split("\\")[-1].strip().upper() for g in str(self.ADMIN_GROUPS).split(",") if g.strip()]

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

    # Database locale SQLite (chemin absolu basé sur la racine du projet pour éviter tout conflit de CWD)
    DATABASE_URL: str = f"sqlite+aiosqlite:///{os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bicec_portal.db').replace(os.sep, '/')}"

    def get_group_map(self) -> Dict[str, str]:
        """Méthode conservée pour compatibilité ascendante."""
        return {}

    def get_dept_hierarchy(self) -> Dict[str, List[str]]:
        """Méthode conservée pour compatibilité ascendante."""
        return {}

    def get_allowed_departments(self, user_departments: List[str]) -> List[str]:
        """Méthode conservée pour compatibilité ascendante."""
        return user_departments

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
