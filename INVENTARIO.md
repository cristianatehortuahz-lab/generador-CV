# Inventario — Generador de Hojas de Vida HUB-UR

Todos los archivos del repositorio, agrupados por función, con una línea de qué
hace cada uno. Para el flujo completo ver [`README.md`](README.md); para los
endpoints, [`API.md`](API.md).

**Estado**, columna derecha: ✅ verificado idéntico contra el servidor de
prácticas (julio 2026) · ⚠️ diferencia conocida, ver nota · — no aplica (doc).

---

## Backend — Python (`localhost:3001`, solo accesible desde el servidor)

| Archivo | Qué hace | Estado |
|---|---|---|
| [`backend/cv_api.py`](backend/cv_api.py) | Servidor HTTP. Expone `GET /api/cv/generate?uri=...&format=...` y `GET /health`. Sin clave de API: el aislamiento a `localhost` es el control de acceso. | ⚠️ el servidor **todavía tiene el código de API key**; el repo ya no. Falta desplegar la versión del repo. |
| [`backend/cv_generator.py`](backend/cv_generator.py) | Extrae los datos del investigador desde Solr + VIVO y los normaliza a un `CVData` común para todos los formatos. | ✅ (paquete `co.edu.urosario.hubur` del proxy verificado) |
| [`backend/cv_format_utils.py`](backend/cv_format_utils.py) | Utilidades compartidas de mapeo de datos (educación, publicaciones, contacto) que usan Harvard y Europass, para no duplicar parseo frágil. | — |
| [`backend/harvard_cv.py`](backend/harvard_cv.py) | Genera el formato Harvard: clona la plantilla oficial (`formatos/2025-template_bullet (3).docx`) y la convierte a PDF vía Word/LibreOffice. | — |
| [`backend/pdf_filler.py`](backend/pdf_filler.py) | Genera el formato Europass: replica el layout oficial de europass.europa.eu. | — |
| [`backend/start_cv.sh`](backend/start_cv.sh) | Script de arranque del backend en el servidor. | — |
| [`backend/requirements.txt`](backend/requirements.txt) | Dependencias Python (`python-docx`, etc.). | — |
| [`backend/.env.example`](backend/.env.example) | Plantilla de variables de entorno (ninguna es una clave secreta: el backend ya no usa API key). | — |
| [`backend/formatos/2025-template_bullet (3).docx`](<backend/formatos/2025-template_bullet (3).docx>) | Plantilla oficial de Harvard sobre la que se clona cada CV. | — |
| [`backend/formatos/europass_template.pdf`](backend/formatos/europass_template.pdf) | Ejemplar de referencia de Europass (con datos falsos) usado para verificar fidelidad visual — **no** es una plantilla rellenable. | — |
| [`backend/formatos/europass_logo.png`](backend/formatos/europass_logo.png) | Logo oficial usado en el render de Europass. | — |

## Frontend — Widget de descarga

| Archivo | Qué hace | Estado |
|---|---|---|
| [`frontend/individual--foaf-person.ftl`](frontend/individual--foaf-person.ftl) | Página de perfil del investigador. Sobre la plantilla base de VIVO, añade el botón desplegable "Descargar Hoja de Vida" (`id="hub-cv-widget"`). | ✅ |
| [`frontend/hub-cv-widget.css`](frontend/hub-cv-widget.css) | Estilos del botón de descarga. | ✅ idéntico byte a byte |

## Webapp — Proxy Java

| Archivo | Qué hace | Estado |
|---|---|---|
| [`webapp/CVProxyServlet.java`](webapp/CVProxyServlet.java) | Reverse proxy: reenvía `/api/cv/generate` al backend Python en `localhost:3001`. El navegador nunca habla directo con Python. | ✅ paquete `co.edu.urosario.hubur` coincide con el `.class` del servidor |
| [`webapp/web.xml`](webapp/web.xml) | **Copia completa** del `web.xml` del servidor (no solo de este módulo): incluye también los servlets del buscador y del mapa, como referencia. Al desplegar, solo se añade el bloque de `CVProxyServlet` — nunca se sobrescribe el `web.xml` real con este archivo entero. | ✅ facetas verificadas = servidor. El fragmento de `busquedas` propone otro orden (no desplegado) — ver nota en el propio archivo |

