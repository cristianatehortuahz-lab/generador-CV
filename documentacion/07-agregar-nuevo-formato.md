# Agregar nuevo formato

Guía paso a paso para extender el sistema con un nuevo formato de CV (p. ej., ATS-friendly, LinkedIn, XML).

## Arquitectura modular

Cada formato es una **clase independiente** que hereda de `CVFormat`:

```
backend/
├── cv_generator.py (extrae datos)
├── harvard_cv.py (class HarvardCVGenerator)
├── pdf_filler.py (class EuropassCVGenerator)
└── (tu_formato)_cv.py (class TuFormatoGenerator) ← agregar aquí
```

---

## Paso 1: Crear clase de formato

**Archivo:** `backend/linkedin_cv.py` (ejemplo)

```python
from abc import ABC, abstractmethod

class CVFormatGenerator(ABC):
    """Interfaz base para generadores de CV"""
    
    @abstractmethod
    def generate(self, cv_data: dict) -> bytes:
        """
        Toma dict de datos normalizados, devuelve bytes PDF/DOCX/JSON.
        
        Args:
            cv_data: {
                "person": {...},
                "education": [...],
                "experience": [...],
                "publications": [...],
                ...
            }
        
        Returns:
            bytes: documento en el formato (PDF, DOCX, etc.)
        """
        pass


class LinkedInCVGenerator(CVFormatGenerator):
    def __init__(self):
        self.name = "linkedin-pdf"
        self.description = "CV formato LinkedIn (optimizado para ATS)"
    
    def generate(self, cv_data: dict) -> bytes:
        """Genera PDF estilo LinkedIn"""
        # 1. Validar datos
        if not cv_data.get("person", {}).get("name"):
            raise ValueError("Falta nombre del investigador")
        
        # 2. Construir PDF
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from io import BytesIO
        
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        
        # Encabezado
        name = cv_data["person"]["name"]
        email = cv_data["person"]["email"]
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, 750, name)
        c.setFont("Helvetica", 10)
        c.drawString(50, 735, email)
        
        # Secciones
        y = 715
        for section, items in [
            ("EDUCACIÓN", cv_data.get("education", [])),
            ("EXPERIENCIA", cv_data.get("experience", [])),
            ("PUBLICACIONES", cv_data.get("publications", []))
        ]:
            y -= 20
            c.setFont("Helvetica-Bold", 11)
            c.drawString(50, y, section)
            
            for item in items:
                y -= 15
                c.setFont("Helvetica", 9)
                title = item.get("title") or item.get("degree") or item.get("position")
                c.drawString(60, y, f"• {title}")
        
        c.save()
        buffer.seek(0)
        return buffer.getvalue()
```

---

## Paso 2: Registrar formato en cv_api.py

**Archivo:** `backend/cv_api.py`

```python
# En la sección de imports
from linkedin_cv import LinkedInCVGenerator
from harvard_cv import HarvardCVGenerator
from pdf_filler import EuropassCVGenerator

# En CVHandler.do_GET()
GENERATORS = {
    "harvard-pdf": HarvardCVGenerator(),
    "europass-pdf": EuropassCVGenerator(),
    "linkedin-pdf": LinkedInCVGenerator(),  # ← AGREGAR
}

def do_GET(self):
    format = self.querystring.get("format", ["harvard-pdf"])[0]
    
    if format not in GENERATORS:
        self.send_error(400, f"Formato no soportado: {format}")
        return
    
    generator = GENERATORS[format]
    cv_bytes = generator.generate(cv_data)
    # ...
```

---

## Paso 3: Actualizar validación de proxy

**Archivo:** `webapp/CVProxyServlet.java`

```java
private static final List<String> ALLOWED_FORMATS =
        Arrays.asList(
            "harvard-pdf",
            "europass-pdf",
            "linkedin-pdf"  // ← AGREGAR
        );
```

Recompilar:

```bash
cd /opt/tomcat/webapps/HUBvivo115/WEB-INF/classes
javac -cp "/opt/tomcat/lib/servlet-api.jar" co/edu/urosario/hubur/CVProxyServlet.java
```

---

## Paso 4: Actualizar widget (FTL)

**Archivo:** `frontend/individual--foaf-person.ftl`

```html
<!-- En la sección de modal de selección de formato -->
<button onclick="downloadCV('linkedin-pdf')">LinkedIn (PDF)</button>
```

---

## Paso 5: Agregar validación

**Archivo:** `verificacion/verify_fidelity.py`

