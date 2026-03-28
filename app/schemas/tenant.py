from __future__ import annotations
import uuid
from typing import Optional, Dict, Any
from pydantic import BaseModel


# ── UPDATE (PATCH) ─────────────────────────────────────────────

class TenantUpdateSchema(BaseModel):
    nombre_comercial: Optional[str] = None
    whatsapp_numero: Optional[str] = None
    config_visual: Optional[Dict[str, Any]] = None


# ── RESPONSE ───────────────────────────────────────────────────

class TenantResponse(BaseModel):
    id: uuid.UUID
    slug: str
    nombre_comercial: str
    whatsapp_numero: str
    config_visual: Optional[Dict[str, Any]] = None

    model_config = {
        "from_attributes": True
    }