## Verificación

| Archivo | Qué hace |
|---|---|
| [`verificacion/verify_fidelity.py`](verificacion/verify_fidelity.py) | Scorecard de fidelidad: compara un PDF generado contra el oficial de referencia (tamaño de página, fuentes, con PyMuPDF). |
| [`verificacion/_demo_formato.py`](verificacion/_demo_formato.py) | Ejemplo ejecutable de cómo agregar un formato nuevo, siguiendo el "Patrón A" documentado. |

## Documentación

| Archivo | Qué hace |
|---|---|
| [`README.md`](README.md) | Punto de entrada: flujo en tiempo de ejecución, estructura del repo. |
| [`API.md`](API.md) | Endpoints, parámetros, ejemplos de uso de la API. |
| [`documentacion/README.md`](documentacion/README.md) | Índice de la documentación ampliada. |
| [`documentacion/01-arquitectura.md`](documentacion/01-arquitectura.md) | Arquitectura del módulo. |
| [`documentacion/02-guia-despliegue.md`](documentacion/02-guia-despliegue.md) | Guía de despliegue para administradores. |
| [`documentacion/03-configuracion.md`](documentacion/03-configuracion.md) | Configuración por ambiente. |
| [`documentacion/04-formatos-harvard-europass.md`](documentacion/04-formatos-harvard-europass.md) | Detalle de los formatos Harvard y Europass. |
| [`documentacion/05-mantenimiento.md`](documentacion/05-mantenimiento.md) | Mantenimiento y troubleshooting. |
| [`documentacion/06-validacion-tecnica-formato.md`](documentacion/06-validacion-tecnica-formato.md) | Cómo se valida la fidelidad visual de un formato. |
| [`documentacion/07-agregar-nuevo-formato.md`](documentacion/07-agregar-nuevo-formato.md) | Patrón para agregar un formato de CV nuevo. |
| [`documentacion/09-referentes-de-formato.md`](documentacion/09-referentes-de-formato.md) | Ejemplares de referencia usados para verificar cada formato. |
| [`GUIA_INSTALACION_FINAL.md`](GUIA_INSTALACION_FINAL.md) | Instalación rápida. |
| [`DESPLIEGUE_MAESTRO.md`](DESPLIEGUE_MAESTRO.md) | Procedimiento maestro de despliegue del sistema completo. |

---

## Nota sobre el formato NIH Biosketch

Durante el desarrollo se construyó un generador completo para el formato NIH
Biographical Sketch (`nih_biosketch.py`). **No se incluyó en este repositorio**
porque el `cv_api.py` del servidor de prácticas solo registra `harvard-pdf` y
`europass-pdf` — mantenerlo fuera evita que el repo prometa un formato que el
servidor no sirve. El archivo se conserva en
`Desktop/HUB-UR/experimentos-cv/nih_biosketch.py` por si se decide integrarlo
más adelante (solo requiere: copiarlo a `backend/`, registrarlo en `cv_api.py`
igual que Harvard/Europass, y actualizar este inventario y el README).

## Deuda técnica

**El scraping de HTML debe retirarse; la extracción debe ser por API.**
`cv_generator.py` usa tres fuentes: Solr y JSON-LD (consumo estructurado, se
conservan) y **`vivo_html`**, que obtiene **overview, educación y tesis
dirigidas** aplicando expresiones regulares sobre la página del perfil
(`_extract_from_vivo`). Si cambia una plantilla o se actualiza VIVO, esas tres
secciones del CV quedan vacías **sin lanzar error**.

Esos datos existen en el modelo RDF; la vía de menor fricción es pedir el
JSON-LD completo del individuo (ya se parsea JSON-LD embebido) o indexarlos en
Solr.

Detalle y alternativas: `DEUDA-TECNICA-Scraping-a-API.md` (raíz de HUB-UR).

## Pendientes conocidos (a resolver en el servidor)

1. **`cv_api.py`** — el repo ya no tiene código de API key; el servidor sí.
   Falta desplegar la versión del repo para que coincidan.
**Ya resuelto:** las facetas de `web.xml` se verificaron contra el servidor y
coinciden (`facet_expertiseAreas` primero). El fragmento del repo `busquedas`
propone otro orden, decisión de producto pendiente, no un error.
