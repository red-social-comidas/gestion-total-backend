from __future__ import annotations
import uuid
from typing import Optional
from pydantic import BaseModel


class CategoriaSyncItem(BaseModel):
    id_local:    int
    nombre:      str
    descripcion: Optional[str] = None
    orden:       int = 0
    activo:      bool = True


class CategoriasBatchPayload(BaseModel):
    batch: list[CategoriaSyncItem]


class CategoriaResponse(BaseModel):
    id:     uuid.UUID
    nombre: str
    orden:  int

    model_config = {"from_attributes": True}
