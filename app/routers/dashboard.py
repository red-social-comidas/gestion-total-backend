"""
app/routers/dashboard.py
Endpoints del dashboard del operador.
Autenticación: JWT Bearer.
Prefijo: /api/v1/dashboard
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.usuario import TenantUsuario

from app.models.tenant import Tenant
from app.schemas.tenant import TenantUpdateSchema, TenantResponse

from app.models.pedido import PedidoWeb, EstadoPedidoEnum
from app.models.producto import ProductoWeb
from app.schemas.pedido import (
    PedidoCreate,
    PedidoResumen,
    PedidoResponse,
    KanbanResponse,
    CambioEstadoRequest,
    PedidoEditarRequest,
)
from decimal import Decimal
from app.schemas.producto import (
    ProductoDashboard,
    HabilitarWebRequest,
    DescripcionWebRequest,
)
from app.services.pedido_service import crear_pedido, cambiar_estado_pedido
from app.config import get_settings
import cloudinary
import cloudinary.uploader

settings = get_settings()
router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


# ── Kanban ────────────────────────────────────────────────────────────────────

@router.get("/pedidos/kanban", response_model=KanbanResponse)
async def get_kanban(
    current_user: TenantUsuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Devuelve todos los pedidos agrupados por estado (columnas del Kanban).
    Se refresca cada 30 segundos desde el portal.
    Solo muestra pedidos del tenant del usuario autenticado.
    """
    result = await db.execute(
        select(PedidoWeb)
        .where(PedidoWeb.tenant_id == current_user.tenant_id)
        .options(selectinload(PedidoWeb.items))
        .order_by(PedidoWeb.created_at.desc())
    )
    todos = result.scalars().all()

    kanban: dict[str, list] = {
        "por_confirmar":  [],
        "en_preparacion": [],
        "para_entregar":  [],
        "entregado":      [],
        "cancelado":      [],
    }
    for pedido in todos:
        kanban[pedido.estado.value].append(pedido)

    return KanbanResponse(**kanban)


@router.get("/pedidos", response_model=list[PedidoResponse])
async def listar_pedidos(
    estado: str | None = None,
    current_user: TenantUsuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista de pedidos con filtro opcional por estado."""
    query = (
        select(PedidoWeb)
        .where(PedidoWeb.tenant_id == current_user.tenant_id)
        .options(selectinload(PedidoWeb.items))
        .order_by(PedidoWeb.created_at.desc())
    )
    if estado:
        try:
            estado_enum = EstadoPedidoEnum(estado)
            query = query.where(PedidoWeb.estado == estado_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Estado inválido: {estado}")

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/pedidos/{pedido_id}", response_model=PedidoResponse)
async def get_pedido(
    pedido_id: uuid.UUID,
    current_user: TenantUsuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Detalle de un pedido."""
    result = await db.execute(
        select(PedidoWeb)
        .where(
            PedidoWeb.id == pedido_id,
            PedidoWeb.tenant_id == current_user.tenant_id,
        )
        .options(selectinload(PedidoWeb.items))
    )
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="pedido_not_found")
    return pedido


@router.patch("/pedidos/{pedido_id}/estado", response_model=PedidoResponse)
async def cambiar_estado(
    pedido_id: uuid.UUID,
    data: CambioEstadoRequest,
    current_user: TenantUsuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Cambia el estado de un pedido desde el Kanban.
    Valida las transiciones permitidas definidas en el modelo.
    """
    result = await db.execute(
        select(PedidoWeb)
        .where(
            PedidoWeb.id == pedido_id,
            PedidoWeb.tenant_id == current_user.tenant_id,
        )
        .options(selectinload(PedidoWeb.items))
    )
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="pedido_not_found")

    return await cambiar_estado_pedido(pedido, data.nuevo_estado, db)


# ── Pedidos manuales ──────────────────────────────────────────────────────────

@router.post("/pedidos", response_model=PedidoResumen, status_code=201)
async def crear_pedido_manual(
    data: PedidoCreate,
    current_user: TenantUsuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Carga manual de pedidos desde el dashboard.
    Origen = 'dashboard_manual'.
    El operador puede ingresar el DNI del cliente (ADR-010).
    """
    from app.models.tenant import Tenant
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == current_user.tenant_id)
    )
    tenant = tenant_result.scalar_one()

    data.origen = "dashboard_manual"
    return await crear_pedido(tenant, data, ip_cliente=None, db=db)


# ── Gestión de productos ──────────────────────────────────────────────────────

