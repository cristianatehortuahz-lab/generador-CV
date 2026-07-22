# API REST — Generador de Hojas de Vida

Especificación de la API HTTP que expone el backend `cv_api.py` en `localhost:3001`.

---

## 📌 Configuración base

```
Servidor:       localhost:3001  (BIND_HOST configurable)
Protocolo:      HTTP/1.1
Autenticación:  ninguna
Límite:         5 solicitudes por minuto y por IP
```

Endpoints disponibles:

| Método | Ruta | Devuelve |
|---|---|---|
| `GET` | `/api/cv/generate` | PDF (`application/pdf`) |
| `GET` | `/health` | JSON de estado |

Cualquier otra ruta, y cualquier método distinto de `GET`/`OPTIONS`, responde `404`.

### Sobre el control de acceso

El servicio **no pide clave de API**. Quien lo protege es la red: el backend
escucha solo en la interfaz de loopback (`BIND_HOST`, `127.0.0.1` por defecto),
de modo que únicamente los procesos del propio servidor pueden alcanzarlo. El
navegador llega a través del proxy `CVProxyServlet` de Tomcat, que reenvía la
petición a `localhost:3001`.

> Si alguna vez se cambia `BIND_HOST` a `0.0.0.0`, el servicio queda expuesto a
> la red **sin ninguna autenticación**. En ese escenario habría que reintroducir
> un control de acceso antes de abrir el puerto.

---

## `GET /api/cv/generate`

Genera la hoja de vida de un investigador.

### Parámetros

| Parámetro | Requerido | Descripción |
|---|---|---|
| `uri` | uno de los dos | URI del investigador en VIVO. Ej: `http://research-hub.urosario.edu.co/individual/nombre-apellido` |
| `name` | uno de los dos | Nombre del investigador, como alternativa a `uri` |
| `format` | no | `harvard-pdf` (por defecto) o `europass-pdf` |

Se acepta también la variante con guion bajo: `harvard_pdf`, `europass_pdf`.

### Petición

```http
GET /api/cv/generate?uri=http://research-hub.urosario.edu.co/individual/boris-julian-pinto-bustamante&format=harvard-pdf HTTP/1.1
Host: localhost:3001
Accept: application/pdf
```

### Respuesta correcta

```http
HTTP/1.1 200 OK
Content-Type: application/pdf
Content-Disposition: attachment; filename="Pinto_Bustamante_Boris_Julin_Harvard.pdf"; filename*=UTF-8''Pinto_Bustamante_Boris_Juli%C3%A1n_Harvard.pdf
Content-Length: 139393
Access-Control-Allow-Origin: http://localhost:8080
Access-Control-Expose-Headers: Content-Disposition, Content-Length

%PDF-1.7...
```

> **Nombres con acentos:** los headers HTTP se codifican en latin-1, así que el
> `Content-Disposition` lleva un `filename=` ASCII de respaldo y un
> `filename*=UTF-8''` (RFC 5987) con el nombre completo.

### Respuestas de error

Todas devuelven `Content-Type: application/json`.

| Código | Cuándo | Cuerpo |
|---|---|---|
| `400` | Faltan `uri` y `name` | `{"error": "Parámetro name o uri requerido"}` |
| `400` | Formato no reconocido | `{"error": "Solo se soportan formatos PDF", "formats": ["harvard-pdf", "europass-pdf"]}` |
| `404` | El investigador no está en Solr | `{"error": "Investigador no encontrado"}` |
| `422` | No se pudo determinar el nombre del titular | `{"error": "No se pudo determinar el nombre del titular; el CV no se generó."}` |
| `429` | Se superó el límite por IP | `{"error": "Demasiadas solicitudes. Intente de nuevo en 60 segundos."}` |
| `500` | Falló la generación del documento | `{"error": "Error generando el PDF Harvard"}` · `{"error": "Error generando el PDF Europass"}` · `{"error": "Error interno generando el CV"}` |
| `503` | Falta un componente | `{"error": "Extractor de datos no disponible"}` · `{"error": "Generador Harvard no disponible"}` · `{"error": "Europass no disponible. Plantilla no encontrada."}` |

La respuesta `429` incluye además el header `Retry-After` con los segundos de espera.

### Ejemplos

