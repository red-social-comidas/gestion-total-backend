import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug             = Column(String(200), nullable=False, unique=True)
    nombre_comercial = Column(String(200), nullable=False)
    whatsapp_numero  = Column(String(20),  nullable=False)
    email_contacto   = Column(String(200), nullable=True)
    activo           = Column(Boolean,     nullable=False, default=True)
    config_visual    = Column(JSONB,       nullable=False, default=dict)
    sync_api_key     = Column(String(128), nullable=False)
    created_at       = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at       = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relaciones
    usuarios   = relationship("TenantUsuario", back_populates="tenant", lazy="noload")
    productos  = relationship("ProductoWeb",   back_populates="tenant", lazy="noload")
    categorias = relationship("CategoriaWeb",  back_populates="tenant", lazy="noload")
    pedidos    = relationship("PedidoWeb",     back_populates="tenant", lazy="noload")
    sync_logs  = relationship("SyncLog",       back_populates="tenant", lazy="noload")
