# Formatos — Harvard y Europass

Especificación técnica de cada formato, mapeeo de campos, validación.

## 1. Harvard CV

### Descripción general

- **Plantilla:** DOCX Microsoft Word (`2025-template_bullet (3).docx`)
- **Conversión:** DOCX → PDF (Word COM en Windows, LibreOffice headless en Linux)
- **Idioma:** Español (campo normalizable)
- **Longitud:** Típicamente 2-4 páginas
- **Fuentes:** Arial, Calibri (must be on server)

### Estructura y campos

| Sección | Campo Solr | Notas |
|---------|------------|-------|
| **Nombre y contacto** | `name`, `lastName`, `email`, `phone` | Nombre completo + email/tel |
| **Perfil/Resumen** | — | Generado automáticamente (opcional) |
| **Educación** | `educationDegree`, `educationInstitution`, `educationYear` | Grado, Universidad, Año graduación |
| **Experiencia** | `workPositionTitle`, `workInstitution`, `workStartDate`, `workEndDate` | Cargo, lugar, fechas |
| **Publicaciones** | `publicationTitle`, `publicationJournal`, `publicationYear`, `publicationDOI` | Artículos, capítulos, etc. |
| **Grants** | `grantTitle`, `grantAgency`, `grantAmount`, `grantYear` | Financiación, premios |
| **Habilidades** | `skills` | Idiomas, competencias técnicas |

### Generación

```python
# En harvard_cv.py
from docx import Document

doc = Document("2025-template_bullet (3).docx")
# Reemplaza placeholders {{nombre}}, {{apellido}}, etc.
# Agrega secciones dinámicas (educación, pubs)
doc.save("/tmp/cv.docx")

# Convierte DOCX → PDF
# Windows: Word COM
# Linux: soffice --headless --convert-to pdf
```

### Validación de fidelidad

`verify_fidelity.py` chequea:
- ✅ **Márgenes:** 2.54 cm (1") arriba/abajo/izquierda/derecha
- ✅ **Alineación:** texto justificado (excepto encabezados)
- ✅ **Fuentes:** Arial 11pt cuerpo, 12pt títulos
- ✅ **Espaciado:** 1.5 líneas entre párrafos
- ✅ **Sin imágenes grandes:** < 50KB total

---

## 2. Europass

### Descripción general

- **Maqueta:** se construye con `python-docx` siguiendo la estructura Europass
- **Referencia:** `europass_template.pdf` sirve de guía visual y de comprobación
  de disponibilidad (si falta, el endpoint responde 503)
- **Idioma:** Multiidioma oficial de Europass
- **Longitud:** Típicamente 1-2 páginas
- **Estándar:** Unión Europea (formato CV estandarizado)

### Estructura y campos

| Sección | Campo Solr | Notas |
|---------|------------|-------|
| **Información personal** | `name`, `lastName`, `email`, `phone`, `address` | Datos básicos |
| **Foto** | — | Opcional, inyectada como imagen |
| **Educación** | `educationDegree`, `educationInstitution`, `educationYear`, `educationField` | Grado, institución, año, área |
| **Experiencia** | `workPositionTitle`, `workInstitution`, `workStartDate`, `workEndDate` | Cargo, lugar, duración |
| **Idiomas** | `languages` | Nivel según Marco Europeo (A1-C2) |
| **Habilidades** | `skills`, `computerSkills` | Competencias y TIC |
| **Publicaciones** | `publicationTitle`, `publicationYear`, `publicationDOI` | Reducido respecto a Harvard |
| **Logo** | `europass_logo.png` | Cabecera/pie de página |

### Generación

```python
# En pdf_filler.py
from docx import Document

doc = Document()
# Se arma la estructura Europass: datos personales, educación,
# experiencia, idiomas y competencias, con el logo en el encabezado.
# El documento resultante se convierte a PDF por la misma vía que Harvard.
```

### Validación de fidelidad

`verify_fidelity.py` chequea:
- ✅ **Formularios rellenados:** todos los campos tienen valor
- ✅ **Formato:** PDF válido (sin corrupción)
- ✅ **Logo:** presente y en tamaño correcto (< 1MB)
- ✅ **Codificación:** UTF-8 (soporta acentos)

---

## 3. Comparativa

| Aspecto | Harvard | Europass |
|---------|---------|----------|
| **Formato** | DOCX → PDF | PDF (formularios) |
| **Flexibilidad** | Alta (editab DOCX) | Media (formularios cerrados) |
| **Longitud** | 2-4 págs | 1-2 págs (estándar) |
| **Internacionalización** | Depende plantilla | Estándar EU |
| **Compatibilidad** | Word/PDF readers | PDF readers |
| **Costo de mantenimiento** | Plantilla DOCX cada año | Plantilla PDF cada 2 años |
| **Uso típico** | Solicitudes académicas/investigación | Solicitudes laborales EU |

---

## 4. Campos normalizados

Backend normaliza datos de Solr en estructura común:

```python
{
    "person": {
        "name": "Juan",
        "lastName": "Pérez",
        "email": "juan@universidadrosario.edu.co",
        "phone": "+57 1 234 5678"
    },
    "education": [
        {
            "degree": "Doctorado",
            "field": "Informática",
            "institution": "Universidad Nacional",
            "year": 2015
        }
    ],
    "experience": [
        {
            "position": "Profesor Asociado",
            "institution": "Universidad Javeriana",
            "startDate": "2016-01-15",
            "endDate": None,
            "description": "Investigación en seguridad informática"
        }
    ],
    "publications": [
        {
            "title": "Deep Learning for Security",
            "journal": "IEEE Transactions",
            "year": 2020,
            "doi": "10.1109/...",
            "url": "https://doi.org/10.1109/..."
        }
    ],
    "grants": [
        {
            "title": "Seguridad en IoT",
            "agency": "COLCIENCIAS",
            "amount": "50,000,000 COP",
            "year": 2019
        }
    ],
    "languages": [
        {"name": "Español", "level": "C2"},
        {"name": "Inglés", "level": "B2"}
    ],
    "skills": ["Python", "Security", "Data Science"]
}
```

---

## 5. Enriquecimiento de datos

### Consulta a VIVO

Además de Solr, el backend consulta la ficha del investigador en VIVO
(`VIVO_BASE_URL`) para completar datos que no están indexados, como educación
y cargos. Si VIVO no responde, la generación continúa con los datos de Solr y
se registra un aviso en el log.

Los DOI de las publicaciones se toman del enlace `doi.org` cuando está presente.

---

## 6. Testing

### Generar muestras

```bash
cd generador-CV/verificacion

# Crea 2 PDFs de prueba (Harvard + Europass) para investigador n1
python _demo_formato.py --uri "http://localhost:8080/display/n1"

# Abre PDFs y verifica manualmente
# A continuación, valida con fidelity
```

### Validar fidelidad

```bash
python verify_fidelity.py --pdf "/tmp/cv_harvard.pdf" --format harvard
# Esperado: 8/8 checks passed

python verify_fidelity.py --pdf "/tmp/cv_europass.pdf" --format europass
# Esperado: 8/8 checks passed
```
