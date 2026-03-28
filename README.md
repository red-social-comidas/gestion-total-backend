# Gestion Total API

Backend FastAPI para el sistema de gestión web.  
Conecta el sistema C# local (SQL Server) con el portal web (React) a través de sync bidireccional.

---

## Setup local (primera vez)

### 1. Clonar y crear entorno virtual

```bash
git clone <tu-repo>
cd gestion-total-api
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
# Para tests también:
pip install aiosqlite
```

### 3. Configurar variables de entorno

```bash
cp .env.example .env
```

Editar `.env` con tus valores:

```env
# PostgreSQL local (la que creaste en el FASE 0-B)
DATABASE_URL=postgresql+asyncpg://postgres:TU_PASSWORD@localhost:5432/gestion-total-web

# Generar con: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=tu_clave_secreta_aqui

ENVIRONMENT=development
```

### 4. Levantar la API

```bash
uvicorn app.main:app --reload --port 8000
```

Verificar en: http://localhost:8000/docs

---

## Estructura del proyecto

```
gestion-total-api/
├── app/
│   ├── main.py              # FastAPI app, CORS, routers
│   ├── config.py            # Variables de entorno
│   ├── database.py          # Engine async SQLAlchemy
│   ├── models/              # ORM models (tablas Postgres)
│   ├── schemas/             # Pydantic schemas (request/response)
│   ├── routers/
│   │   ├── auth.py          # POST /api/v1/auth/login
│   │   ├── sync.py          # /api/v1/sync/* (X-Sync-Api-Key)
│   │   ├── tienda.py        # /api/v1/tienda/{slug}/* (público)
│   │   └── dashboard.py     # /api/v1/dashboard/* (JWT)
│   ├── services/            # Lógica de negocio
│   └── dependencies/        # FastAPI Depends (auth)
├── tests/
├── .env.example
├── requirements.txt
└── Procfile                 # Railway deploy
```

---

## Endpoints principales

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/health` | — | Liveness check |
| POST | `/api/v1/auth/login` | — | Login dashboard |
| POST | `/api/v1/sync/productos` | API Key | Subir productos desde C# |
| POST | `/api/v1/sync/categorias` | API Key | Subir categorías |
| GET | `/api/v1/sync/pedidos/pendientes` | API Key | Pedidos a bajar a SQL Server |
| PATCH | `/api/v1/sync/pedidos/{id}/sincronizado` | API Key | Confirmar bajada |
| PATCH | `/api/v1/sync/pedidos/{id}/estado` | API Key | Actualizar estado desde C# |
| GET | `/api/v1/tienda/{slug}/productos` | — | Catálogo público |
| POST | `/api/v1/tienda/{slug}/pedidos` | — | Crear pedido (portal) |
| GET | `/api/v1/dashboard/pedidos/kanban` | JWT | Vista Kanban |
| PATCH | `/api/v1/dashboard/pedidos/{id}/estado` | JWT | Cambiar estado |
| GET | `/api/v1/dashboard/productos` | JWT | Listar productos |
| PATCH | `/api/v1/dashboard/productos/{id}/habilitar` | JWT | Habilitar en portal |

---

## Correr tests

```bash
pip install aiosqlite  # solo una vez
pytest -v
```

---

## Deploy en Railway

1. Subir el proyecto a GitHub
2. Nuevo proyecto en railway.app → Deploy from GitHub
3. Variables de entorno en Railway Settings:
   ```
   DATABASE_URL=postgresql+asyncpg://user:pass@ep-xxx.neon.tech/neondb?ssl=require
   SECRET_KEY=<openssl rand -hex 32>
   ENVIRONMENT=production
   ```
4. Railway detecta el `Procfile` automáticamente
5. Verificar: `GET https://tu-app.railway.app/health`

---

## App.config del Sync C# (referencia)

```xml
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <startup>
    <supportedRuntime version="v4.0" sku=".NETFramework,Version=v4.7.2" />
  </startup>

  <connectionStrings>
    <!--
      Mismo string de conexión que el sistema de gestión principal.
      Cambiar Data Source, Initial Catalog, User ID y Password según el entorno.
    -->
    <add name="GestionTotalDB" connectionString="Data Source=RAFFA\SQLEXPRESS;Initial Catalog=DB_ROMAN;User ID=Sol;Password=123;TrustServerCertificate=True" providerName="Microsoft.Data.SqlClient" />
  </connectionStrings>

  <appSettings>
    <!-- URL base de la API (local en desarrollo, Railway en producción) -->
    <add key="ApiBaseUrl" value="http://localhost:8000" />

    <!-- API Key del sync: SELECT sync_api_key FROM tenants WHERE slug = 'mi-negocio' -->
    <add key="ApiSyncKey" value="916390d951e275d89ce76eab691ecfaf804c20d8663f29a4f085c90aa30c12c0" />

    <!-- Slug del tenant en el portal -->
    <add key="TenantSlug" value="mi-negocio" />

    <!-- IdUsuario que se usa al insertar pedidos web en VENTA (usuario "sistema") -->
    <add key="IdUsuarioSistema" value="1" />

    <!-- Intervalo de sync automático en minutos -->
    <add key="SyncIntervalMinutos" value="5" />

    <!-- Máximo de productos por llamada a la API (no superar 500) -->
    <add key="BatchSize" value="500" />

    <!-- Reintentos ante error de red antes de marcar como fallido -->
    <add key="MaxReintentos" value="3" />

    <!-- incremental = solo cambios desde último cursor | completo = todos -->
    <add key="ModoSync" value="incremental" />
  </appSettings>
```
