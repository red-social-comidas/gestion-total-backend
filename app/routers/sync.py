"""
app/routers/sync.py
Endpoints exclusivos del servicio de Sync C# WinForms.
Autenticación: X-Sync-Api-Key en header.
Prefijo: /api/v1/sync
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.dependencies.sync_auth import verify_sync_api_key
from app.models.tenant import Tenant
from app.models.pedido import PedidoWeb, PedidoItem
from app.models.sync_log import SyncLog
from app.schemas.producto import ProductosBatchPayload, SyncBatchResponse
from app.schemas.categoria import CategoriasBatchPayload
from app.schemas.pedido import (
    PedidoResponse,
    PedidoSincronizadoUpdate,
    PedidoEstadoSyncUpdate,
)
from app.services.sync_service import upsert_productos, upsert_categorias

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])


# ── Estado general del sync ───────────────────────────────────────────────────

@router.get("/estado")
async def get_estado_sync(
    tenant: Tenant = Depends(verify_sync_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Devuelve el estado actual de la sincronización.
    El C# llama a este endpoint al arrancar para verificar conectividad.
    """
    # Últimas entradas del log
    result = await db.execute(
        select(SyncLog)
        .where(SyncLog.tenant_id == tenant.id)
        .order_by(SyncLog.created_at.desc())
        .limit(5)
    )
    logs = result.scalars().all()

    # Conteo de pedidos pendientes de bajar
    result_pendientes = await db.execute(
        select(PedidoWeb)
        .where(
            PedidoWeb.tenant_id == tenant.id,
            PedidoWeb.sync_bajado == False,
        )
    )
    pendientes = len(result_pendientes.scalars().all())

    return {
        "tenant_slug": tenant.slug,
        "tenant_nombre": tenant.nombre_comercial,
        "pedidos_pendientes_bajar": pendientes,
        "server_time": datetime.now(timezone.utc).isoformat(),
        "ultimos_logs": [
            {
                "tipo": log.tipo,
                "direccion": log.direccion,
                "estado": log.estado,
                "registros": log.registros,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
    }


# ── Subida de productos ───────────────────────────────────────────────────────

@router.post("/productos", response_model=SyncBatchResponse)
async def sync_productos(
    payload: ProductosBatchPayload,
    tenant: Tenant = Depends(verify_sync_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Recibe un batch de hasta 500 productos desde SQL Server.
    Hace upsert en productos_web.
    NO sobreescribe: descripcion_web, imagen_url, habilitado_web.
    """
    return await upsert_productos(tenant.id, payload, db)


# ── Subida de categorías ──────────────────────────────────────────────────────

@router.post("/categorias")
async def sync_categorias(
    payload: CategoriasBatchPayload,
    tenant: Tenant = Depends(verify_sync_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Recibe categorías desde SQL Server y las sincroniza en Postgres."""
    return await upsert_categorias(tenant.id, payload, db)


# ── Bajada de pedidos ─────────────────────────────────────────────────────────

@router.get("/pedidos/pendientes", response_model=list[PedidoResponse])
async def get_pedidos_pendientes(
    tenant: Tenant = Depends(verify_sync_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Devuelve los pedidos que NO han bajado a SQL Server todavía.
    El sync C# los consume, los inserta en VENTA, y luego llama
    a PATCH /pedidos/{id}/sincronizado para marcarlos.
    """
    result = await db.execute(
        select(PedidoWeb)
        .where(
            PedidoWeb.tenant_id == tenant.id,
            PedidoWeb.sync_bajado == False,
        )
        .options(selectinload(PedidoWeb.items))
        .order_by(PedidoWeb.created_at.asc())
    )
    return result.scalars().all()


@router.patch("/pedidos/{pedido_id}/sincronizado")
async def marcar_pedido_sincronizado(
    pedido_id: uuid.UUID,
    data: PedidoSincronizadoUpdate,
    tenant: Tenant = Depends(verify_sync_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    El sync C# llama a este endpoint después de insertar el pedido
    en SQL Server. Marca sync_bajado=True y guarda el IdVenta local.
    """
    result = await db.execute(
        select(PedidoWeb).where(
            PedidoWeb.id == pedido_id,
            PedidoWeb.tenant_id == tenant.id,
        )
    )
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="pedido_not_found")
    if pedido.sync_bajado:
        raise HTTPException(status_code=409, detail="already_synced")

    pedido.sync_bajado = True
    pedido.id_venta_local = data.id_venta_local
    pedido.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"ok": True, "pedido_id": str(pedido_id), "id_venta_local": data.id_venta_local}


# ── Actualización de estado desde SQL Server ──────────────────────────────────

@router.patch("/pedidos/{pedido_id}/estado")
async def actualizar_estado_desde_sync(
    pedido_id: uuid.UUID,
    data: PedidoEstadoSyncUpdate,
    tenant: Tenant = Depends(verify_sync_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    El sync C# notifica un cambio de estado desde SQL Server.
    Mapeo de estados SQL Server → Postgres:
      COMPLETADA (PD convertido) → entregado
      ANULADA                    → cancelado
    También guarda id_venta_rm_local cuando el RM fue creado.
    """
    result = await db.execute(
        select(PedidoWeb).where(
            PedidoWeb.id == pedido_id,
            PedidoWeb.tenant_id == tenant.id,
        )
    )
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="pedido_not_found")

    pedido.estado = data.nuevo_estado
    if data.id_venta_local is not None:
        pedido.id_venta_local = data.id_venta_local
    if data.id_venta_rm_local is not None:
        pedido.id_venta_rm_local = data.id_venta_rm_local
    pedido.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"ok": True, "nuevo_estado": data.nuevo_estado}


# ── Pedidos modificados (bajada para sync C#) ─────────────────────────────────

@router.get("/pedidos-modificados", response_model=list[PedidoResponse])
async def get_pedidos_modificados(
    since: str,
    tenant: Tenant = Depends(verify_sync_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Devuelve pedidos que ya bajaron a SQL Server (sync_bajado=True)
    pero fueron modificados en el dashboard cloud después del cursor.
    El sync C# los consume para actualizar VENTA + DETALLE_VENTA.

    Parámetro:
      since: ISO 8601 timestamp. Ej: 2026-03-21T18:00:00+00:00
    """
    from datetime import datetime, timezone

    try:
        # Parsear el timestamp ISO 8601 con o sin timezone
        if since.endswith("Z"):
            since = since[:-1] + "+00:00"
        cursor_dt = datetime.fromisoformat(since)
        if cursor_dt.tzinfo is None:
            cursor_dt = cursor_dt.replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=422,
            detail="Formato de 'since' inválido. Usar ISO 8601. Ej: 2026-03-21T18:00:00Z"
        )

    result = await db.execute(
        select(PedidoWeb)
        .where(
            PedidoWeb.tenant_id == tenant.id,
            PedidoWeb.sync_bajado == True,      # ya existe en SQL Server
            PedidoWeb.updated_at > cursor_dt,    # fue modificado después del cursor
        )
        .options(selectinload(PedidoWeb.items))
        .order_by(PedidoWeb.updated_at.asc())
        .limit(200)  # máximo 200 por ciclo para no sobrecargar
    )
    pedidos = result.scalars().all()
    return pedidos
