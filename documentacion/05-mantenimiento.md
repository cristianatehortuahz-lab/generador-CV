# Mantenimiento — Troubleshooting y operación

## 🔍 Diagnosis rápida

### Backend no arranca

```bash
# 1. ¿Está el puerto 3001 bloqueado?
lsof -i :3001
# Si hay proceso, kill -9 <PID>

# 3. ¿Python 3.8+?
python3 --version

# 4. ¿Dependencias instaladas?
python3 -c "import dotenv; import requests; print('OK')"

# 5. ¿Archivo main existe?
ls -la /home/admincrai/cv-generator/cv_api.py

# 6. Ver error detallado
cd /home/admincrai/cv-generator && python3 cv_api.py 2>&1 | head -50
```

### "Error, intente de nuevo" en widget

```bash
# 1. ¿Backend está arriba?
curl -s http://localhost:3001/health | jq .

# 2. ¿Proxy redirige correctamente?
curl -v "http://localhost:8080/api/cv/generate?uri=test&format=harvard-pdf" 2>&1 | grep -E "HTTP|Proxy"

# 4. Ver logs
tail -30 /home/admincrai/cv-generator/backend.log
tail -30 /opt/tomcat/logs/catalina.out | grep -i cv
```

### HTTP 502 (Bad Gateway)

```bash
# Causa: backend no alcanzable en localhost:3001

# 1. ¿Backend arriba?
ss -tlnp | grep 3001

# 2. ¿Firewall bloqueando?
sudo firewall-cmd --list-all | grep 3001

# 3. Reiniciar backend
pkill -f cv_api.py
cd /home/admincrai/cv-generator && ./start_cv.sh
sleep 3 && curl http://localhost:3001/health
```

### PDF vacío o con datos incompletos

```bash
# Causa: Solr sin datos para el investigador

# 1. Verificar que el investigador existe en VIVO
curl -s "http://localhost:8983/solr/vivocore/select?q=uri:*n123&wt=json" | jq '.response.docs[0]'

# 2. Probar generación con investigador conocido
curl -s "http://localhost:3001/api/cv/generate?uri=http://localhost:8080/display/n123&format=harvard-pdf" \
  -o /tmp/test.pdf

# 3. Verificar que PDF tiene contenido
file /tmp/test.pdf
pdfinfo /tmp/test.pdf  # Debe mostrar páginas > 0
```

### Letras deformadas en PDF

```bash
# Causa: fuentes faltantes en servidor

# 1. Instalar fonts
sudo yum install fonts-dejavu  # CentOS/RHEL

# 2. Ver fuentes disponibles
fc-list | grep -i arial

# 3. Convertir DOCX manualmente con LibreOffice
/home/admincrai/lo7/opt/libreoffice7.6/program/soffice --headless --convert-to pdf /tmp/test.docx
# Ver resultado: /tmp/test.pdf

# 4. Si LibreOffice falla, ver errores
/home/admincrai/lo7/opt/libreoffice7.6/program/soffice --headless --convert-to pdf /tmp/test.docx 2>&1
```

---

## 📊 Monitoreo

### Health check (automated)

Agregar cron job para verificar cada 5 minutos:

```bash
# /etc/cron.d/cv-generator-health
*/5 * * * * root curl -s http://localhost:3001/health || echo "CV BACKEND DOWN" | mail -s "ALERT" admin@example.com
```

### Logs

**Backend:** `/home/admincrai/cv-generator/backend.log`

```bash
# Monitorear en tiempo real
tail -f /home/admincrai/cv-generator/backend.log

# Contar errores últimas 24h
grep ERROR /home/admincrai/cv-generator/backend.log | wc -l

# Buscar requests lentos (> 10s)
grep "duration:" /home/admincrai/cv-generator/backend.log | awk '{print $NF}' | sort -rn | head -10
```

**Tomcat:** `/opt/tomcat/logs/catalina.out`

```bash
# Errores del servlet
tail -100 /opt/tomcat/logs/catalina.out | grep CVProxyServlet
```

---

## 🔧 Operaciones comunes

### Cambiar plantilla Harvard

```bash
# 1. Backup de plantilla actual
cp /home/admincrai/cv-generator/03-assets/2025-template_bullet (3).docx \
   /home/admincrai/cv-generator/03-assets/2025-template_bullet.BACKUP.docx

# 2. Subir nueva plantilla via XFTP
# Destino: /home/admincrai/cv-generator/03-assets/ (conserva el nombre exacto, con el ' (3)')

# 3. Verificar permisos
chmod 644 "/home/admincrai/cv-generator/03-assets/2025-template_bullet (3).docx"

# 4. Probar con muestras
cd /home/admincrai/cv-generator/verificacion
python _demo_formato.py --format harvard
```

### Limpiar caché

El backend cachea en RAM los datos de cada investigador durante 5 minutos.
No hay endpoint para vaciarla: expira sola o se limpia al reiniciar el backend.

```bash
# Ver cuántas entradas hay en caché
curl -s http://localhost:3001/health | jq '.cache_size'

# Vaciarla reiniciando el backend
pkill -f cv_api.py
cd /home/admincrai/cv-generator && ./start_cv.sh
```

### Backups

```bash
# Backend
tar czf ~/backups/cv-generator-$(date +%F).tgz \
  /home/admincrai/cv-generator/*.py \
  /home/admincrai/cv-generator/03-assets/

# Tomcat
tar czf ~/backups/tomcat-cv-$(date +%F).tgz \
  /opt/tomcat/webapps/HUBvivo115/themes/wilma/templates/individual--foaf-person.ftl \
  /opt/tomcat/webapps/HUBvivo115/themes/wilma/css/hub-cv-widget.css \
  /opt/tomcat/webapps/HUBvivo115/WEB-INF/web.xml \
  /opt/tomcat/webapps/HUBvivo115/WEB-INF/classes/co/edu/urosario/hubur/
```

---

## ⚠️ Limitaciones conocidas

| Limitación | Impacto | Workaround |
|------------|--------|-----------|
| LibreOffice timeout 90s | CVs complejas pueden fallar | Aumentar timeout en CVProxyServlet.java |
| Solr máx 10k docs | Si > 10k investigadores, falla query | Agregar pagination a cv_generator.py |
| Caché en RAM | Pérdida con restart | Migrar a Redis (opcional) |
| Fuentes Linux | Letras deformadas | Instalar fonts-dejavu |
| PDF > 50MB | Descarga lenta | Comprimir imágenes en plantilla DOCX |

---

## 🚀 Escalabilidad futura

### Arquitectura actual
- 1 proceso Python (localhost:3001)
- Caché en RAM
- Solicitud síncrona (blocking)

### Para 1000+ CVs/día
- Load balancer (nginx) frente a N workers Python
- Caché distribuido (Redis)
- Queue (Celery) + workers async
- Monitoreo (Prometheus + Grafana)
- CDN para assets (CSS, imágenes)

### Para 10k+ investigadores
- Sharding de Solr (distribuir índice)
- Caché multi-nivel (Redis + local)
- Pre-generación de CVs (batch nightly)
