from fastapi import APIRouter, Request, Depends, Form, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.auth.security import require_authenticated_user, get_current_user_from_request, create_access_token
from app.auth.ad_auth import ad_client
from app.services.report_service import report_service
from app.config import settings

router = APIRouter(prefix="/api", tags=["API HTMX"])


@router.get("/search", response_class=HTMLResponse)
async def live_search(
    request: Request,
    q: str = "",
    dept: str = "Tous",
    db: AsyncSession = Depends(get_db)
):
    from app.auth.security import is_admin
    from app.templates_env import templates
    user = require_authenticated_user(request)
    reports = await report_service.get_all_reports(db, department=dept, search_query=q, user_upn=user.get("upn"), user=user)

    return templates.TemplateResponse(
        "components/search_results.html",
        {
            "request": request,
            "reports": reports,
            "search_query": q,
            "selected_dept": dept,
            "user": user,
            "is_admin": is_admin(user),
        }
    )


@router.post("/favorites/toggle/{report_id}", response_class=HTMLResponse)
async def toggle_favorite_api(
    request: Request,
    report_id: int,
    db: AsyncSession = Depends(get_db)
):
    user = require_authenticated_user(request)
    is_fav = await report_service.toggle_favorite(db, report_id, user.get("upn"))

    heart_color = "fill-[#E67900] text-[#E67900]" if is_fav else "fill-none text-gray-400 hover:text-[#E67900]"
    title_text = "Retirer des favoris" if is_fav else "Ajouter aux favoris"

    return HTMLResponse(content=f"""
    <button hx-post="/api/favorites/toggle/{report_id}"
            hx-target="this"
            hx-swap="outerHTML"
            title="{title_text}"
            class="p-2 rounded-full hover:bg-orange-50 transition-colors duration-200">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6 {heart_color} transition-all duration-300 transform hover:scale-110" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
        </svg>
    </button>
    """)


@router.post("/anomalies/submit", response_class=HTMLResponse)
async def submit_anomaly(
    request: Request,
    report_id: int = Form(...),
    report_name: str = Form(...),
    report_path: str = Form(""),
    description: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint HTMX pour soumettre un signalement d'anomalie.
    Accessible à tous les utilisateurs authentifiés.
    """
    user = require_authenticated_user(request)

    if not description.strip():
        return HTMLResponse("""
        <div class="flex items-center gap-2 text-red-600 text-sm font-semibold p-3 bg-red-50 rounded-xl border border-red-200">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            Veuillez décrire l'anomalie avant d'envoyer.
        </div>
        """)

    await report_service.submit_anomaly(
        db=db,
        report_id=report_id if report_id else None,
        report_name=report_name,
        report_path=report_path,
        user_upn=user.get("upn", ""),
        user_name=user.get("display_name", ""),
        user_dept=user.get("department", ""),
        description=description.strip()
    )

    return HTMLResponse("""
    <div id="anomaly-success" class="flex flex-col items-center gap-3 py-4 text-center">
        <div class="w-14 h-14 rounded-full bg-emerald-100 flex items-center justify-center">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-7 h-7 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
            </svg>
        </div>
        <p class="font-bold text-gray-900 text-sm">Signalement envoyé avec succès</p>
        <p class="text-xs text-gray-500">Notre équipe d'administration prendra en charge votre signalement dans les plus brefs délais.</p>
    </div>
    """)


@router.post("/auth/login")
async def login(
    username: str = Form(...),
    password: str = Form(...),
    response: Response = None
):
    """
    Authentification AD : valide les credentials et crée une session JWT.
    Obligatoire pour tous les utilisateurs.
    """
    user_info = ad_client.authenticate_user(username, password)
    if not user_info:
        from app.templates_env import templates
        from starlette.requests import Request
        raise HTTPException(status_code=401, detail="Identifiants Active Directory incorrects. Vérifiez votre nom d'utilisateur et mot de passe.")

    token = create_access_token(user_info)
    redirect = RedirectResponse(url="/", status_code=303)
    redirect.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax"
    )
    return redirect


@router.get("/auth/logout")
async def logout():
    redirect = RedirectResponse(url="/login", status_code=303)
    redirect.delete_cookie(key=settings.COOKIE_NAME)
    return redirect


@router.post("/auth/switch-persona/{persona_key}")
async def switch_persona(persona_key: str):
    """
    Connexion rapide avec l'un des profils de démonstration (Emmanuel, Marie-Claire, Alain, Solange).
    """
    from app.auth.ad_auth import DEMO_AD_USERS
    if persona_key not in DEMO_AD_USERS:
        raise HTTPException(status_code=404, detail="Profil de démonstration introuvable.")

    user_info = DEMO_AD_USERS[persona_key].copy()
    user_info["is_authenticated"] = True
    token = create_access_token(user_info)
    redirect = RedirectResponse(url="/", status_code=303)
    redirect.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax"
    )
    return redirect

