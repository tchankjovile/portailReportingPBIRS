# Portail de Reporting Sur-Mesure PBIRS - BICEC

Ce dépôt contient le code source complet du **Portail de Reporting sur-mesure pour Power BI Report Server (PBIRS)** de la **BICEC** (Banque Internationale du Cameroun pour l'Épargne et le Crédit).

---

## 🚀 Stack Technique & Performance

L'application a été conçue pour être extrêmement légère, réactive et sécurisée :

- **Backend** : FastAPI (Python 3.10+) asynchrone pour des performances optimales.
- **Rendu Serveur (SSR)** : Jinja2 + HTMX pour des mises à jour dynamiques instantanées sans rechargement de page (HTML Over The Wire).
- **Interactivité Client** : Alpine.js (v3) pour la gestion fluide des modales, filtres et états UI sans dépendances lourdes.
- **Design System** : TailwindCSS avec intégration stricte des couleurs de la charte graphique institutionnelle **BICEC** :
  - **Orange BICEC** : `#E67900` (Pantone 1595 C)
  - **Chocolat BICEC** : `#491E06` (Pantone 7596 C)
- **Active Directory / SSO** : Authentification centralisée AD et support de l'authentification Windows (NTLM / Kerberos).
- **Sécurité RLS DAX** : Propagation automatique de l'identité utilisateur (`USERPRINCIPALNAME()` / `USERNAME()`) et injection dynamique de paramètres de filtrage DAX dans les iFrames PBIRS.

---

## 🛠️ Structure du Projet

```text
portailReportingPBIRS/
├── app/
│   ├── main.py                  # Initialisation FastAPI & Lifespan
│   ├── config.py                # Paramètres globaux, charte BICEC & URLs PBIRS/AD
│   ├── auth/
│   │   ├── ad_auth.py           # Authentification Active Directory LDAP & Personas
│   │   └── security.py          # Gestion des sessions JWT & Cookies HTTP-Only
│   ├── services/
│   │   ├── pbirs_client.py      # Client API REST PBIRS v2.0
│   │   └── report_service.py    # Logique RLS DAX, favoris, recherche & audit
│   ├── db/
│   │   ├── database.py          # Connexion SQLite / SQLAlchemy async
│   │   └── models.py            # Schéma (Report, Favorite, AuditLog, History)
│   ├── routers/
│   │   ├── pages.py             # Routes HTML principales
│   │   ├── reports.py           # Visionneur de rapports & RLS
│   │   └── api.py               # Endpoints réactifs HTMX
│   ├── static/
│   │   └── images/
│   │       └── bicec_logo.svg   # Logo vectoriel officiel BICEC
│   └── templates/
│       ├── base.html            # Layout principal avec Sidebar et Navbar
│       ├── components/          # Composants réactifs HTMX & Alpine.js
│       └── pages/               # Vues (Dashboard, Catalogue, Favoris, Login)
├── requirements.txt             # Dépendances Python
├── run.py                       # Lanceur Uvicorn
└── README.md                    # Manuel d'utilisation
```

---

## ⚡ Installation & Démarrage Rapide

### 1. Prérequis
- Python 3.10 ou version supérieure.

### 2. Installation des dépendances
```bash
pip install -r requirements.txt
```

### 3. Lancement de l'application
```bash
python run.py
```
Accédez au portail à l'adresse : [http://localhost:8000](http://localhost:8000)

---

## 🔒 Configuration du Row-Level Security (RLS) dans Power BI / DAX

Le portail supporte deux modes d'isolation des données :

### Mode 1 : NTLM & DAX `USERPRINCIPALNAME()` (Recommandé en Intranet)
Dans Power BI Desktop, définissez le rôle RLS avec la formule DAX :
```dax
[EmailUtilisateur] = USERPRINCIPALNAME()
```
Le serveur PBIRS applique automatiquement cette restriction en fonction du compte Windows de l'utilisateur connecté au portail.

### Mode 2 : Filtres DAX d'URL Dynamiques
Le portail génère automatiquement des paramètres d'URL injectés dans l'iFrame PBIRS :
```text
http://pbirs.bicec.local/Reports/powerbi/BICEC/Risques/Cartographie?rs:Embed=true&rc:Toolbar=false&filter=SecuriteDAX/Departement eq 'Risques'
```

---

## 👤 Contacts & Support
Pour toute question d'intégration avec l'infrastructure Power BI Report Server ou l'Active Directory de la BICEC, contactez l'équipe Développement & Bi.
