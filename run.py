import uvicorn
import os

if __name__ == "__main__":
    print("=" * 60)
    print("  PORTAIL DE REPORTING SUR-MESURE PBIRS - BICEC")
    print("  Stack: FastAPI + HTMX + AlpineJS + TailwindCSS")
    print("=" * 60)
    port = int(os.getenv("PORT", 8001))
    print(f"  Lancement du serveur sur : http://localhost:{port}")
    print("=" * 60)

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True
    )

