"""
app/services/pedido_service.py
Lógica de negocio para creación y gestión de pedidos.
"""
import uuid
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException
from app.models.pedido import PedidoWeb, PedidoItem, EstadoPedidoEnum
from app.models.producto import ProductoWeb
from app.models.tenant import Tenant
from app.schemas.pedido import PedidoCreate


async def crear_pedido(
    tenant: Tenant,
    data: PedidoCreate,
    ip_cliente: str | None,
    db: AsyncSession,
) -> PedidoWeb:
    """
    Crea un pedido en la base cloud.
    - Valida que cada producto exista y esté habilitado.
    - NO valida stock (ADR-007 v2 — modo diferido).
    - Genera número GTW-XXXXX único por tenant.
    - Calcula totales desde el precio real en productos_web.
    """
    numero = await _generar_numero_pedido(tenant.id, db)

    # ── Resolver costo de envío desde config_visual del tenant
    costo_envio = Decimal("0")
    if data.metodo_entrega == "domicilio":
        config = tenant.config_visual or {}
        costo_envio = Decimal(str(config.get("costo_envio_domicilio", 0)))

    # ── Construir items con precios reales
    subtotal = Decimal("0")
    items_a_crear: list[PedidoItem] = []

    for item_data in data.items:
        producto = await _obtener_producto_disponible(tenant.id, item_data.id_producto_local, db)
        subtotal_item = producto.precio * item_data.cantidad
        subtotal += subtotal_item

        items_a_crear.append(
            PedidoItem(
                producto_id=producto.id,
                id_producto_local=item_data.id_producto_local,
                nombre_producto=producto.nombre,
                codigo_barras=producto.codigo_barras,
                precio_unitario=producto.precio,
                cantidad=item_data.cantidad,
                subtotal=subtotal_item,
            )
        )

    total = subtotal + costo_envio

    # ── Crear el pedido
    pedido = PedidoWeb(
        tenant_id=tenant.id,
        numero_pedido=numero,
        origen=data.origen,
        cliente_nombre=data.cliente_nombre,
        cliente_celular=data.cliente_celular,
        cliente_email=data.cliente_email,
        cliente_documento=data.cliente_documento,
        metodo_entrega=data.metodo_entrega,
        direccion_entrega=data.direccion_entrega,
        costo_envio=costo_envio,
        notas=data.notas,
        subtotal=subtotal,
        total=total,
        ip_cliente=ip_cliente,
        items=items_a_crear,
    )

    db.add(pedido)
    await db.commit()
    await db.refresh(pedido)
    return pedido


async def cambiar_estado_pedido(
    pedido: PedidoWeb,
    nuevo_estado: EstadoPedidoEnum,
    db: AsyncSession,
) -> PedidoWeb:
    """
    Cambia el estado del pedido validando las transiciones del Kanban.
    """
    if not pedido.puede_transicionar_a(nuevo_estado):
        raise HTTPException(
            status_code=400,
            detail=f"Transición inválida: {pedido.estado} → {nuevo_estado}",
        )
    pedido.estado = nuevo_estado
    await db.commit()
    await db.refresh(pedido)
    return pedido


async def _generar_numero_pedido(tenant_id: uuid.UUID, db: AsyncSession) -> str:
    """
    Genera GTW-XXXXX secuencial por tenant.
    Usa COUNT para evitar gaps visibles al cliente.
    NOTA: en producción con alto volumen, migrar a SEQUENCE de Postgres.
    """
    result = await db.execute(
        select(func.count(PedidoWeb.id)).where(PedidoWeb.tenant_id == tenant_id)
    )
    count = result.scalar_one()
    return f"GTW-{(count + 1):05d}"


async def _obtener_producto_disponible(
    tenant_id: uuid.UUID,
    id_producto_local: int,
    db: AsyncSession,
) -> ProductoWeb:
    """
    Obtiene un producto que esté habilitado en el portal.
    Si no existe o no está habilitado → 404.
    """
    result = await db.execute(
        select(ProductoWeb).where(
            ProductoWeb.tenant_id == tenant_id,
            ProductoWeb.id_local == id_producto_local,
            ProductoWeb.habilitado_web == True,
            ProductoWeb.activo_local == True,
        )
    )
    producto = result.scalar_one_or_none()
    if not producto:
        raise HTTPException(
            status_code=404,
            detail=f"product_not_available:{id_producto_local}",
        )
    return producto
