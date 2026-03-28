import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class TenantUsuario(Base):
    __tablename__ = "tenant_usuarios"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id     = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    nombre        = Column(String(200), nullable=False)
    email         = Column(String(200), nullable=False)
    password_hash = Column(String(255), nullable=False)
    rol           = Column(String(20),  nullable=False, default="operador")
    activo        = Column(Boolean,     nullable=False, default=True)
    ultimo_login  = Column(DateTime(timezone=True), nullable=True)
    created_at    = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at    = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="usuarios")
