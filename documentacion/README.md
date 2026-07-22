# Documentación — Generador de CV

Índice de documentos técnicos y guías de operación.

| Documento | Contenido |
|-----------|----------|
| [01 — Arquitectura](01-arquitectura.md) | Pipeline widget → proxy → API → PDF. Seguridad, flujo de datos. |
| [02 — Guía de despliegue](02-guia-despliegue.md) | Instalación en servidor de prácticas: backend, frontend, verificación. |
| [03 — Configuración](03-configuracion.md) | Variables de entorno, secretos, rutas, integración Solr/VIVO. |
| [04 — Formatos (Harvard/Europass)](04-formatos-harvard-europass.md) | Especificación técnica de cada formato, campos mapeados, origen de datos. |
| [05 — Mantenimiento](05-mantenimiento.md) | Troubleshooting, limitaciones conocidas, escalado, logs. |
| [06 — Validación técnica](06-validacion-tecnica-formato.md) | Cómo `verify_fidelity.py` valida márgenes, fuentes, alineación. |
| [07 — Agregar nuevo formato](07-agregar-nuevo-formato.md) | Guía paso a paso + código de ejemplo para extender a PDF/Word. |
| [09 — Referentes de formato](09-referentes-de-formato.md) | Ejemplares reales y diligenciados de Harvard y Europass para contrastar. |

---

## 🎯 Por rol

**Desarrolladores (agregar features/formatos)**
→ Lee [01 Arquitectura](01-arquitectura.md) + [07 Agregar formato](07-agregar-nuevo-formato.md) + [06 Validación](06-validacion-tecnica-formato.md)

**DevOps/Admins (desplegar en servidor)**
→ Lee [02 Despliegue](02-guia-despliegue.md) + [03 Configuración](03-configuracion.md) + [05 Mantenimiento](05-mantenimiento.md)

**QA (validar formatos)**
→ Lee [04 Formatos](04-formatos-harvard-europass.md) + [06 Validación técnica](06-validacion-tecnica-formato.md)

---

## 🔗 Referencia rápida

**Backend principal:** [`../backend/cv_api.py`](../backend/cv_api.py) (endpoint `/api/cv/generate`)

**Generadores de formato:**
- [`../backend/harvard_cv.py`](../backend/harvard_cv.py) — DOCX → PDF (Word/LibreOffice)
- [`../backend/pdf_filler.py`](../backend/pdf_filler.py) — Europass PDF (inyecta datos)
- [`../backend/cv_generator.py`](../backend/cv_generator.py) — extrae datos de Solr

**Frontend:**
- [`../frontend/individual--foaf-person.ftl`](../frontend/individual--foaf-person.ftl) — widget UI (FreeMarker)
- [`../frontend/hub-cv-widget.css`](../frontend/hub-cv-widget.css) — estilos

**Proxy servlet:**
- [`../webapp/CVProxyServlet.java`](../webapp/CVProxyServlet.java) — reenvía las peticiones al backend