```bash
# Harvard (formato por defecto)
curl -s "http://localhost:3001/api/cv/generate?uri=<uri_investigador>" -o harvard.pdf

# Europass
curl -s "http://localhost:3001/api/cv/generate?uri=<uri_investigador>&format=europass-pdf" -o europass.pdf

# Ver los headers de la respuesta
curl -s -D - -o /dev/null "http://localhost:3001/api/cv/generate?uri=<uri_investigador>&format=harvard-pdf"
```

---

## `GET /health`

Estado del servicio y de sus componentes.

```http
GET /health HTTP/1.1
Host: localhost:3001
```

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "status": "ok",
  "services": {
    "solr": "ok",
    "harvard": "ok",
    "europass": "ok",
    "api": "ok"
  },
  "cache_size": 1
}
```

| Campo | Significado |
|---|---|
| `status` | `ok` si Solr responde; `degraded` si no |
| `services.solr` | Resultado del ping al núcleo de Solr |
| `services.harvard` | Si el generador Harvard se cargó al arrancar |
| `services.europass` | Si la plantilla Europass fue encontrada |
| `cache_size` | Investigadores actualmente en caché |

---

## Cómo fluyen los datos

La extracción y la construcción del documento están separadas. Esto es lo que
permite añadir formatos nuevos sin tocar el resto del sistema:

```
Solr ──JSON──► cv_generator.py ──► CVData ──asdict()──► dict de Python
                                                             │
                                          ┌──────────────────┼──────────────────┐
                                          ▼                  ▼                  ▼
                              generate_harvard_pdf   fill_europass    (formato futuro)
```

`CVData` es una estructura neutral, independiente del formato de salida:

| Campo | Contenido |
|---|---|
| `name`, `first_name`, `last_name` | Nombre del titular |
| `email`, `phone`, `address` | Contacto |
| `job_title`, `department`, `faculty` | Vinculación institucional |
| `education` | Formación académica |
| `publications` | Lista de `Publication` (título, año, revista, DOI, volumen, autores…) |
| `grants` | Lista de `Grant` (título, año inicio/fin) |
| `theses` | Lista de `Thesis` (título, año) |
| `expertise_areas`, `overview` | Áreas de conocimiento y reseña |

Añadir un formato consiste en escribir una función que reciba ese diccionario y
devuelva los bytes del documento. Ver
[`documentacion/07-agregar-nuevo-formato.md`](documentacion/07-agregar-nuevo-formato.md).

---

## Comportamiento interno

### Caché

Los datos extraídos de cada investigador se guardan en memoria durante
**5 minutos** (`CV_CACHE_TTL`), con un máximo de **200 entradas** (`CV_CACHE_MAX`).
Una segunda petición para el mismo investigador reutiliza los datos y solo repite
la construcción del documento. La caché se pierde al reiniciar el backend.

### Límite de peticiones

**5 peticiones por minuto y por IP** (`CV_RATE_LIMIT` / `CV_RATE_WINDOW`). No es
una medida de seguridad: evita que varias generaciones simultáneas saturen
LibreOffice, que es costoso. La IP se toma del header `X-Forwarded-For` que
reenvía el proxy; sin él, todas las peticiones llegarían como `127.0.0.1`.

### Generación serializada

Las conversiones a PDF se serializan con un lock global: el motor de conversión no
es reentrante y dos generaciones simultáneas podrían corromperse.

### Origen de los datos

Los datos provienen de **Solr** (`SOLR_URL`), que responde en JSON. El backend
intenta además enriquecerlos consultando VIVO (`VIVO_BASE_URL`); si VIVO no
responde, la generación continúa con lo que haya en Solr y se registra un aviso.

---

## El proxy de Tomcat

El navegador no habla con este backend directamente, sino con `CVProxyServlet`,
que reenvía `/api/cv/*` a `localhost:3001`.

| Código | Origen |
|---|---|
| `400` | Ruta distinta de `/generate` |
| `405` | Método distinto de `GET` |
| `502` | El proxy no pudo contactar al backend (proceso caído o puerto cerrado) |

El proxy **no valida el parámetro `format`**: lo reenvía tal cual y deja que el
backend decida. Así, añadir un formato nuevo no obliga a recompilar el servlet.

El proxy tampoco reenvía el cuerpo de error del backend, para no exponer trazas
internas al navegador.
