# 🐲 Tibia Bestiary System

Sistema completo de bestiario de Tibia con backend FastAPI y frontend React, incluyendo recomendaciones inteligentes de zonas de hunt basadas en vocación y nivel.

![Tibia](https://img.shields.io/badge/Game-Tibia-green)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-teal)
![React](https://img.shields.io/badge/React-18.2-cyan)
![TypeScript](https://img.shields.io/badge/TypeScript-5.2-blue)

## 🎯 Características Principales

### Backend (FastAPI + SQLite)
- ✅ API RESTful completa con documentación Swagger
- ✅ Base de datos SQLite normalizada con relaciones
- ✅ Integración real con TibiaData y TibiaWiki Fandom para criaturas, guilds y validación
- ✅ Sistema de rifas de guild con participantes por cuenta local, historial y reruns administrados
- ✅ Modo mock aislado por configuración con `USE_MOCK_DATA=false` por defecto
- ✅ Filtros, búsquedas y normalización de nombres para el bestiary

### Frontend (React + TypeScript)
- ✅ Diseño inspirado en la estética de Tibia
- ✅ Interfaz responsive y moderna
- ✅ Búsqueda, orden y manejo explícito de loading/error/empty states
- ✅ Vista detallada con metadata real disponible y fallback a `Unknown` cuando falta en la fuente
- ✅ Consola administrativa para rifas de guild
- ✅ Consumo de API por ruta relativa `/api/v1` para despliegue detrás de Nginx

## 🏗️ Arquitectura

```
tibia-bestiary/
├── backend/                 # FastAPI Backend
│   ├── app/
│   │   ├── api/v1/         # Endpoints REST
│   │   ├── core/           # Configuración
│   │   ├── db/             # Database setup
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   └── services/       # Lógica de negocio
│   ├── main.py             # App principal
│   ├── seed_db.py          # Datos iniciales
│   └── requirements.txt
│
└── frontend/               # React Frontend
    ├── src/
    │   ├── components/     # Componentes UI
    │   ├── pages/          # Páginas principales
    │   ├── services/       # API client
    │   ├── types/          # TypeScript types
    │   └── App.tsx
    ├── package.json
    └── vite.config.ts
```

## 🚀 Inicio Rápido

### 1. Backend Setup

```bash
cd backend

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Copiar configuración
cp .env.example .env

# Mantener datos reales en producción
# USE_MOCK_DATA=false

# Inicializar base de datos
python seed_db.py

# Iniciar servidor
python main.py
```

El backend estará disponible en: http://localhost:8000

📚 Documentación API: http://localhost:8000/docs

### APIs externas usadas
- TibiaData v4: mundos, personajes, guilds
- TibiaWiki Fandom MediaWiki API: bestiary, loot, locations, sprites

### Limitaciones conocidas
- TibiaData no expone un account ID público utilizable para sorteos.
- La restricción de una participación y un premio por cuenta se resuelve con usuarios locales autenticados y sus personajes vinculados.
- Si TibiaWiki o TibiaData no exponen un campo, la UI muestra `Unknown` o `Not available` en vez de inventar valores.

### 2. Frontend Setup

```bash
cd frontend

# Instalar dependencias
npm install

# Iniciar servidor de desarrollo
npm run dev
```

El frontend estará disponible en: http://localhost:5173

## 📊 Modelo de Datos

### Tablas Principales

**Creatures** (Criaturas)
- Información básica: nombre, HP, experiencia, armor, speed
- Stats de combate: max_damage, summon_cost, convince_cost
- Clasificación: difficulty, occurrence, is_boss
- Descripción y comportamiento

**Elements** (Elementos de Daño)
- Physical, Fire, Ice, Energy, Earth, Holy, Death
- Asociaciones con criaturas (weaknesses y resistances)

**Loot** (Items)
- Relación con criaturas
- Rareza y porcentaje de drop
- Valor en gold

**Hunt Zones** (Zonas de Cacería)
- Información de ubicación y acceso
- Niveles recomendados por vocación
- Stats de exp/hora y profit/hora
- Requisitos (quest, premium)

**Spawn Locations** (Ubicaciones de Spawn)
- Vincula criaturas con zonas
- Cantidad de spawns
- Notas especiales

### Relaciones

```
Creature ←→ Element (many-to-many)
Creature → Loot (one-to-many)
Creature ←→ HuntZone (many-to-many via SpawnLocation)
```

## 🎮 Endpoints de la API

### Criaturas

```bash
# Listar todas las criaturas
GET /api/v1/creatures/?skip=0&limit=100&search=dragon&difficulty=Hard

# Obtener criatura por ID
GET /api/v1/creatures/3

# Obtener criatura por nombre
GET /api/v1/creatures/name/Dragon

# Crear criatura
POST /api/v1/creatures/
```

### Zonas de Hunt

```bash
# Listar zonas
GET /api/v1/hunt-zones/?min_level=50&max_level=100

# Obtener zona por ID
GET /api/v1/hunt-zones/2

# Recomendaciones de hunt
GET /api/v1/hunt-zones/recommendations/knight?level=80&limit=10
```

## 🧠 Sistema de Recomendación

El algoritmo de recomendación considera múltiples factores:

1. **Vocación Match** (40 puntos max)
   - Zona recomendada para la vocación

2. **Nivel** (30 puntos max)
   - Coincidencia con nivel recomendado
   - Rango de nivel apropiado

3. **Experiencia** (15 puntos max)
   - Exp/hora promedio de la zona

4. **Profit** (10 puntos max)
   - Gold/hora promedio

5. **Tamaño** (8 puntos max)
   - Zonas más grandes = más spawns

6. **Penalizaciones**
   - -5 puntos si requiere quest

**Score final**: 0-100 puntos

## 🎨 Diseño UI/UX

### Paleta de Colores Tibia

```css
Dark Green:  #1a3a1a  /* Fondo principal */
Green:       #2d5016  /* Fondos secundarios */
Light Green: #3d6b1f  /* Elementos activos */
Gold:        #c6a664  /* Títulos y destacados */
Light Gold:  #e0c891  /* Textos secundarios */
Brown:       #3d2817  /* Paneles */
Dark Brown:  #2a1810  /* Paneles oscuros */
```

### Componentes Clave

- **CreatureCard**: Tarjeta de criatura con stats básicos
- **HuntZoneCard**: Info de zona con requisitos y stats
- **Loading**: Spinner con estilo Tibia
- **ErrorMessage**: Manejo de errores con retry

### Páginas

1. **Creatures Page**: Grid de criaturas con búsqueda
2. **Creature Detail**: Info completa + loot + spawns
3. **Hunt Recommendations**: Selector de vocación/nivel

## 📦 Datos de Ejemplo Incluidos

### Criaturas
- Rat (Trivial)
- Rotworm (Easy)
- Dragon (Medium)
- Dragon Lord (Hard)
- Demon (Hard)

### Zonas de Hunt
- Rookgaard Sewers (Nivel 1-8)
- Fibula Rotworm Cave (Nivel 8-25)
- Darashia Dragon Lair (Nivel 40-100)
- Mintwallin Dragon Lords (Nivel 80-150)
- Goroma Demons (Nivel 150+)

## 🔧 Tecnologías Utilizadas

### Backend
- **FastAPI**: Framework web moderno y rápido
- **SQLAlchemy**: ORM para Python
- **Pydantic**: Validación de datos
- **SQLite**: Base de datos ligera
- **Uvicorn**: Servidor ASGI

### Frontend
- **React 18**: Librería UI
- **TypeScript**: Tipado estático
- **Vite**: Build tool rápido
- **Tailwind CSS**: Framework CSS utility-first
- **Axios**: Cliente HTTP
- **React Router**: Navegación

## 🚀 Deployment

### Quick Deployment con PM2 y Nginx

```bash
# 1. Ejecutar script de instalación
./install.sh

# 2. Configurar nginx (como root)
sudo ln -sf /forge/tibiahub/nginx-tibiahub.conf /etc/nginx/sites-available/tibiahub
sudo ln -sf /etc/nginx/sites-available/tibiahub /etc/nginx/sites-enabled/tibiahub
sudo nginx -t
sudo systemctl reload nginx

# 3. Validar certificado y redirección HTTPS
sudo certbot certificates
sudo openssl s_client -connect tibiahub.domoforge.com:443 -servername tibiahub.domoforge.com
curl -I http://tibiahub.domoforge.com
curl -I https://tibiahub.domoforge.com

# 4. Iniciar servicios con PM2
./start.sh

# 5. Guardar configuración PM2
pm2 save
pm2 startup
```

**Acceso (HTTPS):**
- Frontend: https://tibiahub.domoforge.com
- API Docs: https://tibiahub.domoforge.com/docs

### Gestión de Servicios PM2

```bash
pm2 status                    # Ver estado
pm2 logs                      # Ver logs
pm2 restart all               # Reiniciar todo
./stop.sh                     # Detener servicios
```

### Deployment Manual

#### Backend

```bash
cd backend
pip install -r requirements.txt
python seed_db.py
uvicorn main:app --host 127.0.0.1 --port 8001
```

#### Frontend

```bash
cd frontend
npm install
npm run build
npm run preview -- --port 5174
```

**📖 Ver [DEPLOYMENT.md](DEPLOYMENT.md) para guía completa de deployment**

## 📝 Próximas Características

- [ ] Autenticación de usuarios
- [ ] Sistema de favoritos
- [ ] Comparador de criaturas
- [ ] Calculadora de profit/exp
- [ ] Mapas interactivos
- [ ] Estadísticas de hunt personales
- [ ] Importar datos de TibiaWiki automáticamente
- [ ] Sistema de comentarios y tips
- [ ] Más criaturas y zonas

## 🤝 Contribuir

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para más detalles.

## ⚠️ Disclaimer

Este es un proyecto fan-made no oficial. Tibia es una marca registrada de CipSoft GmbH. Este proyecto no está afiliado, asociado, autorizado, respaldado por, o de ninguna manera conectado oficialmente con CipSoft GmbH.

## 📧 Contacto

Para preguntas o sugerencias, abre un issue en GitHub.

---

**Hecho con ❤️ para la comunidad de Tibia**
