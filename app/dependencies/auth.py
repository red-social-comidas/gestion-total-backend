"""
app/dependencies/auth.py
Verifica el JWT Bearer token para los endpoints del dashboard.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError, jwt
from app.database import get_db
from app.config import get_settings
from app.models.usuario import TenantUsuario

settings = get_settings()
bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> TenantUsuario:
    """
    Dependency que devuelve el usuario autenticado.
    Si el token es inválido, expirado o el usuario no existe → 401.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid_token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(
        select(TenantUsuario).where(
            TenantUsuario.id == user_id,
            TenantUsuario.activo == True,
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise credentials_exception
    return user


async def require_admin(
    current_user: TenantUsuario = Depends(get_current_user),
) -> TenantUsuario:
    """Solo usuarios con rol 'admin' pueden acceder."""
    if current_user.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol admin.",
        )
    return current_user
