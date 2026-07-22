# Guía de despliegue — Servidor de prácticas

Instalación completa en servidor Linux con Tomcat (srvcbpbvivo).

## 📋 Prerequisitos

- **SO:** Linux (CentOS/RHEL compatible)
- **Tomcat:** 9+, corriendo en puerto 8080
- **Python:** 3.8+
- **LibreOffice:** 6.4+ (para DOCX→PDF)
- **Solr:** 8.5+, índice `hub` disponible
- **VIVO:** corriendo en `http://localhost:8080`

---

> **Sobre las direcciones:** los comandos `curl` y `bash` de esta guía se ejecutan
> **en el servidor**, por eso usan `localhost`. Los pasos de navegador usan
> `<servidor>`, que es la dirección del equipo donde corre Tomcat: en el servidor
> de prácticas, `10.194.194.96` (o `srvcbpbvivo`).

---

## 🚀 Pasos de despliegue

### Fase 1: Backend Python (en `/home/admincrai/cv-generator/`)

#### 1.1 Descargar archivos

Via **XFTP** (local → servidor):

| Local | Remoto |
|-------|--------|
| `generador-CV/backend/*.py` | `/home/admincrai/cv-generator/` |
| `generador-CV/backend/formatos/` | `/home/admincrai/cv-generator/03-assets/` |
| `generador-CV/backend/.env.example` | `/home/admincrai/cv-generator/.env.example` |

#### 1.2 Configurar `.env`

En XShell:

```bash
cd /home/admincrai/cv-generator
cp .env.example .env
# Editar .env con valores reales:
```

Contenido de `.env`:

```bash
PORT=3001
VIVO_BASE_URL=http://localhost:8080
SOLR_URL=http://localhost:8983/solr/vivocore/select
SOFFICE_PATH=/home/admincrai/lo7/opt/libreoffice7.6/program/soffice
HARVARD_TEMPLATE="/home/admincrai/cv-generator/03-assets/2025-template_bullet (3).docx"
EUROPASS_TEMPLATE=/home/admincrai/cv-generator/03-assets/europass_template.pdf
EUROPASS_LOGO=/home/admincrai/cv-generator/03-assets/europass_logo.png
```

#### 1.3 Instalar dependencias Python

```bash
cd /home/admincrai/cv-generator
pip3 install -r requirements.txt
# Típicas: python-dotenv, requests, pillow, python-docx, python-pptx
```

#### 1.4 Probar conexiones

```bash
# ¿Solr disponible?
curl -s http://localhost:8983/solr/vivocore/select?q=*:*&rows=1 | grep -q '"numFound"' && echo "✅ Solr OK"

# ¿LibreOffice instalado?
/home/admincrai/lo7/opt/libreoffice7.6/program/soffice --version

# ¿Python listo?
python3 -c "import dotenv; print('✅ dependencias OK')"
```

#### 1.5 Arrancar backend

```bash
cd /home/admincrai/cv-generator
chmod +x start_cv.sh
./start_cv.sh
```

Verificar:

```bash
sleep 3 && ss -tlnp | grep 3001  # Debe mostrar puerto activo
curl -s http://localhost:3001/health  # Debe devolver JSON OK
tail -5 backend.log  # Ver últimas líneas del log
```

**Si falla:**

```bash
# Matar instancia anterior
lsof -i :3001 | grep -v COMMAND | awk '{print $2}' | xargs kill -9

# Ver errores detallados
python3 cv_api.py  # Ctrl+C para salir
```

---

### Fase 2: Frontend + Proxy (Tomcat, en `/opt/tomcat/webapps/HUBvivo115/`)

#### 2.1 Backup previo

```bash
cd /opt/tomcat/webapps/HUBvivo115
tar czf ~/backup_cv_$(date +%F_%T).tgz \
  themes/wilma/templates/individual--foaf-person.ftl \
  themes/wilma/css/hub-cv-widget.css \
  WEB-INF/web.xml \
  WEB-INF/classes/co/edu/urosario/hubur/CVProxyServlet.*
```

