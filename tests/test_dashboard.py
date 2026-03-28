import pytest
from httpx import AsyncClient


async def _get_token(client: AsyncClient, tenant_seed) -> str:
    r = await client.post(
        "/api/v1/auth/login",
        json={
            "email": tenant_seed["usuario"].email,
            "password": tenant_seed["password"],
        },
    )
    assert r.status_code == 200  # 🔥 asegura login válido
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_kanban_requiere_jwt(client: AsyncClient, tenant_seed):
    r = await client.get("/api/v1/dashboard/pedidos/kanban")
    assert r.status_code in (401, 403)  # depende de tu implementación


@pytest.mark.asyncio
async def test_kanban_vacio(client: AsyncClient, tenant_seed):
    token = await _get_token(client, tenant_seed)

    r = await client.get(
        "/api/v1/dashboard/pedidos/kanban",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert r.status_code == 200
    data = r.json()

    assert "por_confirmar" in data
    assert "en_preparacion" in data
    assert "para_entregar" in data
    assert "entregado" in data
    assert "cancelado" in data


@pytest.mark.asyncio
async def test_habilitar_producto(client: AsyncClient, tenant_seed, producto_seed):
    token = await _get_token(client, tenant_seed)
    headers = {"Authorization": f"Bearer {token}"}

    # Deshabilitar
    r = await client.patch(
        f"/api/v1/dashboard/productos/{producto_seed.id}/habilitar",
        json={"habilitado_web": False},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["habilitado_web"] is False

    # Volver a habilitar
    r = await client.patch(
        f"/api/v1/dashboard/productos/{producto_seed.id}/habilitar",
        json={"habilitado_web": True},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["habilitado_web"] is True


@pytest.mark.asyncio
async def test_cambio_estado_valido(client: AsyncClient, tenant_seed, producto_seed):
    token = await _get_token(client, tenant_seed)
    headers = {"Authorization": f"Bearer {token}"}

    slug = tenant_seed["tenant"].slug

    # Crear pedido de prueba
    r_pedido = await client.post(
        f"/api/v1/tienda/{slug}/pedidos",
        json={
            "cliente_nombre": "Test",
            "cliente_celular": "3624000001",
            "metodo_entrega": "retiro",
            "items": [
                {
                    "id_producto_local": producto_seed.id_local,  # 🔥 clave
                    "cantidad": 1,
                }
            ],
        },
    )
    assert r_pedido.status_code == 201 or r_pedido.status_code == 200

    pedido_id = r_pedido.json()["id"]

    # Cambio válido
    r = await client.patch(
        f"/api/v1/dashboard/pedidos/{pedido_id}/estado",
        json={"nuevo_estado": "en_preparacion"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["estado"] == "en_preparacion"


@pytest.mark.asyncio
async def test_cambio_estado_invalido(client: AsyncClient, tenant_seed, producto_seed):
    """No se puede pasar de por_confirmar a entregado directamente."""
    token = await _get_token(client, tenant_seed)
    headers = {"Authorization": f"Bearer {token}"}

    slug = tenant_seed["tenant"].slug

    r_pedido = await client.post(
        f"/api/v1/tienda/{slug}/pedidos",
        json={
            "cliente_nombre": "Test2",
            "cliente_celular": "3624000002",
            "metodo_entrega": "retiro",
            "items": [
                {
                    "id_producto_local": producto_seed.id_local,
                    "cantidad": 1,
                }
            ],
        },
    )
    assert r_pedido.status_code == 201 or r_pedido.status_code == 200

    pedido_id = r_pedido.json()["id"]

    # Cambio inválido
    r = await client.patch(
        f"/api/v1/dashboard/pedidos/{pedido_id}/estado",
        json={"nuevo_estado": "entregado"},
        headers=headers,
    )
    assert r.status_code == 400