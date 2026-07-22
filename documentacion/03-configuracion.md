# Configuración — Variables de entorno y setup

## Backend (.env)

Ubicación: `/home/admincrai/cv-generator/.env` (servidor) o `backend/.env` (desarrollo)

| Variable | Descripción | Ejemplo | Requerido |
|----------|-------------|---------|-----------|
| `PORT` | Puerto HTTP del backend | `3001` | Sí (default: 3001) |
| `VIVO_BASE_URL` | URL base de VIVO | `http://localhost:8080` | ✅ Sí |
| `SOLR_URL` | URL del índice Solr | `http://localhost:8983/solr/vivocore` | ✅ Sí |
| `SOFFICE_PATH` | Ruta a LibreOffice (Linux/macOS) | `/home/admincrai/lo7/opt/libreoffice7.6/program/soffice` | Si generas Harvard |
| `HARVARD_TEMPLATE` | Ruta a plantilla DOCX | `/home/admincrai/cv-generator/03-assets/2025-template_bullet (3).docx` | Si generas Harvard |
| `EUROPASS_TEMPLATE` | Ruta a plantilla Europass PDF | `/home/admincrai/cv-generator/03-assets/europass_template.pdf` | Si generas Europass |
| `EUROPASS_LOGO` | Ruta a logo Europass | `/home/admincrai/cv-generator/03-assets/europass_logo.png` | Si generas Europass |

### Validar .env

```bash
# Ver contenido
cat /home/admincrai/cv-generator/.env

# Verificar que todas las claves están
grep -E "PORT|BIND_HOST|VIVO_BASE_URL|SOLR_URL|SOFFICE_PATH" /home/admincrai/cv-generator/.env
```

---

## Tomcat (setenv.sh)

Ubicación: `/opt/tomcat/bin/setenv.sh`

```bash
#!/bin/bash
export CATALINA_OPTS="-Xmx512m -XX:MaxMetaspaceSize=128m -Dvivo.home=/opt/tomcat/vivo-home -Dfile.encoding=UTF-8"
```

El proxy del generador de CV no necesita variables de entorno: reenvía a
`localhost:3001` sin más configuración.

### Aplicar cambios

```bash
# Reiniciar Tomcat para cargar las variables
sudo /etc/rc.d/init.d/tomcat stop && sleep 5 && sudo /etc/rc.d/init.d/tomcat start
```

### Verificar que arrancó

```bash
curl -s -o /dev/null -w "%{http_code}
" http://localhost:8080/HUBvivo115/
```

---

## Rutas en servidor

```
/home/admincrai/cv-generator/
├── cv_api.py (endpoint principal)
├── cv_generator.py (extrae datos)
├── harvard_cv.py (genera Harvard)
├── pdf_filler.py (genera Europass)
├── .env (secretos, no versionado)
├── .env.example (plantilla)
├── start_cv.sh (arranca backend)
├── backend.log (logs)
├── cv_format_utils.py (helpers de formato)
└── formatos/
    ├── 2025-template_bullet (3).docx
    ├── europass_template.pdf
    └── europass_logo.png

/opt/tomcat/webapps/HUBvivo115/
├── themes/wilma/templates/
│   └── individual--foaf-person.ftl (widget)
├── themes/wilma/css/
│   └── hub-cv-widget.css (estilos)
├── WEB-INF/
│   ├── web.xml (proxy config)
│   ├── classes/co/edu/urosario/hubur/
│   │   ├── CVProxyServlet.java
│   │   └── CVProxyServlet.class (compilado)
```

---

## Solr (índice)

Backend espera que Solr devuelva documentos con campos:

```
uri (clave única)
name, lastName, email, phone
educationDegree, educationInstitution, educationYear
workPositionTitle, workInstitution, workStartDate, workEndDate
publicationTitle, publicationYear, publicationDOI, publicationJournal
grantTitle, grantAgency, grantAmount, grantYear
```

**Prueba de conectividad:**

```bash
curl -s "http://localhost:8983/solr/vivocore/select?q=*:*&rows=1&wt=json" | jq '.response.numFound'
# Esperado: número > 0
```

---

## Control de acceso

El backend **no usa clave de API**. Lo que lo protege es la red:

- Escucha solo en la interfaz de loopback (`BIND_HOST`, `127.0.0.1` por defecto)
- Únicamente los procesos del propio servidor pueden alcanzarlo
- El navegador entra por el proxy de Tomcat (`/api/cv/*`)

> ⚠️ Cambiar `BIND_HOST` a `0.0.0.0` expone el servicio a toda la red **sin
> autenticación**. Antes de hacerlo habría que reintroducir un control de acceso.

Lo que sí conviene cuidar:

- ❌ No commitear el `.env` (está en `.gitignore`)
- ❌ No exponer el puerto 3001 en el firewall
- ✅ Mantener el rate-limit: protege a LibreOffice de generaciones simultáneas

## Logs

### Backend

**Archivo:** `/home/admincrai/cv-generator/backend.log`

```bash
# Ver últimas 50 líneas
tail -50 /home/admincrai/cv-generator/backend.log

# Seguir en tiempo real
tail -f /home/admincrai/cv-generator/backend.log
```

**Nivel de detalle:** información de requests + errores, sin datos sensibles

### Tomcat

**Archivo:** `/opt/tomcat/logs/catalina.out`

```bash
tail -50 /opt/tomcat/logs/catalina.out | grep -i cv
```

---

## Escalabilidad

### Caché en memoria (backend)

El backend cachea en RAM los datos extraídos de cada investigador durante
5 minutos (`CV_CACHE_TTL`), con un tope de 200 entradas (`CV_CACHE_MAX`).
El número de entradas activas se consulta en `/health`:

```bash
curl -s http://localhost:3001/health | jq '.cache_size'
```

La caché se vacía al reiniciar el backend.

### Rate-limiting

Backend limita a 5 requests/min por IP:

```bash
# Test de rate-limit
for i in {1..10}; do
  curl -s "http://localhost:3001/api/cv/generate?uri=test&format=harvard-pdf" \
done
# Esperado: primeros 5 con 200, después 429 Too Many Requests
```