@router.get("/productos", response_model=list[ProductoDashboard])
async def listar_productos_dashboard(
    current_user: TenantUsuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista completa de productos para el dashboard (incluye deshabilitados)."""
    result = await db.execute(
        select(ProductoWeb)
        .where(ProductoWeb.tenant_id == current_user.tenant_id)
        .order_by(ProductoWeb.nombre.asc())
    )
    return result.scalars().all()


@router.patch("/productos/{producto_id}/habilitar", response_model=ProductoDashboard)
async def habilitar_producto_web(
    producto_id: uuid.UUID,
    data: HabilitarWebRequest,
    current_user: TenantUsuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Habilita o deshabilita un producto en el portal web."""
    result = await db.execute(
        select(ProductoWeb).where(
            ProductoWeb.id == producto_id,
            ProductoWeb.tenant_id == current_user.tenant_id,
        )
    )
    producto = result.scalar_one_or_none()
    if not producto:
        raise HTTPException(status_code=404, detail="producto_not_found")

    producto.habilitado_web = data.habilitado_web
    producto.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(producto)
    return producto


@router.patch("/productos/{producto_id}/descripcion", response_model=ProductoDashboard)
async def actualizar_descripcion_web(
    producto_id: uuid.UUID,
    data: DescripcionWebRequest,
    current_user: TenantUsuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza la descripción web de un producto (editable en el dashboard)."""
    result = await db.execute(
        select(ProductoWeb).where(
            ProductoWeb.id == producto_id,
            ProductoWeb.tenant_id == current_user.tenant_id,
        )
    )
    producto = result.scalar_one_or_none()
    if not producto:
        raise HTTPException(status_code=404, detail="producto_not_found")

    producto.descripcion_web = data.descripcion_web
    producto.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(producto)
    return producto


@router.post("/productos/{producto_id}/imagen", response_model=ProductoDashboard)
async def subir_imagen_producto(
    producto_id: uuid.UUID,
    imagen: UploadFile = File(...),
    current_user: TenantUsuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Sube una imagen a Cloudinary y actualiza imagen_url del producto.
    Requiere CLOUDINARY_* en las variables de entorno.
    """
    if not settings.cloudinary_configured:
        raise HTTPException(
            status_code=503,
            detail="Cloudinary no está configurado en este servidor.",
        )

    # Validar formato
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if imagen.content_type not in allowed:
        raise HTTPException(
            status_code=400,
            detail="Formato no soportado. Use JPG, PNG o WEBP.",
        )

    result = await db.execute(
        select(ProductoWeb).where(
            ProductoWeb.id == producto_id,
            ProductoWeb.tenant_id == current_user.tenant_id,
        )
    )
    producto = result.scalar_one_or_none()
    if not producto:
        raise HTTPException(status_code=404, detail="producto_not_found")

    # Configurar Cloudinary
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
    )

    # Eliminar imagen anterior si existe
    if producto.imagen_cloudinary_id:
        cloudinary.uploader.destroy(producto.imagen_cloudinary_id)

    # Subir nueva imagen
    content = await imagen.read()
    upload_result = cloudinary.uploader.upload(
        content,
        folder=f"gestion-total/{current_user.tenant_id}",
        public_id=f"producto_{producto.id_local}",
        overwrite=True,
        transformation=[
            {"width": 800, "height": 800, "crop": "limit"},
            {"quality": "auto"},
            {"fetch_format": "auto"},
        ],
    )

    producto.imagen_url = upload_result["secure_url"]
    producto.imagen_cloudinary_id = upload_result["public_id"]
    producto.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(producto)
    return producto

# ── Configuración del tenant ────────────────────────────────────────────────

@router.get("/config", response_model=TenantResponse)
async def get_config(
    current_user: TenantUsuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Devuelve la configuración completa del negocio (tenant):
    nombre, WhatsApp, config visual (logo, colores, horarios, etc).
    """
    result = await db.execute(
        select(Tenant).where(Tenant.id == current_user.tenant_id)
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="tenant_not_found")

    return tenant


@router.patch("/config", response_model=TenantResponse)
async def update_config(
    data: TenantUpdateSchema,
    current_user: TenantUsuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Actualiza la configuración del negocio.
    Permite modificar:
    - nombre_comercial
    - whatsapp_numero
    - config_visual (JSON: colores, logo, horarios, etc)
    """
    result = await db.execute(
        select(Tenant).where(Tenant.id == current_user.tenant_id)
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="tenant_not_found")

    # ── PATCH real (solo actualiza lo que viene) ───────────────────────────

    if data.nombre_comercial is not None:
        tenant.nombre_comercial = data.nombre_comercial

    if data.whatsapp_numero is not None:
        tenant.whatsapp_numero = data.whatsapp_numero

    if data.config_visual is not None:
        # Merge inteligente (no pisa todo el JSON)
        if tenant.config_visual:
            tenant.config_visual = {
                **tenant.config_visual,
                **data.config_visual,
            }
        else:
            tenant.config_visual = data.config_visual

    tenant.updated_at = datetime.now(timezone.utc)

    # ── Commit seguro con rollback ─────────────────────────────────────────

    try:
        await db.commit()
        await db.refresh(tenant)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="error_actualizando_configuracion"
        )

    return tenant


# ── Editar pedido (items, entrega, notas) ─────────────────────────────────────

@router.patch("/pedidos/{pedido_id}/editar", response_model=PedidoResponse)
async def editar_pedido(
    pedido_id: uuid.UUID,
    data: PedidoEditarRequest,
    current_user: TenantUsuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Edita un pedido existente desde el dashboard.
    Permite modificar: items, método de entrega, dirección, notas.
    Solo disponible para pedidos que no estén en estados terminales
    (entregado / cancelado).
    Recalcula subtotal y total automáticamente si se modifican los items.
    """
    from app.models.pedido import PedidoItem
    from app.models.producto import ProductoWeb
    from sqlalchemy import delete

    result = await db.execute(
        select(PedidoWeb)
        .where(
            PedidoWeb.id == pedido_id,
            PedidoWeb.tenant_id == current_user.tenant_id,
        )
        .options(selectinload(PedidoWeb.items))
    )
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="pedido_not_found")

    if pedido.estado.value in ("entregado", "cancelado"):
        raise HTTPException(
            status_code=400,
            detail="No se puede editar un pedido en estado terminal."
        )

    # ── Actualizar items si vienen ────────────────────────────────────────
    if data.items is not None:
        # Borrar items existentes
        await db.execute(
            delete(PedidoItem).where(PedidoItem.pedido_id == pedido.id)
        )

        subtotal = Decimal("0")
        nuevos_items = []
        for item_data in data.items:
            # Obtener datos actuales del producto para el snapshot
            res_prod = await db.execute(
                select(ProductoWeb).where(
                    ProductoWeb.tenant_id == current_user.tenant_id,
                    ProductoWeb.id_local  == item_data.id_producto_local,
                )
            )
            producto = res_prod.scalar_one_or_none()
            if not producto:
                raise HTTPException(
                    status_code=404,
                    detail=f"product_not_found:{item_data.id_producto_local}"
                )

            subtotal_item = producto.precio * item_data.cantidad
            subtotal += subtotal_item

            nuevos_items.append(
                PedidoItem(
                    pedido_id=pedido.id,
                    producto_id=producto.id,
                    id_producto_local=item_data.id_producto_local,
                    nombre_producto=producto.nombre,
                    codigo_barras=producto.codigo_barras,
                    precio_unitario=producto.precio,
                    cantidad=item_data.cantidad,
                    subtotal=subtotal_item,
                )
            )

        for item in nuevos_items:
            db.add(item)

        pedido.subtotal = subtotal

        # Recalcular total con costo de envío
        costo_envio = pedido.costo_envio or Decimal("0")
        if data.costo_envio is not None:
            costo_envio = data.costo_envio
        elif data.metodo_entrega == "retiro":
            costo_envio = Decimal("0")
        pedido.total = subtotal + costo_envio

    # ── Actualizar método de entrega ──────────────────────────────────────
    if data.metodo_entrega is not None:
        pedido.metodo_entrega = data.metodo_entrega
        if data.metodo_entrega == "retiro":
            pedido.costo_envio = Decimal("0")
            pedido.total = pedido.subtotal

    # ── Actualizar costo de envío explícito ───────────────────────────────
    if data.costo_envio is not None:
        pedido.costo_envio = data.costo_envio
        pedido.total = pedido.subtotal + data.costo_envio

    # ── Actualizar dirección ──────────────────────────────────────────────
    if data.direccion_entrega is not None:
        pedido.direccion_entrega = data.direccion_entrega

    # ── Actualizar notas ──────────────────────────────────────────────────
    if data.notas is not None:
        pedido.notas = data.notas if data.notas.strip() else None

    pedido.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(pedido)
    return pedido
