# Tibia Bestiary - Frontend

Frontend del sistema de bestiario de Tibia construido con React, TypeScript y Tailwind CSS.

## 🚀 Características

- ✅ Interfaz inspirada en el diseño de Tibia
- ✅ Búsqueda y filtrado de criaturas
- ✅ Vista detallada de cada criatura con stats, loot y spawn locations
- ✅ Sistema de recomendación de zonas de hunt
- ✅ Diseño responsive y moderno
- ✅ Tipado completo con TypeScript

## 📋 Requisitos

- Node.js 18+
- npm o yarn

## 🛠️ Instalación

1. Instalar dependencias:
```bash
npm install
```

2. Copiar variables de entorno (opcional):
```bash
cp .env.example .env
```

3. Configurar URL del API (opcional):
Editar `.env` y establecer:
```
VITE_API_URL=http://localhost:8000/api/v1
```

## 🏃 Ejecución

Modo desarrollo:
```bash
npm run dev
```

La aplicación estará disponible en: http://localhost:5173

Build de producción:
```bash
npm run build
```

Preview del build:
```bash
npm run preview
```

## 📁 Estructura del Proyecto

```
frontend/
├── src/
│   ├── components/         # Componentes reutilizables
│   │   ├── Header.tsx
│   │   ├── CreatureCard.tsx
│   │   ├── HuntZoneCard.tsx
│   │   ├── Loading.tsx
│   │   └── ErrorMessage.tsx
│   ├── pages/             # Páginas principales
│   │   ├── CreaturesPage.tsx
│   │   ├── CreatureDetailPage.tsx
│   │   └── HuntRecommendationsPage.tsx
│   ├── services/          # Servicios API
│   │   └── api.ts
│   ├── types/             # Definiciones TypeScript
│   │   └── index.ts
│   ├── App.tsx            # Componente principal
│   ├── main.tsx           # Punto de entrada
│   └── index.css          # Estilos globales
├── public/                # Archivos estáticos
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

## 🎨 Diseño

El frontend utiliza un tema inspirado en Tibia con:
- Colores verde oscuro y dorado característicos
- Fuente pixelada "Press Start 2P"
- Bordes y paneles estilo medieval
- Animaciones sutiles y efectos hover

### Paleta de Colores

- **Dark Green**: `#1a3a1a` - Fondo principal
- **Green**: `#2d5016` - Fondos secundarios
- **Gold**: `#c6a664` - Textos importantes
- **Light Gold**: `#e0c891` - Textos secundarios

## 📄 Páginas

### Creatures Page (`/`)
- Lista de todas las criaturas
- Búsqueda por nombre
- Filtro por dificultad
- Tarjetas con información básica

### Creature Detail Page (`/creature/:id`)
- Información completa de la criatura
- Stats detallados (HP, EXP, Armor, Speed, etc.)
- Debilidades y resistencias
- Lista completa de loot con rareza
- Spawn locations

### Hunt Recommendations Page (`/recommendations`)
- Selector de vocación (Knight, Paladin, Sorcerer, Druid)
- Slider de nivel
- Sistema de scoring inteligente
- Top 10 zonas recomendadas
- Razones de la recomendación

## 🔌 Integración con API

El frontend se conecta al backend FastAPI a través de:

```typescript
// src/services/api.ts
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// Creatures API
creaturesApi.getAll(params)
creaturesApi.getById(id)
creaturesApi.getByName(name)

// Hunt Zones API
huntZonesApi.getAll(params)
huntZonesApi.getById(id)
huntZonesApi.getRecommendations(vocation, level, limit)
```

## 🌐 Rutas

| Ruta | Descripción |
|------|-------------|
| `/` | Lista de criaturas |
| `/creature/:id` | Detalle de criatura |
| `/recommendations` | Buscador de zonas de hunt |

## 🚀 Deployment

Build para producción:
```bash
npm run build
```

Los archivos se generarán en `/dist`. Puedes servir este directorio con cualquier servidor web estático.

Ejemplo con Nginx:
```nginx
server {
    listen 80;
    server_name tibia-bestiary.com;
    root /path/to/dist;
    
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

## 📝 Licencia

MIT
