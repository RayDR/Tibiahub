# Tibia Bestiary API - Backend

Automatic raffle scheduling, recovery, and operational runbooks are documented
in [`../docs/automatic-raffle-operations.md`](../docs/automatic-raffle-operations.md).

Backend API para el sistema de bestiario de Tibia construido con FastAPI y PostgreSQL 16+.

## 🚀 Características

- ✅ API RESTful con FastAPI
- ✅ PostgreSQL con baseline Alembic reproducible
- ✅ Integración real con TibiaData y TibiaWiki Fandom
- ✅ Bestiary live con cache TTL y sin fallback falso en producción
- ✅ Sistema de rifas de guild con reglas por cuenta local y reruns auditables
- ✅ Documentación automática con Swagger UI

## 📋 Requisitos

- Python 3.10+
- pip

## 🛠️ Instalación

1. Crear entorno virtual:
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

2. Instalar dependencias:
```bash
pip install -r requirements.txt
```

3. Copiar archivo de configuración:
```bash
cp .env.example .env
```

4. Aplicar el esquema a una base PostgreSQL vacía:
```bash
venv/bin/alembic -c alembic.ini upgrade head
```

5. Asegurar modo real en producción:
```bash
USE_MOCK_DATA=false
```

## 🏃 Ejecución

Iniciar el servidor de desarrollo:
```bash
python main.py
```

O con uvicorn directamente:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

La API estará disponible en: http://localhost:8000

## 📚 Documentación API

Una vez iniciado el servidor, accede a:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🌐 Fuentes externas

- TibiaData v4 para worlds, characters y guilds.
- TibiaWiki Fandom MediaWiki API para bestiary, loot, locations e imágenes.

## ⚠️ Limitaciones conocidas

- No existe account ID público confiable en TibiaData para rifas.
- La unicidad por cuenta se implementa con usuarios locales y personajes vinculados.
- Si una fuente externa no entrega un campo, la API responde `null` y el frontend renderiza `Unknown` o `Not available`.

## 🎯 Endpoints Principales

### Criaturas

- `GET /api/v1/creatures/` - Lista todas las criaturas
  - Query params: `skip`, `limit`, `search`, `difficulty`
- `GET /api/v1/creatures/{id}` - Obtiene una criatura por ID
- `GET /api/v1/creatures/name/{name}` - Obtiene una criatura por nombre
- `POST /api/v1/creatures/` - Crea una nueva criatura

### Zonas de Hunt

- `GET /api/v1/hunt-zones/` - Lista todas las zonas
  - Query params: `skip`, `limit`, `min_level`, `max_level`, `city`
- `GET /api/v1/hunt-zones/{id}` - Obtiene una zona por ID
- `GET /api/v1/hunt-zones/recommendations/{vocation}` - Recomendaciones de hunt
  - Path param: `vocation` (knight, paladin, sorcerer, druid)
  - Query params: `level` (requerido), `limit`
- `POST /api/v1/hunt-zones/` - Crea una nueva zona

## 🗂️ Estructura del Proyecto

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── creatures.py      # Endpoints de criaturas
│   │       ├── hunt_zones.py     # Endpoints de zonas
│   │       └── router.py         # Router principal
│   ├── core/
│   │   └── config.py             # Configuración
│   ├── db/
│   │   └── database.py           # Configuración de BD
│   ├── models/                   # Modelos SQLAlchemy
│   │   ├── creature.py
│   │   ├── element.py
│   │   ├── loot.py
│   │   ├── spawn_location.py
│   │   └── hunt_zone.py
│   ├── schemas/                  # Schemas Pydantic
│   │   └── __init__.py
│   └── services/                 # Lógica de negocio
│       └── hunt_service.py
├── main.py                       # Aplicación principal
├── seed_db.py                    # Script de datos iniciales
└── requirements.txt
```

## 🗄️ Modelo de Datos

### Tablas Principales

- **creatures**: Información de monstruos
- **elements**: Tipos de daño (Physical, Fire, Ice, etc.)
- **loot**: Items que dropean las criaturas
- **hunt_zones**: Zonas de cacería
- **spawn_locations**: Ubicaciones donde spawean las criaturas

### Relaciones

- Creature ↔ Element (many-to-many): weaknesses y resistances
- Creature → Loot (one-to-many)
- Creature → SpawnLocation ← HuntZone (many-to-many through SpawnLocation)

## 🎮 Sistema de Recomendación

El sistema de recomendación considera:

1. **Vocación**: Recomienda zonas apropiadas para la clase
2. **Nivel**: Filtra por rango de nivel del jugador
3. **Experiencia**: Prioriza zonas con buen exp/hora
4. **Profit**: Considera el gold/hora promedio
5. **Tamaño**: Prefiere zonas más grandes
6. **Requisitos**: Penaliza zonas que requieren quests

Cada zona recibe un score de 0-100 basado en estos factores.

## 🧪 Datos de Ejemplo

El script `seed_db.py` incluye:
- 7 elementos de daño
- 5 criaturas ejemplo (Rat, Rotworm, Dragon, Dragon Lord, Demon)
- Loot asociado a cada criatura
- 5 zonas de hunt (desde Rookgaard hasta Goroma)
- Spawn locations vinculando criaturas y zonas

## 🔧 Desarrollo

Para agregar más criaturas, edita `seed_db.py` o usa los endpoints POST de la API.

## 📝 Licencia

MIT
