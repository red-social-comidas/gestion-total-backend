"""
tests/conftest.py
Fixtures compartidas para todos los tests.
Usa base de datos de test separada.
"""
import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import app
from app.database import Base, get_db
from app.models import *  # noqa: F401
from app.services.auth_service import hash_password
import uuid

# ⚠️ IMPORTANTE: evitar :memory: con async
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"


# ─────────────────────────────────────────────────────────────
# Event loop (necesario para pytest-asyncio)
# ─────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ─────────────────────────────────────────────────────────────
# Engine de test
# ─────────────────────────────────────────────────────────────
@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


# ─────────────────────────────────────────────────────────────
# Sesión de DB por test (aislada)
# ─────────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def db_session(test_engine):
    TestSession = async_sessionmaker(test_engine, expire_on_commit=False)

    async with TestSession() as session:
        yield session
        await session.rollback()


# ─────────────────────────────────────────────────────────────
# Cliente HTTP
# ─────────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ─────────────────────────────────────────────────────────────
# Seed de tenant + usuario REALISTA
# ─────────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def tenant_seed(db_session: AsyncSession):
    from app.models.tenant import Tenant
    from app.models.usuario import TenantUsuario

    password_plano = "configuracion1"

    tenant = Tenant(
        id=uuid.uuid4(),  # ✅ mejor que fijo
        slug="mi-negocio",
        nombre_comercial="Mi Negocio",
        whatsapp_numero="5493735479602",
        email_contacto="frefirerafa1@gmail.com",
        sync_api_key="916390d951e275d89ce76eab691ecfaf804c20d8663f29a4f085c90aa30c12c0",
        config_visual={
            "color_acento": "#2E75B6",
            "acepta_retiro": True,
            "horario_cierre": "18:00",
            "direccion_local": "Av. Siempreviva 742, Resistencia",
            "acepta_domicilio": True,
            "horario_apertura": "09:00",
            "envio_gratis_desde": 0,
            "mensaje_bienvenida": "Bienvenidos a nuestra tienda",
            "costo_envio_domicilio": 0,
        },
        activo=True,
    )
    db_session.add(tenant)
    await db_session.flush()

    usuario = TenantUsuario(
        tenant_id=tenant.id,
        nombre="Admin",
        email="frefirerafa1@gmail.com",
        password_hash=hash_password(password_plano),
        rol="admin",
        activo=True,
    )
    db_session.add(usuario)

    await db_session.commit()

    return {
        "tenant": tenant,
        "usuario": usuario,
        "password": password_plano,
    }


# ─────────────────────────────────────────────────────────────
# Seed de producto (realista)
# ─────────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def producto_seed(db_session: AsyncSession, tenant_seed):
    from app.models.producto import ProductoWeb

    producto = ProductoWeb(
        tenant_id=tenant_seed["tenant"].id,
        id_local=18,
        codigo_barras="7791843020760",
        codigo_interno="0760",
        nombre="VINO BLANCO CONEJO VERDE 750MLS",
        precio=5900.00,
        stock_actual=99,
        stock_minimo=1,
        habilitado_web=True,
        activo_local=True,
    )
    db_session.add(producto)
    await db_session.commit()

    return producto