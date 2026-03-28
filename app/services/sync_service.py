"""
app/services/sync_service.py
Lógica de upsert para el sync bidireccional.
Usa INSERT ... ON CONFLICT DO UPDATE (upsert nativo de Postgres).
"""
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models.producto import ProductoWeb
from app.models.categoria import CategoriaWeb
from app.models.sync_log import SyncLog
from app.schemas.producto import ProductosBatchPayload, SyncBatchResponse
from app.schemas.categoria import CategoriasBatchPayload
import uuid


async def upsert_productos(
    tenant_id: uuid.UUID,
    payload: ProductosBatchPayload,
    db: AsyncSession,
) -> SyncBatchResponse:
    """
    Inserta o actualiza productos en productos_web.
    Usa upsert por (tenant_id, id_local) — clave de reconciliación.
    Si el producto ya existe, actualiza precio, stock, nombre, estado.
    NO actualiza: descripcion_web, imagen_url, habilitado_web
    (esos los gestiona el operador desde el dashboard).
    """
    creados = actualizados = errores = 0
    ahora = datetime.now(timezone.utc)

    for item in payload.batch:
        try:
            # Resolver categoria_id si viene id_categoria_local
            categoria_id = None
            if item.id_categoria_local is not None:
                result = await db.execute(
                    select(CategoriaWeb.id).where(
                        CategoriaWeb.tenant_id == tenant_id,
                        CategoriaWeb.id_local == item.id_categoria_local,
                    )
                )
                row = result.scalar_one_or_none()
                if row:
                    categoria_id = row

            # Preparar valores del INSERT (incluyendo habilitado_web si viene)
            insert_values = dict(
                tenant_id=tenant_id,
                id_local=item.id_local,
                codigo_barras=item.codigo_barras,
                codigo_interno=item.codigo,
                nombre=item.nombre,
                precio=item.precio,
                stock_actual=item.stock_actual,
                stock_minimo=item.stock_minimo,
                activo_local=item.activo_local,
                categoria_id=categoria_id,
                ultima_sync=ahora,
                updated_at=ahora,
            )
            # FIX: aplicar habilitado_web si viene en el payload (INSERT y UPDATE)
            # - En INSERT: siempre se aplica (primer sync = intención explícita del operador)
            # - En UPDATE: se aplica si el sync lo manda explícitamente
            # El operador puede cambiarlo después desde el dashboard
            if item.habilitado_web is not None:
                insert_values["habilitado_web"] = item.habilitado_web

            # Campos que siempre se actualizan en UPDATE (precio, stock, etc.)
            update_set = {
                "codigo_barras": item.codigo_barras,
                "codigo_interno": item.codigo,
                "nombre":        item.nombre,
                "precio":        item.precio,       # precio siempre sincroniza
                "stock_actual":  item.stock_actual,  # stock siempre sincroniza
                "stock_minimo":  item.stock_minimo,
                "activo_local":  item.activo_local,
                "categoria_id":  categoria_id,
                "ultima_sync":   ahora,
                "updated_at":    ahora,
                # descripcion_web e imagen_url NUNCA se sobreescriben desde el sync
            }
            # Solo sobreescribir habilitado_web si viene explícito en el payload
            if item.habilitado_web is not None:
                update_set["habilitado_web"] = item.habilitado_web

            stmt = (
                pg_insert(ProductoWeb)
                .values(**insert_values)
                .on_conflict_do_update(
                    index_elements=["tenant_id", "id_local"],
                    set_=update_set,
                )
                .returning(ProductoWeb.created_at, ProductoWeb.updated_at)
            )
            result = await db.execute(stmt)
            row = result.fetchone()
            # Si created_at == updated_at → fue INSERT (nuevo)
            if row and row[0] == row[1]:
                creados += 1
            else:
                actualizados += 1

        except Exception as e:
            errores += 1

    await db.commit()

    # Registrar en sync_log
    await _registrar_sync_log(
        tenant_id=tenant_id,
        tipo="productos",
        direccion="subida",
        estado="ok" if errores == 0 else "parcial",
        registros=creados + actualizados,
        mensaje_error=f"{errores} errores" if errores else None,
        db=db,
    )

    return SyncBatchResponse(
        procesados=len(payload.batch),
        creados=creados,
        actualizados=actualizados,
        errores=errores,
    )


async def upsert_categorias(
    tenant_id: uuid.UUID,
    payload: CategoriasBatchPayload,
    db: AsyncSession,
) -> dict:
    """Inserta o actualiza categorías."""
    creados = actualizados = errores = 0
    ahora = datetime.now(timezone.utc)

    for item in payload.batch:
        try:
            stmt = (
                pg_insert(CategoriaWeb)
                .values(
                    tenant_id=tenant_id,
                    id_local=item.id_local,
                    nombre=item.nombre,
                    descripcion=item.descripcion,
                    orden=item.orden,
                    activo=item.activo,
                    ultima_sync=ahora,
                )
                .on_conflict_do_update(
                    index_elements=["tenant_id", "id_local"],
                    set_={
                        "nombre":       item.nombre,
                        "descripcion":  item.descripcion,
                        "orden":        item.orden,
                        "activo":       item.activo,
                        "ultima_sync":  ahora,
                    },
                )
            )
            await db.execute(stmt)
            creados += 1  # simplificado, no distinguimos insert/update aquí
        except Exception:
            errores += 1

    await db.commit()
    return {"procesados": len(payload.batch), "creados": creados, "errores": errores}


async def _registrar_sync_log(
    tenant_id: uuid.UUID,
    tipo: str,
    direccion: str,
    estado: str,
    registros: int,
    mensaje_error: str | None,
    db: AsyncSession,
    duracion_ms: int | None = None,
) -> None:
    log = SyncLog(
        tenant_id=tenant_id,
        tipo=tipo,
        direccion=direccion,
        estado=estado,
        registros=registros,
        mensaje_error=mensaje_error,
        duracion_ms=duracion_ms,
    )
    db.add(log)
    await db.commit()
