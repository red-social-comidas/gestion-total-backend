import pytest
from httpx import AsyncClient


def _get_headers(tenant_seed):
    return {
        "X-Sync-Api-Key": tenant_seed["tenant"].sync_api_key
    }


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_sync_productos_sin_api_key(client: AsyncClient, tenant_seed):
    r = await client.post("/api/v1/sync/productos", json={"batch": []})
    assert r.status_code == 422  # header requerido


@pytest.mark.asyncio
async def test_sync_productos_api_key_invalida(client: AsyncClient, tenant_seed):
    r = await client.post(
        "/api/v1/sync/productos",
        json={"batch": []},
        headers={"X-Sync-Api-Key": "clave-falsa"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_sync_productos_ok(client: AsyncClient, tenant_seed):
    headers = _get_headers(tenant_seed)

    r = await client.post(
        "/api/v1/sync/productos",
        json={
            "batch": [
                {
                    "id_local": 1,
                    "codigo_barras": "7798000000001",
                    "nombre": "Yerba Mate 1kg",
                    "precio": 1500.00,
                    "stock_actual": 50.0,
                    "stock_minimo": 5.0,
                    "activo_local": True,
                }
            ]
        },
        headers=headers,
    )

    assert r.status_code == 200
    data = r.json()

    assert data["procesados"] == 1
    assert data["errores"] == 0


@pytest.mark.asyncio
async def test_sync_batch_limite(client: AsyncClient, tenant_seed):
    """Batch > 500 debe fallar."""
    headers = _get_headers(tenant_seed)

    batch = [
        {
            "id_local": i,
            "codigo_barras": str(i),
            "nombre": f"P{i}",
            "precio": 100,
            "stock_actual": 1,
        }
        for i in range(501)
    ]

    r = await client.post(
        "/api/v1/sync/productos",
        json={"batch": batch},
        headers=headers,
    )

    assert r.status_code == 422


@pytest.mark.asyncio
async def test_get_pedidos_pendientes_vacio(client: AsyncClient, tenant_seed):
    headers = _get_headers(tenant_seed)

    r = await client.get(
        "/api/v1/sync/pedidos/pendientes",
        headers=headers
    )

    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_estado_sync(client: AsyncClient, tenant_seed):
    headers = _get_headers(tenant_seed)

    r = await client.get(
        "/api/v1/sync/estado",
        headers=headers
    )

    assert r.status_code == 200
    data = r.json()

    assert "pedidos_pendientes_bajar" in data
    assert "tenant_slug" in data