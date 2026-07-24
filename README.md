# Generador de Hojas de Vida (CV) — HUB-UR

Sistema modular para generar hojas de vida en formatos **Harvard** (DOCX→PDF vía Word/LibreOffice) y **Europass** (PDF con datos inyectados) a partir de perfiles de investigador en VIVO.

---

## 🔄 Flujo en tiempo de ejecución

```
Navegador (perfil de investigador)
   │  click "Descargar Hoja de Vida" → GET /api/cv/generate?uri=…&format=harvard-pdf
   ▼
CVProxyServlet (Tomcat, webapps/HUBvivo115)
   │  reenvía la petición al backend
   ▼  GET localhost:3001/api/cv/generate?…
cv_api.py (Python, localhost:3001)
   │  cv_generator extrae los datos de Solr
   │  harvard_cv.py (DOCX→PDF vía LibreOffice) | pdf_filler.py (Europass)
   ▼  application/pdf + Content-Disposition: attachment
Navegador descarga  Nombre_Apellido_harvard.pdf
```

**Puntos clave del flujo:**

- El navegador **nunca habla directo con el backend Python**: siempre pasa por el
  servlet, que es quien conoce la dirección interna del servicio.
- `cv_api.py` escucha **solo en `localhost:3001`**. No está expuesto a la red, y
  ese aislamiento es el control de acceso (no hay clave de API).
- Añadir un formato nuevo es escribir **un archivo** en `backend/` y registrarlo
  en `cv_api.py`. **No se recompila Java**: el servlet reenvía el parámetro
  `format` tal cual, así que no hay que tocarlo ni redesplegarlo.

---

## 📖 Empezar

- **Desarrolladores:** ver [`GUIA_INSTALACION_FINAL.md`](GUIA_INSTALACION_FINAL.md)
- **Administradores:** ver [`documentacion/02-guia-despliegue.md`](documentacion/02-guia-despliegue.md)
- **Integración con API:** ver [`API.md`](API.md) (endpoints, parámetros, ejemplos)
- **Documentación completa:** [`documentacion/README.md`](documentacion/README.md)

---

## 📁 Estructura

```
generador-CV/
├─ README.md (este archivo)
├─ GUIA_INSTALACION_FINAL.md (instalación rápida)
├─ documentacion/ → arquitectura, despliegue, configuración, formatos, etc.
├─ backend/ → Python (servidor, extracción de datos y generadores de formato)
├─ frontend/ → Widget FTL + CSS (botón "Descargar Hoja de Vida")
├─ webapp/ → Proxy servlet + web.xml (reenvía al backend)
└─ verificacion/ → verify_fidelity.py, _demo_formato.py
```

---

## 🏗️ Arquitectura (resumen)

1. **Widget (FTL):** Botón en perfil → abre modal de selección (Harvard/Europass)
2. **Proxy (Java/Tomcat):** Reenvía `/api/cv/generate` al backend Python en `localhost:3001`
3. **Backend (Python):** Extrae datos de Solr, genera CV según formato, devuelve PDF
4. **Descarga:** `Content-Disposition: attachment` → navegador descarga con nombre `Nombre_Apellido_harvard.pdf`

Ver [`documentacion/01-arquitectura.md`](documentacion/01-arquitectura.md) para detalles.

---

## 🔑 Variables de entorno

| Variable | Dónde | Valor |
|----------|-------|-------|
| `VIVO_BASE_URL` | Backend | `http://localhost:8080` |
| `SOFFICE_PATH` | Backend | ruta a LibreOffice (si es Linux) |
| `HARVARD_TEMPLATE` | Backend | ruta a plantilla DOCX |
| `EUROPASS_TEMPLATE` | Backend | ruta a plantilla PDF |

Ver [`documentacion/03-configuracion.md`](documentacion/03-configuracion.md).

---

## 🚀 Despliegue rápido

```bash
# 1. Clonar
git clone https://github.com/cristianatehortuahz-lab/generador-CV.git
cd generador-CV

# 2. Backend (Linux/macOS)
cd backend
chmod +x start_cv.sh
# Editar .env (copiar de .env.example)
./start_cv.sh

# 3. Frontend (subir a Tomcat via XFTP)
# - frontend/individual--foaf-person.ftl → webapps/HUBvivo115/themes/wilma/templates/
# - frontend/hub-cv-widget.css → webapps/HUBvivo115/themes/wilma/css/
# - webapp/CVProxyServlet.java → webapps/HUBvivo115/WEB-INF/classes/co/edu/urosario/hubur/
# - webapp/web.xml → webapps/HUBvivo115/WEB-INF/

# 4. Verificar (en el servidor)
curl -s "http://localhost:8080/api/cv/generate?uri=test&format=harvard-pdf" -o /tmp/test.pdf
file /tmp/test.pdf  # → PDF document
```

Ver [`GUIA_INSTALACION_FINAL.md`](GUIA_INSTALACION_FINAL.md) para pasos completos.

---

## ✅ Características

- ✅ **Dos formatos:** Harvard (DOCX) y Europass (PDF)
- ✅ **Aislamiento:** el backend solo escucha en loopback; no es alcanzable desde fuera del servidor
- ✅ **Modular:** cada formato es una clase independiente (fácil agregar nuevos)
- ✅ **Caché:** resultados en memoria (evita regeneraciones innecesarias)
- ✅ **Datos desde Solr:** el perfil del investigador se toma del índice de Solr
- ✅ **Validación técnica:** `verify_fidelity.py` chequea márgenes, fuentes, alineación
- ✅ **Superficie mínima:** el backend solo expone `/api/cv/generate` y `/health`; cualquier otra ruta responde 404

---

## 🐛 Troubleshooting

| Problema | Causa | Solución |
|----------|-------|----------|
| "Error, intente de nuevo" | Backend no arranca | `tail -f backend.log` |
| HTTP 502 | Puerto 3001 caído | `lsof -i :3001` y `./start_cv.sh` |
| PDF vacío | Solr sin datos para el investigador | Verificar URI en VIVO |
| Letras deformadas | Fuentes faltantes en server | Instalar `fonts-dejavu` (Linux) |

Ver [`documentacion/05-mantenimiento.md`](documentacion/05-mantenimiento.md) para más.

---

## 👥 Contribuciones

Las mejoras van contra `main` del repo. PRs bienvenidas.

---

## 📄 Licencia

Interna HUB-UR. No distribuir.
