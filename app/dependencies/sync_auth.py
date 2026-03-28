"""
app/dependencies/sync_auth.py
Verifica el header X-Sync-Api-Key contra la tabla tenants.
Usado por todos los endpoints del router sync.py.
"""
from fastapi import Header, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.tenant import Tenant


async def verify_sync_api_key(
    x_sync_api_key: str = Header(..., alias="X-Sync-Api-Key"),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """
    Dependency que devuelve el Tenant autenticado.
    Si la key no existe o el tenant está inactivo → 403.
    """
    result = await db.execute(
        select(Tenant).where(
            Tenant.sync_api_key == x_sync_api_key,
            Tenant.activo == True,
        )
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=403, detail="invalid_api_key")
    return tenant
