from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int   # segundos


class TokenPayload(BaseModel):
    sub: str          # usuario id (UUID string)
    tenant_id: str
    rol: str
    exp: int
