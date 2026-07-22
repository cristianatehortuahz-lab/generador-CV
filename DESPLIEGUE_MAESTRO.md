# Despliegue Maestro — Generador de CV

**Mapeo de cada archivo del repositorio a su ruta en el servidor** para el módulo de generación de hojas de vida del HUB-UR.

> Este documento cubre **únicamente** el generador de CV. Los otros módulos
> (búsquedas, mapa de coautorías) tienen su propio `DESPLIEGUE_MAESTRO.md` en sus
> respectivos repositorios.

---

> **Sobre las direcciones:** los comandos `curl` y `bash` de esta guía se ejecutan
> **en el servidor**, por eso usan `localhost`. Los pasos de navegador usan
> `<servidor>`, que es la dirección del equipo donde corre Tomcat: en el servidor
> de prácticas, `10.194.194.96` (o `srvcbpbvivo`).

---

## 📍 Ubicaciones

**Contenido del repositorio:**

```
generador-CV/
├── backend/
│   ├── cv_api.py                      (servidor HTTP + endpoint /api/cv/generate)
│   ├── cv_generator.py                (extractor de datos)
│   ├── harvard_cv.py                  (generador Harvard: DOCX→PDF)
│   ├── pdf_filler.py                  (generador Europass)
│   ├── cv_format_utils.py             (helpers de formato)
│   ├── .env.example                   (plantilla de configuración)
│   ├── start_cv.sh                    (script de arranque)
│   └── formatos/
│       ├── 2025-template_bullet (3).docx
│       ├── europass_template.pdf
│       └── europass_logo.png
├── frontend/
│   ├── individual--foaf-person.ftl    (widget + botón "Descargar Hoja de Vida")
│   └── hub-cv-widget.css              (estilos del widget)
└── webapp/
    ├── CVProxyServlet.java            (proxy: reenvía al backend)
    └── web.xml                        (registro del servlet)
```

**Rutas en el servidor (`srvcbpbvivo`, Linux):**

```
/home/admincrai/cv-generator/          ← Backend Python
├── cv_api.py
├── cv_generator.py
├── harvard_cv.py
├── pdf_filler.py
├── cv_format_utils.py
├── .env                               ← copiado de .env.example y editado (NO versionado)
├── start_cv.sh
└── 03-assets/                         ← plantillas (backend/formatos/ del repo)

/opt/tomcat/webapps/HUBvivo115/        ← Frontend + proxy en Tomcat
├── themes/wilma/templates/
│   └── individual--foaf-person.ftl
├── themes/wilma/css/
│   └── hub-cv-widget.css
└── WEB-INF/
    ├── web.xml
    └── classes/co/edu/urosario/hubur/
        ├── CVProxyServlet.java
        └── CVProxyServlet.class       ← generado al compilar

```

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

---

## 🔄 Pasos de despliegue

### PASO 1: Backup en servidor

```bash
# Backend
cd /home/admincrai/cv-generator
tar czf ~/backup_cv_backend_$(date +%F_%T).tgz *.py 03-assets/ 2>/dev/null

# Tomcat
cd /opt/tomcat/webapps/HUBvivo115
tar czf ~/backup_cv_tomcat_$(date +%F_%T).tgz \
  themes/wilma/templates/individual--foaf-person.ftl \
  themes/wilma/css/hub-cv-widget.css \
  WEB-INF/web.xml \
  WEB-INF/classes/co/edu/urosario/hubur/CVProxyServlet.*
```

### PASO 2: Subir backend Python vía XFTP

**Destino:** `/home/admincrai/cv-generator/`

| Archivo del repositorio | Ruta en el servidor |
|---|---|
| `backend/cv_api.py` | `/home/admincrai/cv-generator/` |
| `backend/cv_generator.py` | `/home/admincrai/cv-generator/` |
| `backend/harvard_cv.py` | `/home/admincrai/cv-generator/` |
| `backend/pdf_filler.py` | `/home/admincrai/cv-generator/` |
| `backend/cv_format_utils.py` | `/home/admincrai/cv-generator/` |
| `backend/start_cv.sh` | `/home/admincrai/cv-generator/` |
| `backend/.env.example` | `/home/admincrai/cv-generator/` |
| `backend/formatos/` (carpeta completa) | `/home/admincrai/cv-generator/03-assets/` |

### PASO 3: Subir frontend + proxy vía XFTP

| Archivo del repositorio | Ruta en el servidor |
|---|---|
| `frontend/individual--foaf-person.ftl` | `/opt/tomcat/webapps/HUBvivo115/themes/wilma/templates/` |
| `frontend/hub-cv-widget.css` | `/opt/tomcat/webapps/HUBvivo115/themes/wilma/css/` |
| `webapp/CVProxyServlet.java` | `/opt/tomcat/webapps/HUBvivo115/WEB-INF/classes/co/edu/urosario/hubur/` |
| `webapp/web.xml` | `/opt/tomcat/webapps/HUBvivo115/WEB-INF/` (merge — ver PASO 5) |

