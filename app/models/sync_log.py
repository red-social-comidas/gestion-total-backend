import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class SyncLog(Base):
    __tablename__ = "sync_log"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id     = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    tipo          = Column(String(20),  nullable=False)   # productos | categorias | pedidos | estados
    direccion     = Column(String(10),  nullable=False)   # subida | bajada
    estado        = Column(String(10),  nullable=False)   # ok | error | parcial
    registros     = Column(Integer,     nullable=False, default=0)
    mensaje_error = Column(Text,        nullable=True)
    duracion_ms   = Column(Integer,     nullable=True)
    created_at    = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="sync_logs")
