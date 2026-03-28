import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_correcto(client: AsyncClient, tenant_seed):
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": tenant_seed["usuario"].email,
            "password": "configuracion1",
        },
    )
    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_password_incorrecto(client: AsyncClient, tenant_seed):
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": tenant_seed["usuario"].email,
            "password": "wrongpass",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_email_inexistente(client: AsyncClient, tenant_seed):
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "noexiste@test.com",
            "password": "algo",
        },
    )
    assert response.status_code == 401