### PASO 4: Configurar `.env` en el servidor (XShell)

```bash
cd /home/admincrai/cv-generator
cp .env.example .env
nano .env    # editar los valores reales
```

Contenido mínimo de `.env` (ver `.env.example` para la lista completa):

```bash
PORT=3001
VIVO_BASE_URL=http://localhost:8080
SOLR_URL=http://localhost:8983/solr/vivocore
SOFFICE_PATH=/home/admincrai/lo7/opt/libreoffice7.6/program/soffice
HARVARD_TEMPLATE="/home/admincrai/cv-generator/03-assets/2025-template_bullet (3).docx"   # comillas: la ruta lleva un espacio
EUROPASS_TEMPLATE=/home/admincrai/cv-generator/03-assets/europass_template.pdf
EUROPASS_LOGO=/home/admincrai/cv-generator/03-assets/europass_logo.png
```

### PASO 5: Registrar el servlet en `web.xml` y compilar (XShell)

```bash
# Merge del web.xml (si tu web.xml ya existe, integra el bloque <servlet> del repo)
nano /opt/tomcat/webapps/HUBvivo115/WEB-INF/web.xml

# Compilar el servlet
cd /opt/tomcat/webapps/HUBvivo115/WEB-INF/classes
javac -cp "/opt/tomcat/lib/servlet-api.jar" co/edu/urosario/hubur/CVProxyServlet.java
ls -la co/edu/urosario/hubur/CVProxyServlet.class    # verificar
```

### PASO 6: Permisos

```bash
chmod +x /home/admincrai/cv-generator/start_cv.sh
chmod 644 /opt/tomcat/webapps/HUBvivo115/themes/wilma/templates/individual--foaf-person.ftl
chmod 644 /opt/tomcat/webapps/HUBvivo115/themes/wilma/css/hub-cv-widget.css
```

### PASO 8: Arrancar backend y reiniciar Tomcat

> **Reinicio de Tomcat:** usar siempre `/etc/rc.d/init.d/tomcat stop` seguido de
> `start`. No usar `/opt/tomcat/bin/startup.sh` (arranca sin las variables de
> entorno del sistema y provoca errores de traducción en VIVO) ni confiar en
> `systemctl`: el servicio es SysV y el wrapper puede reportar que está vivo
> cuando en realidad murió.

```bash
# Backend
cd /home/admincrai/cv-generator && ./start_cv.sh
sleep 3 && ss -tlnp | grep 3001         # confirmar puerto activo

# Tomcat
sudo /etc/rc.d/init.d/tomcat stop && sleep 5 && sudo /etc/rc.d/init.d/tomcat start
```

---

## ✅ Verificación

```bash
# 1. Backend arriba
curl -s http://localhost:3001/health

# 2. Generación vía proxy (misma ruta que usa el widget)
curl -s "http://localhost:8080/api/cv/generate?uri=http://localhost:8080/display/n1&format=harvard-pdf" \
  -o /tmp/test.pdf -w "HTTP %{http_code}\n"
file /tmp/test.pdf                       # → PDF document
```

### En navegador


1. `http://<servidor>:8080/` → perfil de investigador
2. Botón rojo **"Descargar Hoja de Vida"** bajo la foto
3. **Harvard** → descarga `Nombre_Apellido_harvard.pdf`
4. **Europass** → descarga `Nombre_Apellido_europass.pdf`

---

## 📝 Checklist final

- [ ] Backup hecho (backend + Tomcat)
- [ ] Backend `.py` subidos a `/home/admincrai/cv-generator/` y `backend/formatos/` a `03-assets/`
- [ ] `.env` creado desde `.env.example` con las rutas del servidor
- [ ] `individual--foaf-person.ftl` y `hub-cv-widget.css` subidos a `webapps/HUBvivo115/…`
- [ ] `CVProxyServlet.java` compilado sin errores (`.class` generado)
- [ ] Bloque `<servlet>` integrado en `web.xml`
- [ ] Backend arrancado (puerto 3001 activo) + Tomcat reiniciado
- [ ] Verificación: `/health` OK, proxy devuelve PDF, widget descarga en navegador

---

## 🐛 Troubleshooting

| Síntoma | Causa | Solución |
|--------|-------|----------|
| "Error, intente de nuevo" (widget) | Backend caído | `./start_cv.sh` en `/home/admincrai/cv-generator/` |
| HTTP 502 (proxy) | Puerto 3001 no responde | `ss -tlnp \| grep 3001` y rearrancar backend |
| 404 en `/api/cv/generate` | Falta registrar el servlet | Revisar bloque `<servlet>` en `web.xml` |
| PDF vacío | Solr sin datos para esa URI | `curl "http://localhost:8983/solr/vivocore/select?q=uri:\"…\""` |
| Letras deformadas | Fuentes faltantes en el server | `sudo yum install dejavu-sans-fonts` |
| 404 en rutas distintas de CV | Comportamiento esperado | Solo `/api/cv/generate` y `/health` están habilitados |
