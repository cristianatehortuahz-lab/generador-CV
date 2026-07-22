# Guía de instalación — Generador de CV

Instalación paso a paso para **desarrollo local** (tu máquina) y **servidor de prácticas**.

## 🖥️ Desarrollo local (Windows/macOS/Linux)

### 1. Clonar y dependencias

```bash
git clone https://github.com/cristianatehortuahz-lab/generador-CV.git
cd generador-CV/backend
pip install -r requirements.txt
```

**Dependencias:** `python-docx`, `python-dotenv`, `requests` (ver [`backend/requirements.txt`](backend/requirements.txt)).
La conversión a PDF la hace LibreOffice en Linux y Microsoft Word en Windows; en Windows
se necesitan además `pywin32` y `docx2pdf`.

### 2. Configurar `.env`

Copia `backend/.env.example` → `backend/.env`:

```bash
VIVO_BASE_URL=http://localhost:8080
SOLR_URL=http://localhost:8983/solr/vivocore
PORT=3001
SOFFICE_PATH=/usr/bin/soffice   # ruta de LibreOffice en tu equipo
```

**Notas:**
- `SOFFICE_PATH`: ruta a LibreOffice (solo en Linux/macOS). En Windows la conversión la hace Word vía `pywin32` + `docx2pdf`
- `VIVO_BASE_URL`: si VIVO corre en tu máquina, déjalo en `http://localhost:8080`

### 3. Arrancar backend

```bash
# macOS/Linux
chmod +x backend/start_cv.sh
./backend/start_cv.sh

# Windows (CMD o PowerShell)
cd backend
python cv_api.py
```

Verifica en `http://localhost:3001/health` (debe devolver `200`).

### 4. Probar sin proxy

```bash
# Generar CV directo (omite proxy)
curl "http://localhost:3001/api/cv/generate?uri=http://localhost:8080/display/n1&format=harvard-pdf" \
  -o /tmp/test.pdf

file /tmp/test.pdf  # → PDF document
```

---

> **Sobre las direcciones:** los comandos `curl` y `bash` de esta guía se ejecutan
> **en el servidor**, por eso usan `localhost`. Los pasos de navegador usan
> `<servidor>`, que es la dirección del equipo donde corre Tomcat: en el servidor
> de prácticas, `10.194.194.96` (o `srvcbpbvivo`).

---

## 🌐 Servidor de prácticas (Linux + Tomcat)

### 1. Preparar backend

En tu máquina local, comprime para transferir:

```bash
tar czf generador-CV-backend.tgz backend/
```

En XFTP (o mediante SCP), sube a `/home/admincrai/cv-generator/`:

```
backend/*.py → /home/admincrai/cv-generator/
backend/.env (editado) → /home/admincrai/cv-generator/.env
backend/formatos/ → /home/admincrai/cv-generator/03-assets/
```

### 2. Configurar .env en el servidor

En `/home/admincrai/cv-generator/.env`:

```bash
VIVO_BASE_URL=http://localhost:8080
SOLR_URL=http://localhost:8983/solr/vivocore/select
PORT=3001
SOFFICE_PATH=/home/admincrai/lo7/opt/libreoffice7.6/program/soffice
HARVARD_TEMPLATE="/home/admincrai/cv-generator/03-assets/2025-template_bullet (3).docx"
EUROPASS_TEMPLATE=/home/admincrai/cv-generator/03-assets/europass_template.pdf
EUROPASS_LOGO=/home/admincrai/cv-generator/03-assets/europass_logo.png
```

### 3. Arrancar backend (XShell)

```bash
cd /home/admincrai/cv-generator/
chmod +x start_cv.sh
./start_cv.sh
```

Verifica:

```bash
ss -tlnp | grep 3001  # Debe mostrar el puerto activo
curl -s http://localhost:3001/health  # status: ok / degraded + estado de cada componente
```

### 4. Subir frontend a Tomcat

Via **XFTP**, sube a `/opt/tomcat/webapps/HUBvivo115/`:

```
frontend/individual--foaf-person.ftl → themes/wilma/templates/
frontend/hub-cv-widget.css → themes/wilma/css/
webapp/web.xml → WEB-INF/
webapp/CVProxyServlet.java → WEB-INF/classes/co/edu/urosario/hubur/
```

### 5. Recompilar servlet (si lo modificaste)

En XShell:

```bash
cd /opt/tomcat/webapps/HUBvivo115/WEB-INF/classes
javac -cp "/opt/tomcat/lib/servlet-api.jar" co/edu/urosario/hubur/CVProxyServlet.java
```

### 6. Reiniciar Tomcat

```bash
sudo /etc/rc.d/init.d/tomcat stop && sleep 5 && sudo /etc/rc.d/init.d/tomcat start
```

Espera 30s a que Tomcat cargue las nuevas plantillas FTL.

---

## ✅ Verificación

### Backend

```bash
curl -s http://localhost:3001/health
```

### Proxy directo (sin widget)

```bash
curl -s "http://localhost:8080/api/cv/generate?uri=http://localhost:8080/display/n1&format=harvard-pdf" \
  -o /tmp/test.pdf && file /tmp/test.pdf
```

Debe devolver `application/pdf` y un archivo válido.

### Widget en navegador


1. Abre VIVO en el navegador: `http://<servidor>:8080/`
2. Navega a un perfil de investigador (p. ej. `/display/n1`)
3. Busca botón rojo **"Descargar Hoja de Vida"** bajo la foto
4. Selecciona **Harvard** → debe descargar PDF
5. Selecciona **Europass** → debe descargar PDF

---

## 🐛 Problemas comunes

**"Error, intente de nuevo" en el widget**
- Backend no está corriendo: `./start_cv.sh` en `/home/admincrai/cv-generator/`
- Puerto 3001 no abierto: `lsof -i :3001`

**PDF vacío o con datos incorrectos**
- URI del investigador mal formada: verifica que VIVO devuelva datos vía Solr
- Solr caído: `curl "http://localhost:8983/solr/vivocore/select?q=*:*&rows=0"`

**Letras deformadas en PDF**
- Fuentes faltantes: `sudo apt install fonts-dejavu` (Linux)
- LibreOffice mal configurado: verifica `SOFFICE_PATH`

Ver [`documentacion/05-mantenimiento.md`](documentacion/05-mantenimiento.md) para más.

---

## 📝 Checklist de despliegue

- [ ] Backend python arrancado en puerto 3001
- [ ] `.env` con las rutas correctas en backend
- [ ] Frontend (FTL + CSS) subido a Tomcat
- [ ] Servlet recompilado (si tocaste el .java)
- [ ] Tomcat reiniciado
- [ ] Verificación en verde (backend, proxy y widget)