```python
def verify_linkedin(pdf_path: str) -> dict:
    """Valida PDF estilo LinkedIn"""
    checks = [
        ("encabezado", "nombre en negrita 16pt"),
        ("email", "presente bajo nombre"),
        ("secciones", "EDUCACIÓN, EXPERIENCIA, PUBLICACIONES"),
        ("sin imágenes grandes", "< 100KB"),
        ("tamaño", "1-2 páginas"),
    ]
    
    results = []
    for check_name, check_desc in checks:
        # Implementar validación
        results.append({
            "name": check_name,
            "status": "PASS" or "FAIL",
            "value": check_desc
        })
    
    return results

# En main()
VALIDATORS = {
    "harvard": verify_harvard,
    "europass": verify_europass,
    "linkedin": verify_linkedin,  # ← AGREGAR
}
```

---

## Paso 6: Documentación

Agregar a `documentacion/04-formatos.md`:

```markdown
### LinkedIn CV (ATS-friendly)

- **Formato:** PDF con texto plano (sin imágenes)
- **Propósito:** Solicitudes laborales via sistemas ATS (Applicant Tracking Systems)
- **Validación:** `verify_fidelity.py --format linkedin`
- **Tamaño:** máx 2 páginas
- **Campos:** educación, experiencia, publicaciones (sin detalles de grants)
```

---

## Paso 7: Testing

```bash
# Crear test data
python verificacion/_demo_formato.py --format linkedin

# Validar
python verificacion/verify_fidelity.py --pdf cv_linkedin_demo.pdf --format linkedin

# Probar vía API
curl "http://localhost:3001/api/cv/generate?uri=http://localhost:8080/display/n1&format=linkedin-pdf" \
  -o /tmp/test_linkedin.pdf

file /tmp/test_linkedin.pdf
```

---

## Ejemplo completo: CVinvestigador (JSON + XML)

Formato alternativo que genera JSON/XML en lugar de PDF.

```python
# backend/cv_researcher.py
import json
from datetime import datetime

class ResearcherCVGenerator(CVFormatGenerator):
    def generate(self, cv_data: dict) -> bytes:
        """Genera CV en formato JSON-LD (Linked Data)"""
        
        output = {
            "@context": "https://schema.org",
            "@type": "Person",
            "name": f"{cv_data['person']['name']} {cv_data['person']['lastName']}",
            "email": cv_data["person"]["email"],
            "telephone": cv_data["person"].get("phone"),
            "educationCredential": [
                {
                    "@type": "EducationalOccupationalCredential",
                    "credentialCategory": edu["degree"],
                    "educationalLevel": edu["field"],
                    "validFrom": edu.get("year", "")
                }
                for edu in cv_data.get("education", [])
            ],
            "workLocation": [
                {
                    "@type": "Place",
                    "name": exp["institution"]
                }
                for exp in cv_data.get("experience", [])
            ],
            "hasOccupation": [
                {
                    "@type": "Occupation",
                    "name": exp["position"],
                    "occupationLocation": exp["institution"]
                }
                for exp in cv_data.get("experience", [])
            ]
        }
        
        # Convertir a JSON
        json_bytes = json.dumps(output, indent=2, ensure_ascii=False).encode("utf-8")
        
        # Opcional: convertir a PDF si se requiere
        # from reportlab.lib.pagesizes import letter
        # from reportlab.pdfgen import canvas
        # ...
        
        return json_bytes
```

Registrar:

```python
GENERATORS = {
    "harvard-pdf": HarvardCVGenerator(),
    "europass-pdf": EuropassCVGenerator(),
    "researcher-json": ResearcherCVGenerator(),
}
```

---

## Checklist de implementación

- [ ] Crear clase heredando de `CVFormatGenerator`
- [ ] Implementar método `generate(cv_data) -> bytes`
- [ ] Registrar en `GENERATORS` en `cv_api.py`
- [ ] Agregar a `ALLOWED_FORMATS` en `CVProxyServlet.java`
- [ ] Recompilar servlet
- [ ] Agregar botón en FTL widget
- [ ] Crear validador en `verify_fidelity.py`
- [ ] Actualizar documentación
- [ ] Testear vía API + UI
- [ ] Commit + push a GitHub

---

## Referencia: estructura de cv_data

```python
{
    "person": {
        "name": "Juan",
        "lastName": "Pérez García",
        "email": "juan@univ.edu.co",
        "phone": "+57 1 234 5678",
        "orcid": "0000-0001-2345-6789"
    },
    "education": [
        {
            "degree": "Doctorado",
            "field": "Informática",
            "institution": "MIT",
            "year": 2010,
            "country": "USA"
        }
    ],
    "experience": [
        {
            "position": "Profesor Asociado",
            "institution": "Universidad Javeriana",
            "startDate": "2015-01-01",
            "endDate": None,
            "description": "..."
        }
    ],
    "publications": [
        {
            "title": "Deep Learning for...",
            "journal": "IEEE Transactions",
            "year": 2020,
            "doi": "10.1109/...",
            "authors": ["Juan Pérez", "..."],
            "citations": 42
        }
    ],
    "grants": [
        {
            "title": "Seguridad en IoT",
            "agency": "COLCIENCIAS",
            "amount": 50000000,
            "currency": "COP",
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
