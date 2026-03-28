import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class CategoriaWeb(Base):
    __tablename__ = "categorias_web"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id   = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    id_local    = Column(Integer,    nullable=False)
    nombre      = Column(String(200), nullable=False)
    descripcion = Column(Text,        nullable=True)
    orden       = Column(Integer,     nullable=False, default=0)
    activo      = Column(Boolean,     nullable=False, default=True)
    ultima_sync = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    created_at  = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    tenant    = relationship("Tenant", back_populates="categorias")
    productos = relationship("ProductoWeb", back_populates="categoria", lazy="noload")
