"""
app/main.py
Punto de entrada principal de la API.
Ensambla routers, CORS, rate limiting y lifespan.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from app.config import get_settings
from app.routers import auth, sync, tienda, dashboard

settings = get_settings()

# ── Rate limiter global ───────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"🚀 Gestion Total API — entorno: {settings.environment}")
    yield
    # Shutdown
    print("API detenida.")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Gestion Total API",
    description="API backend para el sistema de gestión web. Sync, catálogo y dashboard.",
    version="1.0.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    lifespan=lifespan,
)

# ── Rate limiter ──────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────
origins = [
    "http://localhost:5173",     # React dev (Vite)
    "http://localhost:3000",     # React dev alternativo
    "https://*.vercel.app",      # Previews de Vercel
]

if settings.is_production:
    # En producción podés agregar tu dominio real aquí
    origins.append("https://gestiontotalweb.com")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(sync.router)
app.include_router(tienda.router)
app.include_router(dashboard.router)

# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
async def health():
    """
    Liveness probe para Railway.
    También sirve para verificar conectividad desde el sync C#.
    """
    return {
        "status": "ok",
        "environment": settings.environment,
        "version": "1.0.0",
    }


@app.get("/", tags=["system"])
async def root():
    return {"mensaje": "Gestion Total API", "docs": "/docs"}
