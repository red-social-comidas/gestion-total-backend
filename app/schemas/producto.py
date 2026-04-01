from __future__ import annotations
import uuid
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, field_validator


# ── Sync (C# → API) ──────────────────────────────────────────────────────────

class ProductoSyncItem(BaseModel):
    """Un producto individual en el batch de sync."""
    id_local:      int
    codigo_barras: str
    codigo:        Optional[str] = None
    nombre:        str
    precio:        Decimal
    stock_actual:  Decimal
    stock_minimo:  Decimal = Decimal("0")
    activo_local:  bool = True
    id_categoria_local: Optional[int] = None
    # FIX: campo agregado para recibir habilitado_web desde el sync C#
    # El sync lo envía siempre; None = no especificado (usar valor existente en DB)
    habilitado_web: Optional[bool] = None


class ProductosBatchPayload(BaseModel):
    """Payload del endpoint POST /sync/productos."""
    batch: list[ProductoSyncItem]

    @field_validator("batch")
    @classmethod
    def batch_no_vacio(cls, v: list) -> list:
        if len(v) > 500:
            raise ValueError("El batch no puede superar 500 items por llamada.")
        return v


class SyncBatchResponse(BaseModel):
    procesados:   int
    creados:      int
    actualizados: int
    errores:      int


# ── Catálogo público (API → Portal React) ────────────────────────────────────

class ProductoCatalogoItem(BaseModel):
    """Versión reducida para el grid del catálogo."""
    id:           uuid.UUID
    id_local:     int
    nombre:       str
    precio:       Decimal
    imagen_url:   Optional[str] = None
    stock_badge:  Optional[str] = None   # null | "ultimas_unidades" | "sin_stock"
    categoria_id: Optional[uuid.UUID] = None

    model_config = {"from_attributes": True}


class ProductoDetalle(ProductoCatalogoItem):
    """Versión completa para la página de detalle."""
    codigo_barras:   str
    descripcion_web: Optional[str] = None

    model_config = {"from_attributes": True}


class CatalogoResponse(BaseModel):
    items:     list[ProductoCatalogoItem]
    total:     int
    page:      int
    page_size: int
    pages:     int


# ── Dashboard ─────────────────────────────────────────────────────────────────

class ProductoDashboard(BaseModel):
    id:                   uuid.UUID
    id_local:             int
    nombre:               str
    codigo_barras:        str
    precio:               Decimal
    stock_actual:         Decimal
    habilitado_web:       bool
    activo_local:         bool
    imagen_url:           Optional[str] = None
    descripcion_web:      Optional[str] = None

    model_config = {"from_attributes": True}


class HabilitarWebRequest(BaseModel):
    habilitado_web: bool


class DescripcionWebRequest(BaseModel):
    descripcion_web: Optional[str] = None


# ── Sync parcial: stock y precios (C# → API) ─────────────────────────────────

class StockSyncItem(BaseModel):
    """Un producto con solo su stock actualizado."""
    id_local:     int
    stock_actual: Decimal


class StockBatchPayload(BaseModel):
    batch: list[StockSyncItem]

    @field_validator("batch")
    @classmethod
    def batch_no_vacio(cls, v: list) -> list:
        if len(v) > 1000:
            raise ValueError("El batch no puede superar 1000 items.")
        return v


class PrecioSyncItem(BaseModel):
    """Un producto con solo su precio actualizado."""
    id_local:    int
    precio:      Decimal
    id_lista:    int = 0       # 0 = precio base
    nombre_lista: str = "BASE"


class PrecioBatchPayload(BaseModel):
    batch: list[PrecioSyncItem]

    @field_validator("batch")
    @classmethod
    def batch_no_vacio(cls, v: list) -> list:
        if len(v) > 1000:
            raise ValueError("El batch no puede superar 1000 items.")
        return v


class PatchBatchResult(BaseModel):
    actualizados:   int
    no_encontrados: int
    errores:        int

