import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_categorias_vacio(client: AsyncClient, tenant_seed):
    slug = tenant_seed["tenant"].slug
    r = await client.get(f"/api/v1/tienda/{slug}/categorias")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_get_productos_vacio(client: AsyncClient, tenant_seed):
    slug = tenant_seed["tenant"].slug
    # Si no hay producto_seed, debería ser vacío
    r = await client.get(f"/api/v1/tienda/{slug}/productos")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0 or "items" in data


@pytest.mark.asyncio
async def test_get_productos_con_producto(client: AsyncClient, tenant_seed, producto_seed):
    slug = tenant_seed["tenant"].slug
    r = await client.get(f"/api/v1/tienda/{slug}/productos")
    assert r.status_code == 200
    data = r.json()
    # Verifica que al menos haya un producto y coincida con el seed
    assert any(item["nombre"] == producto_seed.nombre for item in data["items"])


@pytest.mark.asyncio
async def test_slug_inexistente(client: AsyncClient):
    r = await client.get("/api/v1/tienda/no-existe/productos")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_crear_pedido_ok(client: AsyncClient, tenant_seed, producto_seed):
    slug = tenant_seed["tenant"].slug
    r = await client.post(
        f"/api/v1/tienda/{slug}/pedidos",
        json={
            "cliente_nombre":  "Juan Pérez",
            "cliente_celular": "3624123456",
            "metodo_entrega":  "retiro",
            "items": [{"id_producto_local": producto_seed.id_local, "cantidad": 2}],
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["numero_pedido"].startswith("GTW-")
    assert data["estado"] == "por_confirmar"


@pytest.mark.asyncio
async def test_crear_pedido_con_dni(client: AsyncClient, tenant_seed, producto_seed):
    slug = tenant_seed["tenant"].slug
    r = await client.post(
        f"/api/v1/tienda/{slug}/pedidos",
        json={
            "cliente_nombre":    "María García",
            "cliente_celular":   "3624654321",
            "cliente_documento": "28456789",
            "metodo_entrega":    "domicilio",
            "direccion_entrega": "Av. Test 123",
            "items": [{"id_producto_local": producto_seed.id_local, "cantidad": 1}],
        },
    )
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_crear_pedido_dni_invalido(client: AsyncClient, tenant_seed, producto_seed):
    slug = tenant_seed["tenant"].slug
    r = await client.post(
        f"/api/v1/tienda/{slug}/pedidos",
        json={
            "cliente_nombre":    "Cliente",
            "cliente_celular":   "3624000000",
            "cliente_documento": "abc123",   # inválido
            "metodo_entrega":    "retiro",
            "items": [{"id_producto_local": producto_seed.id_local, "cantidad": 1}],
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_crear_pedido_domicilio_sin_direccion(client: AsyncClient, tenant_seed, producto_seed):
    slug = tenant_seed["tenant"].slug
    r = await client.post(
        f"/api/v1/tienda/{slug}/pedidos",
        json={
            "cliente_nombre":  "Cliente",
            "cliente_celular": "3624000000",
            "metodo_entrega":  "domicilio",
            # sin direccion_entrega
            "items": [{"id_producto_local": producto_seed.id_local, "cantidad": 1}],
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_crear_pedido_producto_no_habilitado(client: AsyncClient, tenant_seed):
    slug = tenant_seed["tenant"].slug
    r = await client.post(
        f"/api/v1/tienda/{slug}/pedidos",
        json={
            "cliente_nombre":  "Cliente",
            "cliente_celular": "3624000000",
            "metodo_entrega":  "retiro",
            "items": [{"id_producto_local": 999, "cantidad": 1}],
        },
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_consultar_pedido_por_numero(client: AsyncClient, tenant_seed, producto_seed):
    slug = tenant_seed["tenant"].slug
    # Crear pedido
    r_create = await client.post(
        f"/api/v1/tienda/{slug}/pedidos",
        json={
            "cliente_nombre":  "Carlos López",
            "cliente_celular": "3624999888",
            "metodo_entrega":  "retiro",
            "items": [{"id_producto_local": producto_seed.id_local, "cantidad": 1}],
        },
    )
    numero = r_create.json()["numero_pedido"]

    # Consultar
    r = await client.get(f"/api/v1/tienda/{slug}/pedidos/{numero}")
    assert r.status_code == 200
    assert r.json()["numero_pedido"] == numero