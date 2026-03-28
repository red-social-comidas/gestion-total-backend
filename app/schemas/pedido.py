from __future__ import annotations
import re
import uuid
from decimal import Decimal
from typing import Optional, Literal
from datetime import datetime
from pydantic import BaseModel, field_validator, model_validator
from app.models.pedido import EstadoPedidoEnum


# ── Items ─────────────────────────────────────────────────────────────────────

class PedidoItemCreate(BaseModel):
    id_producto_local: int
    cantidad:          Decimal

    @field_validator("cantidad")
    @classmethod
    def cantidad_positiva(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("La cantidad debe ser mayor a 0.")
        return v


class PedidoItemResponse(BaseModel):
    id:               uuid.UUID
    id_producto_local: int
    nombre_producto:  str
    codigo_barras:    str
    precio_unitario:  Decimal
    cantidad:         Decimal
    subtotal:         Decimal

    model_config = {"from_attributes": True}


# ── Crear pedido (portal web y dashboard manual) ──────────────────────────────

class PedidoCreate(BaseModel):
    cliente_nombre:    str
    cliente_celular:   str
    cliente_email:     Optional[str] = None
    cliente_documento: Optional[str] = None   # DNI/CUIT — ADR-010

    metodo_entrega:    Literal["retiro", "domicilio"]
    direccion_entrega: Optional[str] = None
    notas:             Optional[str] = None

    items: list[PedidoItemCreate]

    # Para dashboard_manual — el router lo fuerza a "portal_web" si viene del portal
    origen: Literal["portal_web", "dashboard_manual"] = "portal_web"

    @field_validator("cliente_documento")
    @classmethod
    def validar_documento(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v.strip() == "":
            return None
        v = v.strip()
        if not re.match(r"^\d{7,11}$", v):
            raise ValueError("El documento debe ser numérico y tener entre 7 y 11 dígitos.")
        return v

    @model_validator(mode="after")
    def domicilio_requiere_direccion(self) -> "PedidoCreate":
        if self.metodo_entrega == "domicilio" and not self.direccion_entrega:
            raise ValueError("La dirección de entrega es requerida para envío a domicilio.")
        if not self.items:
            raise ValueError("El pedido debe tener al menos un ítem.")
        return self


# ── Respuestas ────────────────────────────────────────────────────────────────

class PedidoResumen(BaseModel):
    """Respuesta al crear un pedido (201)."""
    id:           uuid.UUID
    numero_pedido: str
    estado:        EstadoPedidoEnum
    total:         Decimal
    metodo_entrega: str
    created_at:    datetime

    model_config = {"from_attributes": True}


class PedidoResponse(BaseModel):
    """Respuesta completa para el portal y el dashboard."""
    id:                uuid.UUID
    numero_pedido:     str
    origen:            str
    estado:            EstadoPedidoEnum
    cliente_nombre:    str
    cliente_celular:   str
    cliente_email:     Optional[str] = None
    cliente_documento: Optional[str] = None
    metodo_entrega:    str
    direccion_entrega: Optional[str] = None
    costo_envio:       Decimal
    notas:             Optional[str] = None
    subtotal:          Decimal
    total:             Decimal
    sync_bajado:       bool
    id_venta_local:    Optional[int] = None
    items:             list[PedidoItemResponse] = []
    created_at:        datetime
    updated_at:        datetime

    model_config = {"from_attributes": True}


# ── Kanban ────────────────────────────────────────────────────────────────────

class KanbanResponse(BaseModel):
    por_confirmar:  list[PedidoResponse]
    en_preparacion: list[PedidoResponse]
    para_entregar:  list[PedidoResponse]
    entregado:      list[PedidoResponse]
    cancelado:      list[PedidoResponse]


# ── Sync callbacks (C# → API) ─────────────────────────────────────────────────

class PedidoSincronizadoUpdate(BaseModel):
    """Marca un pedido como bajado a SQL Server."""
    id_venta_local: int


class PedidoEstadoSyncUpdate(BaseModel):
    """El sync notifica un cambio de estado desde SQL Server."""
    nuevo_estado:      EstadoPedidoEnum
    id_venta_local:    Optional[int] = None
    id_venta_rm_local: Optional[int] = None


class CambioEstadoRequest(BaseModel):
    """Dashboard — cambio manual de estado."""
    nuevo_estado: EstadoPedidoEnum


# ── Editar pedido desde el dashboard ─────────────────────────────────────────

class PedidoEditarItemSchema(BaseModel):
    id_producto_local: int
    cantidad:          Decimal

    @field_validator("cantidad")
    @classmethod
    def cantidad_positiva(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("La cantidad debe ser mayor a 0.")
        return v


class PedidoEditarRequest(BaseModel):
    """
    Payload para PATCH /dashboard/pedidos/{id}
    Todos los campos son opcionales — solo se actualiza lo que viene.
    """
    items:             Optional[list[PedidoEditarItemSchema]] = None
    metodo_entrega:    Optional[Literal["retiro", "domicilio"]] = None
    direccion_entrega: Optional[str] = None
    notas:             Optional[str] = None
    costo_envio:       Optional[Decimal] = None   # si se manda explícito, sobreescribe