#### 2.2 Subir archivos (XFTP)

| Local | Remoto |
|-------|--------|
| `generador-CV/frontend/individual--foaf-person.ftl` | `themes/wilma/templates/` |
| `generador-CV/frontend/hub-cv-widget.css` | `themes/wilma/css/` |
| `generador-CV/webapp/web.xml` | `WEB-INF/` |
| `generador-CV/webapp/CVProxyServlet.java` | `WEB-INF/classes/co/edu/urosario/hubur/` |

#### 2.3 Compilar servlet (solo si cambiaste el .java)

```bash
cd /opt/tomcat/webapps/HUBvivo115/WEB-INF/classes
javac -cp "/opt/tomcat/lib/servlet-api.jar" co/edu/urosario/hubur/CVProxyServlet.java
# Debe generar CVProxyServlet.class sin errores
```

#### 2.4 Reiniciar Tomcat

Edita `/opt/tomcat/bin/setenv.sh`:

```bash
#!/bin/bash
export CATALINA_OPTS="-Xmx512m -XX:MaxMetaspaceSize=128m"
```

**Importantísimo:** la clave debe ser **exactamente igual** a la del backend `.env`.

#### 2.5 Reiniciar Tomcat

```bash
sudo /etc/rc.d/init.d/tomcat stop && sleep 5 && sudo /etc/rc.d/init.d/tomcat start
```

Espera 30-60s a que cargue completamente.

---

## ✅ Verificación post-despliegue

### Backend

```bash
# Salud
curl -s http://localhost:3001/health
# Esperado: {"status":"ok"} + HTTP 200

# Test directo al backend
curl -s "http://localhost:3001/api/cv/generate?uri=http://localhost:8080/display/n1&format=harvard-pdf" \
  -o /tmp/test.pdf

file /tmp/test.pdf  # Esperado: PDF document
```

### Proxy directo

```bash
curl -s "http://localhost:8080/api/cv/generate?uri=http://localhost:8080/display/n1&format=harvard-pdf" \
  -o /tmp/test.pdf

file /tmp/test.pdf  # Esperado: PDF document
```

### Widget en navegador


1. Abre `http://<servidor>:8080/` en el navegador
2. Navega a perfil de investigador (p. ej., `/display/n1`)
3. Busca botón rojo **"Descargar Hoja de Vida"** bajo la foto
4. Selecciona **Harvard** → descarga `Nombre_Apellido_harvard.pdf`
5. Selecciona **Europass** → descarga `Nombre_Apellido_europass.pdf`
6. Abre PDFs, verifica formato correcto

---

## 🐛 Troubleshooting

| Síntoma | Causa | Solución |
|---------|-------|----------|
| Port 3001 refused | Backend no arranca | `./start_cv.sh` en `/home/admincrai/cv-generator/` |
| "Error, intente de nuevo" (widget) | Backend no arranca o proxy no alcanza | `curl http://localhost:3001/health` |
| HTTP 502 (proxy) | Backend caído | `lsof -i :3001` y `./start_cv.sh` |
| PDF vacío | Solr sin datos para investigador | Verificar URI, `curl http://localhost:8983/solr/vivocore/select?q=uri:"..."` |
| Letras deformadas | Fuentes faltantes | `sudo apt install fonts-dejavu` |
| Servlet error (logs) | `.java` no compila | Verificar sintaxis y recompilar |

---

## 📝 Checklist final

- [ ] Backup hecho
- [ ] Backend Python subido y arrancado
- [ ] `.env` con las rutas del servidor
- [ ] Frontend (FTL + CSS) subido
- [ ] Servlet compilado (si tocaste .java)
- [ ] Tomcat reiniciado y cargado completamente
- [ ] Verificación §3 en verde
- [ ] Widget en navegador descarga PDF sin errores
