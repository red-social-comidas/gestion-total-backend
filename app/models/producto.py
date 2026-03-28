import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Numeric, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class ProductoWeb(Base):
    __tablename__ = "productos_web"

    id                   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id            = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    id_local             = Column(Integer,     nullable=False)
    codigo_barras        = Column(String(100), nullable=False)
    codigo_interno       = Column(String(50),  nullable=True)
    nombre               = Column(String(300), nullable=False)
    descripcion_web      = Column(Text,        nullable=True)   # editable en dashboard
    precio               = Column(Numeric(18, 2), nullable=False)
    stock_actual         = Column(Numeric(18, 3), nullable=False, default=0)
    stock_minimo         = Column(Numeric(18, 3), nullable=False, default=0)
    imagen_url           = Column(String(500), nullable=True)
    imagen_cloudinary_id = Column(String(200), nullable=True)
    habilitado_web       = Column(Boolean,     nullable=False, default=False)
    activo_local         = Column(Boolean,     nullable=False, default=True)
    categoria_id         = Column(UUID(as_uuid=True), ForeignKey("categorias_web.id", ondelete="SET NULL"), nullable=True)
    ultima_sync          = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    created_at           = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at           = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    tenant    = relationship("Tenant",      back_populates="productos")
    categoria = relationship("CategoriaWeb", back_populates="productos")
    items     = relationship("PedidoItem",  back_populates="producto", lazy="noload")

    @property
    def stock_badge(self) -> str | None:
        """
        Badge de stock para el portal.
        No expone el número exacto al cliente (ADR-007 v2).
        """
        if self.stock_actual <= 0:
            return "sin_stock"
        if self.stock_minimo > 0 and self.stock_actual <= self.stock_minimo:
            return "ultimas_unidades"
        return None
