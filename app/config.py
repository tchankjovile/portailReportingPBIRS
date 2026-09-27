import os
from typing import List
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
    AD_ENABLE_DEV_MOCK: str = "true"  # Allows fallback mock login when AD DC is unreachable
    
    # Administration
    ADMIN_GROUPS: List[str] = ["PBIRS-ADMINS"]
    
    # Power BI Report Server Configuration
    PBIRS_SERVER_URL: str = "http://localhost/Reports"
    PBIRS_API_URL: str = "http://localhost/Reports/api/v2.0"
    PBIRS_MOCK_MODE: bool = True  # True = données fictives ; False = connexion PBIRS réelle
    # Compte de service NTLM pour se connecter au PBIRS (renseigné via .env)
    PBIRS_SERVICE_ACCOUNT: str = ""
    PBIRS_SERVICE_PASSWORD: str = ""
    
    # SQL Server — Base de données ReportServer PBIRS
    REPORTSERVER_SQL_SERVER: str = "localhost\\PBIRS"
    REPORTSERVER_DB: str = "ReportServer"
    REPORTSERVER_TRUSTED_CONN: bool = False   # False = SQL Auth (login/password)
    REPORTSERVER_SQL_USER: str = "tchank"
    REPORTSERVER_SQL_PASSWORD: str = "SQLroot"
    REPORTSERVER_MOCK_MODE: bool = True  # True = données fictives si SQL Server inaccessible

    # Database locale SQLite
    DATABASE_URL: str = "sqlite+aiosqlite:///./bicec_portal.db"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
