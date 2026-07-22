# Validación técnica de formato

Herramienta `verify_fidelity.py`: valida automáticamente que PDFs generados cumplen estándares.

## Qué valida

### Harvard CV

```python
checks = [
    ("márgenes", "2.54 cm (1 pulgada) en todos lados"),
    ("alineación", "justificada excepto títulos"),
    ("fuentes", "Arial 11pt cuerpo, 12pt títulos"),
    ("espaciado", "1.5 líneas entre párrafos"),
    ("sin imágenes grandes", "< 50KB total"),
    ("saltos de página", "máx 4 páginas"),
    ("encabezados", "nombre en negrita 14pt"),
    ("listas", "viñetas indentadas 0.5 cm")
]
```

### Europass PDF

```python
checks = [
    ("formularios", "todos los campos rellenados"),
    ("codificación", "UTF-8 (soporta acentos)"),
    ("formato", "PDF válido sin corrupción"),
    ("logo", "presente en encabezado, < 1MB"),
    ("campos obligatorios", "nombre, apellido, email"),
    ("estructura", "2 páginas máximo"),
    ("tamaño archivo", "< 5MB"),
    ("metadata", "autor/título configurados")
]
```

---

## Uso

### Instalación de dependencias

```bash
pip install pymupdf python-docx
```

### Ejecutar validación

```bash
cd generador-CV/verificacion

# Validar PDF Harvard
python verify_fidelity.py --pdf "/tmp/cv_harvard.pdf" --format harvard

# Validar PDF Europass
python verify_fidelity.py --pdf "/tmp/cv_europass.pdf" --format europass

# Genera reporte HTML
python verify_fidelity.py --pdf "/tmp/cv_harvard.pdf" --format harvard --output report.html
```

### Salida esperada

```
╔════════════════════════════════════╗
║  Harvard CV Fidelity Report        ║
╠════════════════════════════════════╣
║ ✅ Márgenes correctos              ║
║ ✅ Alineación justificada          ║
║ ✅ Fuentes compatibles             ║
║ ✅ Espaciado 1.5 líneas            ║
║ ✅ Tamaño de imágenes              ║
║ ✅ Saltos de página                ║
║ ✅ Encabezados formateados         ║
║ ✅ Listas indentadas               ║
╠════════════════════════════════════╣
║ RESULTADO: 8/8 PASSED              ║
╚════════════════════════════════════╝
```

---

## Cómo funciona internamente

### 1. Extracción de propiedades PDF

```python
import fitz  # PyMuPDF

doc = fitz.open("cv.pdf")
page = doc[0]

# Márgenes
margin_top = page.rect.y0
margin_left = page.rect.x0

# Texto
text_blocks = page.get_text("dict")["blocks"]

# Imágenes
images = [img for img in page.get_images()]
```

### 2. Cálculo de métricas

```python
# Alineación
for block in text_blocks:
    x0, y0, x1, y1 = block['bbox']
    # Si x1 coincide con margen derecho ≈ justificado
    is_justified = abs(x1 - page.width) < 10

# Fuentes
for span in block['spans']:
    font_name = span['font']
    font_size = span['size']
    # Validar contra reglas (Arial 11pt, etc.)

# Espaciado
line_heights = []
for i, block in enumerate(text_blocks):
    y = block['bbox'][1]
    if i > 0:
        line_heights.append(y - prev_y)
    prev_y = y
# Promedio debe ser ≈ 1.5 * font_size
```

### 3. Generación de reporte

```python
report = {
    "format": "harvard",
    "checks": [
        {"name": "márgenes", "status": "PASS", "value": "2.54cm"},
        {"name": "alineación", "status": "FAIL", "value": "left-aligned"}
    ],
    "score": 7/8,
    "timestamp": "2026-07-21 14:30:00"
}

# Exportar JSON / HTML
```

---

## Normas de referencia

### Harvard CV (sin estándar oficial)

Basado en:
- MLA (Modern Language Association)
- APA (American Psychological Association)
- Universidad de Harvard — CV guidelines

**Requerimientos comunes:**
- Márgenes: 1" (2.54cm)
- Fuente: Times New Roman o Arial, 11-12pt
- Espaciado: 1 o 1.5 líneas
- Orden: contacto → educación → experiencia → pubs → skills

### Europass CV (estándar EU)

Oficial: https://europass.cedefop.europa.eu/

**Requerimientos:**
- Formulario PDF estandarizado (formato fijo)
- Campos: nombre, email, educación, experiencia, idiomas, skills
- Máx 2-3 páginas
- Logo de Europass obligatorio
- Idiomas según Marco Común Europeo (A1-C2)

---

## Testing

### Test suite

```bash
# Generar PDFs de prueba
cd generador-CV/verificacion

# Opción 1: Desde URI real en VIVO
python _demo_formato.py --uri "http://localhost:8080/display/n1"

# Opción 2: Datos simulados
python _demo_formato.py --mock

# Luego validar
python verify_fidelity.py --pdf cv_harvard_demo.pdf --format harvard
python verify_fidelity.py --pdf cv_europass_demo.pdf --format europass
```

### CI/CD integration

Agregar a pipeline (GitHub Actions / GitLab CI):

```yaml
- name: Validate PDF fidelity
  run: |
    cd verificacion
    python verify_fidelity.py --pdf /tmp/test_harvard.pdf --format harvard
    python verify_fidelity.py --pdf /tmp/test_europass.pdf --format europass
```

---

## Troubleshooting validación

| Error | Causa | Solución |
|-------|-------|----------|
| "Fuentes faltantes" | Arial no instalado en server | `apt install fonts-dejavu-sans` |
| "Márgenes incorrectos" | LibreOffice usa márgenes default (2cm) | Ajustar en plantilla DOCX |
| "Texto no justificado" | Configuración de párrafo en DOCX | Verificar formato en Word |
| "PDF corrupto" | Conversión DOCX → PDF falló | Probar conversión manual: `soffice --convert-to pdf` |
| "Score bajo" | Validación muy estricta | Ajustar thresholds en `verify_fidelity.py` |
