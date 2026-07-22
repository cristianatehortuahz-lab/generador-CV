# Arquitectura — Generador de CV

## Visión general

```
┌──────────────────┐
│   VIVO Browser   │
└────────┬─────────┘
         │ GET /display/n<ID>
         ▼
┌──────────────────────────────────────┐
│ Tomcat (webapps/HUBvivo115)                │
│ ┌──────────────────────────────────┐ │
│ │ individual--foaf-person.ftl      │ │ ← renderiza perfil + widget
│ └──────┬───────────────────────────┘ │
│        │                              │
│        ▼ (click "Descargar Hoja...")  │
│ ┌──────────────────────────────────┐ │
│ │ hub-cv-widget.js (inline)        │ │ ← abre modal, selecciona formato
│ └──────┬───────────────────────────┘ │
│        │ GET /api/cv/generate?...   │
│        ▼                              │
│ ┌──────────────────────────────────┐ │
│ │ CVProxyServlet                   │ │ ← reenvía al backend
│ └──────┬───────────────────────────┘ │
└────────┼──────────────────────────────┘
         │ GET localhost:3001/api/cv/generate
         ▼
┌──────────────────────────────────────┐
│ Backend Python (localhost:3001)      │
│ ┌──────────────────────────────────┐ │
│ │ cv_api.py                        │ │ ← servidor HTTP y rutas
│ └───────────────┬──────────────────┘ │
│                 ▼                    │
│ ┌──────────────────────────────────┐ │
│ │ cv_generator.py                  │ │ ← extrae datos de Solr
│ └───────────────┬──────────────────┘ │
│                 ▼                    │
│ ┌───────────────┐  ┌───────────────┐ │
│ │ harvard_cv.py │  │ pdf_filler.py │ │ ← construyen el documento
│ └──────┬────────┘  └──────┬────────┘ │
│        └────────┬─────────┘          │
│                 ▼                    │
│   LibreOffice (Linux) / Word (Win)   │
│                 ▼                    │
│                PDF                   │
└─────────────────┬────────────────────┘
     │ Content-Disposition: attachment
     ▼ application/pdf
┌──────────────────┐
│   VIVO Browser   │ ← descarga CV_NombreApellido.pdf
└──────────────────┘
```

---

## Componentes

### 1. Frontend (Tomcat)

**Archivo:** `themes/wilma/templates/individual--foaf-person.ftl`

- Renderiza perfil de investigador
- Inyecta botón rojo **"Descargar Hoja de Vida"** bajo la foto
- Script inline (JS) en mismo FTL:
  - Abre modal de selección: "Harvard" / "Europass"
  - GET a `/api/cv/generate?uri=<perfil>&format=<formato>`

