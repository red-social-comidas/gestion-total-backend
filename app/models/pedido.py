import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Numeric, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship
from app.database import Base


class EstadoPedidoEnum(str, enum.Enum):
    por_confirmar  = "por_confirmar"
    en_preparacion = "en_preparacion"
    para_entregar  = "para_entregar"
    entregado      = "entregado"
    cancelado      = "cancelado"


# Transiciones válidas del Kanban
TRANSICIONES_VALIDAS: dict[EstadoPedidoEnum, list[EstadoPedidoEnum]] = {
    EstadoPedidoEnum.por_confirmar:  [EstadoPedidoEnum.en_preparacion, EstadoPedidoEnum.cancelado],
    EstadoPedidoEnum.en_preparacion: [EstadoPedidoEnum.para_entregar,  EstadoPedidoEnum.cancelado],
    EstadoPedidoEnum.para_entregar:  [EstadoPedidoEnum.entregado,      EstadoPedidoEnum.cancelado],
    EstadoPedidoEnum.entregado:      [],   # estado terminal
    EstadoPedidoEnum.cancelado:      [],   # estado terminal
}


class PedidoWeb(Base):
    __tablename__ = "pedidos_web"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id         = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    numero_pedido     = Column(String(20),  nullable=False)
    origen            = Column(String(20),  nullable=False, default="portal_web")
    estado            = Column(
                            ENUM(EstadoPedidoEnum, name="estado_pedido", create_type=False),
                            nullable=False,
                            default=EstadoPedidoEnum.por_confirmar,
                        )
    cliente_nombre    = Column(String(200), nullable=False)
    cliente_celular   = Column(String(20),  nullable=False)
    cliente_email     = Column(String(200), nullable=True)
    cliente_documento = Column(String(20),  nullable=True)   # DNI/CUIT — ADR-010
    metodo_entrega    = Column(String(20),  nullable=False)
    direccion_entrega = Column(Text,        nullable=True)
    costo_envio       = Column(Numeric(18, 2), nullable=False, default=0)
    notas             = Column(Text,        nullable=True)
    subtotal          = Column(Numeric(18, 2), nullable=False)
    total             = Column(Numeric(18, 2), nullable=False)
    sync_bajado       = Column(Boolean,     nullable=False, default=False)
    id_venta_local    = Column(Integer,     nullable=True)
    id_venta_rm_local = Column(Integer,     nullable=True)
    ip_cliente        = Column(String(45),  nullable=True)
    created_at        = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at        = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    tenant = relationship("Tenant",    back_populates="pedidos")
    items  = relationship("PedidoItem", back_populates="pedido", cascade="all, delete-orphan", lazy="selectin")

    def puede_transicionar_a(self, nuevo_estado: EstadoPedidoEnum) -> bool:
        return nuevo_estado in TRANSICIONES_VALIDAS.get(self.estado, [])


class PedidoItem(Base):
    __tablename__ = "pedido_items"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id         = Column(UUID(as_uuid=True), ForeignKey("pedidos_web.id", ondelete="CASCADE"), nullable=False)
    producto_id       = Column(UUID(as_uuid=True), ForeignKey("productos_web.id", ondelete="SET NULL"), nullable=True)
    id_producto_local = Column(Integer,     nullable=False)
    nombre_producto   = Column(String(300), nullable=False)
    codigo_barras     = Column(String(100), nullable=False)
    precio_unitario   = Column(Numeric(18, 2), nullable=False)
    cantidad          = Column(Numeric(10, 2), nullable=False)
    subtotal          = Column(Numeric(18, 2), nullable=False)
    created_at        = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    pedido   = relationship("PedidoWeb",  back_populates="items")
    producto = relationship("ProductoWeb", back_populates="items", lazy="noload")
