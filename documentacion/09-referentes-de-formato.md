# Referentes de formato

Ejemplares reales y diligenciados de cada formato, para contrastar contra lo que
genera el sistema. Son documentos publicados por las instituciones que definen
cada estándar, no reconstrucciones.

---

## Harvard

**Fuente:** Harvard Griffin GSAS — *CVs and Cover Letters* (Mignone Center for
Career Success, edición 2024).

🔗 https://cdn-careerservices.fas.harvard.edu/wp-content/uploads/sites/161/2024/07/2024-gsas-cvs-and-cover-letters.pdf

Documento de 23 páginas que incluye **CVs académicos completos y rellenados**.
Los datos identificativos están anonimizados y los títulos sustituidos por texto
de relleno, pero la estructura y el formato son los reales.

Páginas con ejemplares diligenciados:

| Páginas | Contenido |
|---|---|
| 3 | Lista de verificación con todas las secciones posibles |
| 5–6 | CV de doctoranda en Historia del Arte: educación con tesis y comité, publicaciones, becas, premios, docencia, congresos |
| 7–8 | CV con publicaciones, docencia, idiomas y servicio |
| 9–10 | CV con grants y docencia |
| 12–13 | CV con grants, premios, docencia, publicaciones, congresos |
| 15–16 | CV con premios, servicio y publicaciones |

Ejemplo del encabezado de la página 5:

```
SABINE ROSE
Department of History of Art and Architecture, Harvard University, Cambridge MA 02138
smrose@fas.harvard.edu | 617-555-5555 | she/her/hers

EDUCATION
Harvard University                                              Cambridge, MA
PhD, History of Art and Architecture                         Expected May 2024
Dissertation: "..."
Committee: Joseph F. Klein, Ian Kazmarzek, and Sarah Liebowitz
```

**Por qué sirve de referente:** son CVs de perfil investigador, con las mismas
secciones que produce el sistema (educación, publicaciones, grants, tesis). Útil
para contrastar orden de secciones, densidad de información y estilo de citación.

Guía complementaria de la misma fuente:
🔗 https://careerservices.fas.harvard.edu/resources/gsas-cv-cover-letter-guide/

---

## Europass

**Fuente:** Comisión Europea — portal oficial de Europass.

🔗 https://europass.europa.eu/en/create-europass-cv

A diferencia de Harvard, la Comisión **no publica PDFs de ejemplo ya
diligenciados**. El modelo oficial se obtiene de dos formas:

1. **Plantilla en blanco con instrucciones** (la estructura canónica):
   🔗 https://enlargement.ec.europa.eu/document/download/a0c6aa88-e1df-4a41-bf10-af33f4979f8a_en?filename=cv_eu_en.pdf

   Documento de 2 páginas con todas las secciones y las indicaciones de qué va
   en cada campo. Es la referencia de **qué campos existen y en qué orden**.

2. **Generando uno desde el editor oficial** (la referencia visual):
   🔗 https://europa.eu/europass/eportfolio/screen/cv-editor

   Se crea un perfil, se rellena y se exporta en PDF. Ese archivo es el
   referente más fiel al resultado que espera un evaluador europeo.

> **Recomendación:** generar un CV en el editor oficial con los datos de un
> investigador de prueba y compararlo lado a lado con el que produce el sistema.
> Es la comparación más directa, y no depende de que la Comisión publique
> ejemplares.

Instrucciones oficiales de diligenciamiento:
🔗 https://www.eea.europa.eu/about-us/jobs/application-documents/instructions_for_europass_cv.pdf

---

## Cómo usarlos

Para contrastar un CV generado por el sistema contra estos referentes:

```bash
# 1. Generar el CV
curl -s "http://localhost:3001/api/cv/generate?uri=<uri_investigador>&format=harvard-pdf" \
  -o /tmp/generado.pdf

# 2. Validar métricas de formato (márgenes, fuentes, alineación)
cd verificacion
python verify_fidelity.py --pdf /tmp/generado.pdf --format harvard
```

La comparación visual contra el referente detecta cosas que la validación
automática no cubre: orden de secciones, criterio sobre qué información incluir
y densidad de cada bloque.

---

## Nota sobre derechos

Estos documentos pertenecen a Harvard University y a la Comisión Europea. Se
enlazan como referencia; no se redistribuyen dentro de este repositorio.