**Estilos:** `themes/wilma/css/hub-cv-widget.css`
- Botón rojo (#b91c2e), modal, spinner de carga

### 2. Proxy (Tomcat)

**Archivo:** `WEB-INF/classes/co/edu/urosario/hubur/CVProxyServlet.java`

**Responsabilidades:**
- Recibe GET `/api/cv/generate?uri=<uri>&format=<formato>`
- **Validación:** solo método GET y ruta `/generate`
- **No valida `format`:** lo reenvía tal cual; el backend decide qué formatos
  existen, así un formato nuevo no obliga a recompilar el servlet
- Reenvía `X-Forwarded-For` con la IP real del cliente
- **Timeout:** 10s connect, 90s read (LibreOffice puede tardar en arranque en frío)
- **Error:** 502 Bad Gateway (no expone detalles internos)

**Respuesta correcta:** `Content-Type: application/pdf` + `Content-Disposition: attachment`

### 3. Backend Python (localhost:3001)

**Archivo principal:** `cv_api.py`

**Componentes internos:**

#### 3.1 HTTP Server
- `RobustHTTPServer`: ThreadingHTTPServer resiliente
- `CVHandler`: enrutador de peticiones
- Suporta `GET /api/cv/generate?uri=<uri>&format=<formato>`

#### 3.2 Límite de peticiones
- Máx 5 por minuto y por IP; evita saturar LibreOffice

#### 3.3 cv_generator.py (extracción)
- Busca el investigador en Solr por URI
- Extrae:
  - Nombre, apellido, email, teléfono
  - Educación (grados, años, instituciones)
  - Experiencia laboral / posiciones académicas
  - Publicaciones (título, año, DOI, journal)
  - Grants y financiación
  - Habilidades, idiomas
- Enriquece los datos consultando la ficha del investigador en VIVO (`VIVO_BASE_URL`);
  si VIVO no responde, continúa con lo que haya en Solr

#### 3.4 harvard_cv.py (generador Harvard)
- Usa plantilla DOCX (`2025-template_bullet (3).docx`)
- Rellena con datos del extracto
- Convierte DOCX→PDF:
  - **Linux:** LibreOffice headless (`soffice --headless --convert-to pdf`)
  - **Windows:** Microsoft Word vía COM (requiere `pywin32` y `docx2pdf`)
- Devuelve bytes PDF + header `Content-Disposition`

#### 3.5 pdf_filler.py (generador Europass)
- Construye el documento con `python-docx` siguiendo la maqueta Europass
- Incorpora el logo (`europass_logo.png`)
- Convierte a PDF por la misma vía que Harvard y devuelve el archivo

### 4. Solr (data source)

**URL:** `http://localhost:8983/solr/vivocore`

Backend consulta:
```
/select?q=uri:"http://localhost:8080/display/n123"&rows=1&wt=json
```

Devuelve documento con campos: `name`, `lastName`, `email`, `educationDegree`, `publicationTitle`, etc.

---

## Flujo de datos

```
1. Usuario hace clic en "Descargar Hoja de Vida" en perfil
   → JS envía GET /api/cv/generate?uri=http://localhost:8080/display/n123&format=harvard-pdf

2. CVProxyServlet valida método (GET) y ruta (/generate)

3. CVProxyServlet añade X-Forwarded-For con la IP del cliente
   y reenvía a localhost:3001/api/cv/generate?...

5. cv_api.py:
   - Extrae URI del query param
   - Llama cv_generator.extract_cv(uri)

6. cv_generator.py:
   - Consulta Solr: /select?q=uri:"..."
   - Extrae datos (nombre, educación, pubs, etc.)
   - Retorna dict con campos normalizados

7. harvard_cv.py o pdf_filler.py:
   - Toma dict de datos
   - Rellena plantilla (DOCX o PDF)
   - Convierte DOCX→PDF (si es Harvard)
   - Retorna bytes PDF

8. CVProxyServlet:
   - Recibe bytes PDF
   - Devuelve con:
     - HTTP 200
     - Content-Type: application/pdf
     - Content-Disposition: attachment; filename="Nombre_Apellido_harvard.pdf"

9. Navegador:
   - Reconoce `Content-Disposition: attachment`
   - Descarga archivo
```

---

## Seguridad

### 1. Aislamiento de red
- El backend escucha solo en loopback (`BIND_HOST`, `127.0.0.1` por defecto)
- No es alcanzable desde fuera del servidor; el navegador entra por el proxy
- **No hay clave de API.** Si se cambiara `BIND_HOST` a `0.0.0.0`, el servicio
  quedaría expuesto sin autenticación y habría que reintroducir un control

### 2. Validación de entrada
- Backend valida `uri` y `format`; responde 400 si no los reconoce
- Backend sanitiza errores (no devuelve trazas al cliente)

### 3. Rate-limit
- Backend limita 5 req/min por IP
- Proxy reenvía `X-Forwarded-For` (para rate-limit real, no por 127.0.0.1)

### 4. Content-Type
- Proxy fuerza `Content-Type: application/pdf`
- Proxy asegura `X-Content-Type-Options: nosniff` (evita content-sniffing)

### 5. Manejo de errores
- Backend no expone rutas internas, trazas de Python
- Proxy devuelve "Servicio de hojas de vida no disponible" (genérico)
- Logs estructurados (sin datos sensibles)

---

## Escalabilidad / Limitaciones

### Limitaciones actuales
- **LibreOffice:** 90s timeout para DOCX→PDF (puede ser corto si hay muchos formatos)
- **Caché en memoria:** resultados se guardan en RAM (restart = pérdida de caché)

### Mejoras futuras
- Caché distribuido (Redis)
- Queue (Celery) para generaciones largas
- Múltiples workers Python (load balancer frente a localhost:3001)
