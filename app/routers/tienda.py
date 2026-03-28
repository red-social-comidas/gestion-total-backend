"""
app/routers/tienda.py
Endpoints públicos del portal web.
Sin autenticación. Rate limiting en el endpoint de pedidos.
Prefijo: /api/v1/tienda/{slug}
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.database import get_db
from app.models.tenant import Tenant
from app.models.producto import ProductoWeb
from app.models.categoria import CategoriaWeb
from app.models.pedido import PedidoWeb
from app.schemas.producto import ProductoCatalogoItem, CatalogoResponse, ProductoDetalle
from app.schemas.categoria import CategoriaResponse
from app.schemas.pedido import PedidoCreate, PedidoResumen, PedidoResponse
from app.services.pedido_service import crear_pedido

router = APIRouter(prefix="/api/v1/tienda", tags=["tienda"])
limiter = Limiter(key_func=get_remote_address)


# ── Helper: resolver tenant por slug ─────────────────────────────────────────

async def _get_tenant_activo(slug: str, db: AsyncSession) -> Tenant:
    result = await db.execute(
        select(Tenant).where(Tenant.slug == slug, Tenant.activo == True)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="tenant_not_found")
    return tenant


# ── Info de la tienda ─────────────────────────────────────────────────────────

@router.get("/{slug}/info")
async def get_info_tienda(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Información pública de la tienda (nombre, config_visual, horarios)."""
    tenant = await _get_tenant_activo(slug, db)
    return {
        "nombre_comercial": tenant.nombre_comercial,
        "whatsapp_numero":  tenant.whatsapp_numero,
        "config_visual":    tenant.config_visual,
    }


# ── Categorías ────────────────────────────────────────────────────────────────

@router.get("/{slug}/categorias", response_model=list[CategoriaResponse])
async def get_categorias(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Lista de categorías activas de la tienda."""
    tenant = await _get_tenant_activo(slug, db)
    result = await db.execute(
        select(CategoriaWeb)
        .where(CategoriaWeb.tenant_id == tenant.id, CategoriaWeb.activo == True)
        .order_by(CategoriaWeb.orden.asc(), CategoriaWeb.nombre.asc())
    )
    return result.scalars().all()


# ── Catálogo de productos ─────────────────────────────────────────────────────

@router.get("/{slug}/productos", response_model=CatalogoResponse)
async def get_productos(
    slug: str,
    categoria_id: uuid.UUID | None = Query(default=None),
    q: str | None = Query(default=None, min_length=2, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Catálogo público paginado.
    Filtra por categoría y/o búsqueda de texto.
    Solo muestra productos habilitados_web=True y activo_local=True.
    """
    tenant = await _get_tenant_activo(slug, db)

    # Query base
    base_query = (
        select(ProductoWeb)
        .where(
            ProductoWeb.tenant_id == tenant.id,
            ProductoWeb.habilitado_web == True,
            ProductoWeb.activo_local == True,
        )
    )

    # Filtro por categoría
    if categoria_id:
        base_query = base_query.where(ProductoWeb.categoria_id == categoria_id)

    # Búsqueda full-text
    if q:
        base_query = base_query.where(
            ProductoWeb.nombre.ilike(f"%{q}%")
        )

    # Total para paginación
    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = count_result.scalar_one()

    # Página
    offset = (page - 1) * page_size
    result = await db.execute(
        base_query
        .order_by(ProductoWeb.nombre.asc())
        .offset(offset)
        .limit(page_size)
    )
    productos = result.scalars().all()

    pages = (total + page_size - 1) // page_size if total > 0 else 1

    items = [
        ProductoCatalogoItem(
            id=p.id,
            id_local=p.id_local,
            nombre=p.nombre,
            precio=p.precio,
            imagen_url=p.imagen_url,
            stock_badge=p.stock_badge,
            categoria_id=p.categoria_id,
        )
        for p in productos
    ]

    return CatalogoResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{slug}/productos/{id_local}", response_model=ProductoDetalle)
async def get_producto_detalle(
    slug: str,
    id_local: int,
    db: AsyncSession = Depends(get_db),
):
    """Detalle completo de un producto."""
    tenant = await _get_tenant_activo(slug, db)
    result = await db.execute(
        select(ProductoWeb).where(
            ProductoWeb.tenant_id == tenant.id,
            ProductoWeb.id_local == id_local,
            ProductoWeb.habilitado_web == True,
            ProductoWeb.activo_local == True,
        )
    )
    producto = result.scalar_one_or_none()
    if not producto:
        raise HTTPException(status_code=404, detail="product_not_available")

    return ProductoDetalle(
        id=producto.id,
        id_local=producto.id_local,
        nombre=producto.nombre,
        precio=producto.precio,
        imagen_url=producto.imagen_url,
        stock_badge=producto.stock_badge,
        categoria_id=producto.categoria_id,
        codigo_barras=producto.codigo_barras,
        descripcion_web=producto.descripcion_web,
    )


# ── Pedidos ───────────────────────────────────────────────────────────────────

@router.post("/{slug}/pedidos", response_model=PedidoResumen, status_code=201)
@limiter.limit("10/hour")
async def crear_pedido_portal(
    request: Request,
    slug: str,
    data: PedidoCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Crea un pedido desde el portal web.
    Rate limit: 10 pedidos/hora por IP.
    El campo cliente_documento es opcional (ADR-010).
    """
    tenant = await _get_tenant_activo(slug, db)

    # Forzar origen portal_web — el dashboard usa su propio endpoint
    data.origen = "portal_web"

    ip = request.client.host if request.client else None
    pedido = await crear_pedido(tenant, data, ip, db)
    return pedido


@router.get("/{slug}/pedidos/{numero_pedido}", response_model=PedidoResponse)
async def get_pedido_por_numero(
    slug: str,
    numero_pedido: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Consulta el estado de un pedido por su número GTW-XXXXX.
    Usado por la página de confirmación del portal.
    """
    tenant = await _get_tenant_activo(slug, db)
    result = await db.execute(
        select(PedidoWeb)
        .where(
            PedidoWeb.tenant_id == tenant.id,
            PedidoWeb.numero_pedido == numero_pedido,
        )
        .options(selectinload(PedidoWeb.items))
    )
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="pedido_not_found")
    return pedido
