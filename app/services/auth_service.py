"""
app/services/auth_service.py
Lógica de autenticación: verificar password, generar JWT.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.config import get_settings
from app.models.usuario import TenantUsuario

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(user: TenantUsuario) -> tuple[str, int]:
    """
    Genera un JWT para el usuario.
    Devuelve (token, expires_in_seconds).
    """
    expire = datetime.now(timezone.utc) + timedelta(
        hours=settings.access_token_expire_hours
    )
    expires_in = settings.access_token_expire_hours * 3600

    payload = {
        "sub":       str(user.id),
        "tenant_id": str(user.tenant_id),
        "rol":       user.rol,
        "nombre":    user.nombre,
        "exp":       expire,
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    return token, expires_in


async def autenticar_usuario(
    email: str,
    password: str,
    db: AsyncSession,
) -> Optional[TenantUsuario]:
    """
    Busca el usuario por email y verifica la contraseña.
    Actualiza ultimo_login si es exitoso.
    Devuelve None si las credenciales son incorrectas.
    """
    result = await db.execute(
        select(TenantUsuario).where(
            TenantUsuario.email == email,
            TenantUsuario.activo == True,
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None

    # Actualizar ultimo_login
    await db.execute(
        update(TenantUsuario)
        .where(TenantUsuario.id == user.id)
        .values(ultimo_login=datetime.now(timezone.utc))
    )
    await db.commit()
    await db.refresh(user)
    return user
