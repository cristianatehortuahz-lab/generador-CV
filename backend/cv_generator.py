"""
HUB-UR: Extractor y Generador de Hojas de Vida
================================================
Extrae datos de investigadores desde Solr + VIVO y genera CVs en formato JSON.

Fuentes de datos:
  - Solr (http://localhost:8983/solr/vivocore): metadata, publicaciones, grants, expertise
  - VIVO (http://localhost:8080): JSON-LD embebido (email, teléfono, afiliaciones, ORCID, Scholar)
  - VIVO HTML: overview, educación, áreas de investigación

Uso:
  from cv_generator import CVExtractor, CVGenerator

  extractor = CVExtractor()
  cv = extractor.extract_by_name("Juan Ramírez")

  generator = CVGenerator()
  path = generator.generate(cv)
"""

import requests
import json
import re
import os
import html as html_module
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# CONFIGURACION
# ============================================================
from dotenv import load_dotenv

load_dotenv()
SOLR_URL = os.environ.get('SOLR_URL', 'http://localhost:8983/solr/vivocore/select').strip()
VIVO_BASE = os.environ.get('VIVO_BASE_URL', 'http://localhost:8080').strip()

OUTPUT_DIR = Path(__file__).parent / "cv_output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ============================================================
# MODELO DE DATOS
# ============================================================
@dataclass
class Publication:
    title: str = ""
    year: str = ""
    type: str = ""
    uri: str = ""
    journal: str = ""
    doi: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    authors: List[str] = field(default_factory=list)

@dataclass
class Grant:
    title: str = ""
    year: str = ""
    year_end: str = ""
    uri: str = ""

@dataclass
class Thesis:
    title: str = ""
    year: str = ""
    uri: str = ""

@dataclass
class CVData:
    """Datos completos de un investigador para generar CV."""
    # Basicos
    name: str = ""
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    photo_url: str = ""
    job_title: str = ""
    uri: str = ""
    vivo_url: str = ""
    
    # Institucional
    department: str = ""
    faculty: str = ""
    organization: str = "Universidad del Rosario"
    affiliations: List[Dict] = field(default_factory=list)
    # Sin dirección por defecto: VIVO no expone la dirección personal del
    # investigador y mostrar una fija (la de la sede) sería un dato falso y
    # un problema de privacidad. Solo se incluye si una fuente real la provee.
    address: str = ""
    
    # Academico
    expertise_areas: List[str] = field(default_factory=list)
    overview: str = ""
    education: List[str] = field(default_factory=list)
    
    # Produccion
    publications: List[Publication] = field(default_factory=list)
    grants: List[Grant] = field(default_factory=list)
    theses: List[Thesis] = field(default_factory=list)
    num_publications: int = 0
    num_grants: int = 0
    num_theses: int = 0
    
    # Enlaces externos
    orcid: str = ""
    google_scholar: str = ""
    cvlac: str = ""
    pure: str = ""
    nationality: str = ""
    other_links: List[str] = field(default_factory=list)
    
    # Metadata
    extracted_at: str = ""
    data_sources: List[str] = field(default_factory=list)


# ============================================================
# EXTRACTOR DE DATOS
# ============================================================
class CVExtractor:
    """Extrae datos de investigadores desde Solr y VIVO."""
    
    # Nº de publicaciones a enriquecer en paralelo desde VIVO (DOI/edición).
    _ENRICH_WORKERS = 10
    # Tope de publicaciones a enriquecer por CV (protege VIVO ante autores muy
    # prolíficos; las primeras N por año ya cubren lo que se muestra).
    _ENRICH_MAX = 250

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        self._name_cache: Dict[str, str] = {}
        # Caché de metadatos por URI de publicación: {uri: {"doi":..,"issue":..}}
        self._pub_meta_cache: Dict[str, Dict[str, str]] = {}
    
    def _sanitize_solr_query(self, q):
        """Escape Solr special characters.
        
        Nota: Esta función solo debe usarse para consultas de texto libre sin comillas.
        Si el valor se encierra en comillas dobles (ej. f'URI:"{uri}"'), NO se debe 
        escapar los caracteres, ya que Solr no encontrará los resultados.
        """
        special = r'+-&|!(){}[]^"~*?:\/'
        for c in special:
            q = q.replace(c, '\\' + c)
        return q

    @staticmethod
    def _escape_solr_quoted(value: str) -> str:
        """Escapar un valor que irá dentro de comillas dobles en una query Solr.

        Neutraliza la barra invertida y la comilla doble para que el usuario no
        pueda romper la frase entrecomillada e inyectar cláusulas (p. ej.
        'Juan" OR ALLTEXT:"'). El backslash debe escaparse primero.
        """
        return (value or "").replace('\\', '\\\\').replace('"', '\\"')

    def search_researchers(self, query: str, rows: int = 20) -> List[Dict]:
        """Buscar investigadores por nombre."""
        # El valor va dentro de comillas dobles: escapamos backslash y comillas
        # para evitar inyección en el parámetro fq.
        safe_q = self._escape_solr_quoted(query)
        params = {
            "q": f'type:"http://xmlns.com/foaf/0.1/Person"',
            "fq": f'nameRaw:"{safe_q}" OR ALLTEXT:"{safe_q}"',
            "rows": rows,
            "wt": "json",
            "fl": "URI,nameRaw,es_label_display,facet_academicDepartment_ss,numPublications,numGrants,numTutoredTheses",
            "sort": "numPublications desc"
        }
        r = self.session.get(SOLR_URL, params=params, timeout=10)
        return r.json()["response"]["docs"]
    
    def extract_by_uri(self, uri: str) -> CVData:
        """Extraer datos completos de un investigador por su URI."""
        cv = CVData()
        cv.uri = uri
        cv.extracted_at = datetime.now().isoformat()
        
        # 1. Datos de Solr
        self._extract_from_solr(cv)
        
        # 2. Datos de VIVO (JSON-LD + HTML)
        self._extract_from_vivo(cv)
        
        return cv
    
    def extract_by_name(self, name: str) -> Optional[CVData]:
        """Extraer datos de un investigador por nombre (búsqueda fuzzy)."""
        results = self.search_researchers(name, rows=5)
        if not results:
            return None
        
        # Tomar el más relevante
        best = results[0]
        uri = best.get("URI", "")
        if not uri:
            return None
        
        cv = self.extract_by_uri(uri)
        return cv
    
    def _extract_from_solr(self, cv: CVData):
        """Extraer datos desde Solr."""
        params = {
            "q": f'URI:"{self._escape_solr_quoted(cv.uri)}"',
            "rows": 1,
            "wt": "json",
            "fl": "*"
        }
        try:
            r = self.session.get(SOLR_URL, params=params, timeout=10)
            docs = r.json()["response"]["docs"]
            if not docs:
                return
            
            doc = docs[0]
            cv.data_sources.append("solr")
            
            # Datos básicos
            cv.name = html_module.unescape(doc.get("es_label_display", doc.get("en-US_label_display", "")))
            if not cv.name:
                cv.name = html_module.unescape(self._first(doc.get("nameRaw", [])))
            cv.photo_url = doc.get("THUMBNAIL_URL", "")
            cv.department = html_module.unescape(self._first(doc.get("facet_academicDepartment_ss", [])))
            
            # Map departments to faculties
            dept_to_faculty = {
                "Escuela de Medicina": "Escuela de Medicina y Ciencias de la Salud",
                "Escuela de Medicina y Ciencias de la Salud": "Escuela de Medicina y Ciencias de la Salud",
                "Escuela de Ciencias e Ingeniería": "Escuela de Ingeniería, Ciencia y Tecnología",
                "Escuela de Ingeniería, Ciencia y Tecnología": "Escuela de Ingeniería, Ciencia y Tecnología",
                "Facultad de Jurisprudencia": "Facultad de Jurisprudencia",
                "Facultad de Economía": "Facultad de Economía",
                "Escuela de Administración": "Escuela de Administración",
                "Escuela de Ciencias Humanas": "Escuela de Ciencias Humanas",
                "Facultad de Estudios Internacionales, Políticos y Urbanos": "Facultad de Estudios Internacionales, Políticos y Urbanos",
                "Facultad de Creación": "Facultad de Creación",
            }
            cv.faculty = dept_to_faculty.get(cv.department, cv.department)

            
            cv.num_publications = doc.get("numPublications", 0)
            cv.num_grants = doc.get("numGrants", 0)
            cv.num_theses = doc.get("numTutoredTheses", 0)
            
            # Expertise
            cv.expertise_areas = doc.get("facet_expertiseAreas_ss", [])
            
            # Separar nombre: "Apellidos, Nombres" — solo el primer split
            if cv.name:
                if "," in cv.name:
                    cv.last_name, cv.first_name = [
                        p.strip() for p in cv.name.split(",", 1)
                    ]
                else:
                    tokens = cv.name.strip().rsplit(None, 1)
                    if len(tokens) == 2:
                        cv.first_name, cv.last_name = tokens
                    else:
                        cv.first_name = cv.name
            
            # Afiliaciones se manejan por JSON-LD en _extract_from_vivo
            cv.affiliations = []
            
        except Exception as e:
            print(f"  [WARN] Error Solr: {e}")
        
        # Extraer publicaciones del investigador
        self._extract_publications(cv)
        
        # Extraer grants del investigador
        self._extract_grants(cv)
        
        # Sincronizar contadores reales tras los filtros de extracción
        cv.num_publications = len(cv.publications)
        cv.num_grants = len(cv.grants)
    
    _NAME_BATCH = 50  # keep OR-query under Solr maxBooleanClauses + Jetty header limits

    def _resolve_person_names(self, uris: List[str]) -> Dict[str, str]:
        """Batch-resolve person URIs to display names via Solr, in chunks."""
        if not uris:
            return {}
        uncached = [u for u in uris if u not in self._name_cache]
        for i in range(0, len(uncached), self._NAME_BATCH):
            chunk = uncached[i:i + self._NAME_BATCH]
            escaped = " OR ".join(
                f'"{self._escape_solr_quoted(u)}"' for u in chunk
            )
            params = {
                "q": f"URI:({escaped})",
                "rows": len(chunk),
                "wt": "json",
                "fl": "URI,nameRaw,es_label_display",
            }
            try:
                r = self.session.get(SOLR_URL, params=params, timeout=10)
                for doc in r.json().get("response", {}).get("docs", []):
                    uri = doc.get("URI", "")
                    raw = doc.get("es_label_display", self._first(doc.get("nameRaw", [])))
                    if uri and raw:
                        name = html_module.unescape(raw)
                        if "," in name:
                            last, first = name.split(",", 1)
                            name = f"{first.strip()} {last.strip()}"
                        self._name_cache[uri] = name
            except Exception:
                pass
            for u in chunk:
                self._name_cache.setdefault(u, "")
        return {u: self._name_cache.get(u, "") for u in uris}

    def _extract_publications(self, cv: CVData):
        """Extraer publicaciones del investigador desde Solr."""
        NON_PUB_TYPES = {
            "Award", "Grant", "Contract", "FundingOrganization",
            "ProjectGrant", "ResearchGrant", "TrainingGrant"
        }

        params = {
            "q": f'persons_ss:"{self._escape_solr_quoted(cv.uri)}"',
            "fq": 'classgroup:"http://vivoweb.org/ontology#vitroClassGrouppublications"',
            "rows": 500,
            "wt": "json",
            "fl": "URI,es_label_display,en-US_label_display,publication_year_ss,"
                  "mostSpecificTypeURIs,journal_ss,volume,issue,pageStart,pageEnd,"
                  "doi,persons_ss",
            "sort": "publication_year_ss desc"
        }
        try:
            r = self.session.get(SOLR_URL, params=params, timeout=10)
            data = r.json()
            if "response" not in data:
                return
            docs = data["response"]["docs"]

            # Collect all person URIs across all publications for batch resolve
            all_person_uris: set = set()
            for doc in docs:
                for uri in doc.get("persons_ss", []):
                    all_person_uris.add(uri)
            self._resolve_person_names(list(all_person_uris))

            for doc in docs:
                pub_type_raw = self._extract_type(doc.get("mostSpecificTypeURIs", []))
                if pub_type_raw in NON_PUB_TYPES:
                    continue

                title = doc.get("es_label_display", doc.get("en-US_label_display", ""))
                title = html_module.unescape(title)

                # Build pages string
                page_start = doc.get("pageStart", "")
                page_end = doc.get("pageEnd", "")
                pages = ""
                if page_start:
                    pages = str(page_start)
                    if page_end and str(page_end) != str(page_start):
                        pages += f"–{page_end}"

                # Resolve authors from persons_ss
                author_uris = doc.get("persons_ss", [])
                authors = [
                    self._name_cache[u]
                    for u in author_uris
                    if self._name_cache.get(u)
                ]

                pub = Publication(
                    title=title,
                    year=self._first(doc.get("publication_year_ss", [])),
                    type=pub_type_raw,
                    uri=doc.get("URI", ""),
                    journal=html_module.unescape(self._first(doc.get("journal_ss", []))),
                    doi=doc.get("doi", ""),
                    volume=doc.get("volume", ""),
                    issue=doc.get("issue", ""),
                    pages=pages,
                    authors=authors,
                )
                cv.publications.append(pub)

            # Enriquecer con DOI/edición desde la página VIVO de cada publicación
            # (esos campos no están en Solr). Fetch en paralelo + caché.
            self._enrich_publications(cv.publications)
        except Exception as e:
            print(f"  [WARN] Error publicaciones: {e}")

    def _fetch_pub_meta(self, uri: str) -> Dict[str, str]:
        """Descargar la página VIVO de una publicación y extraer DOI y edición.

        Estos campos no existen en Solr; solo se muestran en el HTML individual.
        Resultado cacheado por URI.
        """
        if uri in self._pub_meta_cache:
            return self._pub_meta_cache[uri]
        meta = {"doi": "", "issue": ""}
        try:
            from urllib.parse import quote as _q
            url = f"{VIVO_BASE}/individual?uri={_q(uri, safe='')}"
            r = self.session.get(url, timeout=10, headers={"Accept": "text/html"})
            if r.status_code == 200:
                html = r.text
                # DOI: preferir el enlace doi.org (fiable), luego patrón suelto.
                m = re.search(r'doi\.org/(10\.\d{4,9}/[^\s"\'<>]+)', html)
                if not m:
                    m = re.search(r'"(10\.\d{4,9}/[^\s"\'<>]+)"', html)
                if m:
                    meta["doi"] = m.group(1).rstrip('.,;')
                # Edición: <ul ... id="edition-...-List"> <li> 11 </li>
                me = re.search(
                    r'id="edition-[^"]*-List"[^>]*>(.*?)</ul>', html, re.DOTALL)
                if me:
                    val = re.sub(r'<[^>]+>', ' ', me.group(1))
                    val = re.sub(r'\s+', ' ', val).strip()
                    if val:
                        meta["issue"] = val
        except Exception:
            pass
        self._pub_meta_cache[uri] = meta
        return meta

    def _enrich_publications(self, pubs: List["Publication"]):
        """Poblar doi/issue de cada publicación en paralelo desde VIVO."""
        targets = [p for p in pubs if p.uri][: self._ENRICH_MAX]
        if not targets:
            return
        try:
            with ThreadPoolExecutor(max_workers=self._ENRICH_WORKERS) as ex:
                future_map = {ex.submit(self._fetch_pub_meta, p.uri): p
                              for p in targets}
                for fut in as_completed(future_map):
                    pub = future_map[fut]
                    try:
                        meta = fut.result()
                    except Exception:
                        continue
                    if not pub.doi and meta.get("doi"):
                        pub.doi = meta["doi"]
                    if not pub.issue and meta.get("issue"):
                        pub.issue = meta["issue"]
        except Exception as e:
            print(f"  [WARN] Error enriqueciendo publicaciones: {e}")

    def _extract_grants(self, cv: CVData):
        """Extraer proyectos/grants del investigador desde Solr."""
        params = {
            "q": f'persons_ss:"{self._escape_solr_quoted(cv.uri)}"',
            "fq": 'type:"http://vivoweb.org/ontology/core#Grant"',
            "rows": 100,
            "wt": "json",
            "fl": "URI,es_label_display,en-US_label_display,dates_drsim",
            # Nota: NO ordenar por dates_drsim en Solr — es un SpatialField y el
            # sort lanza error que aborta toda la consulta (grants=0). El orden
            # descendente por año se hace en Python más abajo.
        }
        try:
            r = self.session.get(SOLR_URL, params=params, timeout=10)
            data = r.json()
            if "response" not in data:
                return
            docs = data["response"]["docs"]
            for doc in docs:
                title = doc.get("es_label_display", doc.get("en-US_label_display", ""))
                title = html_module.unescape(title)
                raw_date = doc.get("dates_drsim", "")
                year = ""
                year_end = ""
                if raw_date:
                    years = re.findall(r'(\d{4})', str(raw_date))
                    if years:
                        year = years[0]
                    if len(years) >= 2 and years[-1] != years[0]:
                        year_end = years[-1]
                grant = Grant(title=title, year=year, year_end=year_end,
                              uri=doc.get("URI", ""))
                cv.grants.append(grant)
            cv.grants.sort(key=lambda g: g.year or "", reverse=True)
        except Exception as e:
            print(f"  [WARN] Error grants: {e}")
    
    def _extract_from_vivo(self, cv: CVData):
        """Extraer datos desde VIVO (JSON-LD + HTML scraping)."""
        # Extraer URI corta para la URL
        short_uri = cv.uri.split("/individual/")[-1] if "/individual/" in cv.uri else cv.uri
        vivo_url = f"{VIVO_BASE}/individual?uri={cv.uri}"
        cv.vivo_url = vivo_url
        
        try:
            r = self.session.get(vivo_url, timeout=15, headers={"Accept": "text/html"})
            if r.status_code != 200:
                return
            
            html = r.text
            cv.data_sources.append("vivo_html")
            
            # JSON-LD
            self._parse_jsonld(cv, html)
            
            # Overview
            self._parse_overview(cv, html)

            # Educación
            self._parse_education(cv, html)

            # Tesis dirigidas
            self._parse_theses(cv, html)

        except Exception as e:
            print(f"  [WARN] Error VIVO: {e}")
    
    def _parse_jsonld(self, cv: CVData, html: str):
        """Extraer datos del JSON-LD embebido en la página."""
        match = re.search(r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL)
        if not match:
            return
        
        try:
            data = json.loads(match.group(1))
            cv.data_sources.append("jsonld")
            
            cv.name = cv.name or data.get("name", "")
            cv.job_title = data.get("jobTitle", "")
            cv.email = data.get("email", "")
            cv.phone = data.get("telephone", "")
            cv.photo_url = cv.photo_url or data.get("image", "")
            
            # Afiliaciones (dedup por name+role, orden: facultad → grupos → otros)
            GENERIC_ROLES = {
                "Authorship", "Investigator Role", "Member Role",
                "Researcher Role", "Presenter Role", "Authorship Role"
            }

            if "affiliation" in data:
                seen: set = set()
                raw_affs: List[Dict] = []
                for aff in data["affiliation"]:
                    if not isinstance(aff, dict):
                        continue
                    name = aff.get("name", "")
                    # R11 — el organization ya indica "Universidad del Rosario"
                    # en el bloque superior; en las afiliaciones sale duplicado
                    # como sufijo "…Escuela… - Universidad del Rosario".
                    name = re.sub(
                        r"\s*[-–]\s*Universidad\s+del\s+Rosario\s*$",
                        "",
                        name,
                        flags=re.IGNORECASE,
                    ).strip()
                    role = aff.get("roleName", aff.get("role", ""))
                    if role in GENERIC_ROLES:
                        continue
                    if not role or role.lower() in ("member", "researcher"):
                        nl = name.lower()
                        if "facultad" in nl or "escuela" in nl or "school" in nl:
                            role = "Faculty Member"
                        elif "grupo" in nl or "group" in nl:
                            role = "Research Group Member"
                        elif "institut" in name.lower():
                            role = "Affiliate"
                        else:
                            role = "Affiliate"
                    key = (name.lower(), role.lower())
                    if key in seen:
                        continue
                    seen.add(key)
                    raw_affs.append({"name": name, "role": role})

                def _aff_order(a):
                    n = a["name"].lower()
                    if "facultad" in n or "escuela" in n or "school" in n:
                        return 0
                    if "grupo" in n or "group" in n:
                        return 1
                    return 2
                raw_affs.sort(key=_aff_order)
                cv.affiliations = raw_affs
            
            # Enlaces externos
            for link in data.get("sameAs", []):
                if "orcid.org" in link:
                    cv.orcid = link
                elif "scholar.google" in link:
                    cv.google_scholar = link
                elif "scienti.minciencias" in link:
                    cv.cvlac = link
                elif "pure.urosario" in link:
                    cv.pure = link
                elif "scopus" in link:
                    pass  # Scopus Author ID - could add cv.scopus_id field
                elif "researcherid" in link or "webofscience" in link:
                    pass  # ResearcherID - could add cv.researcher_id field
                else:
                    cv.other_links.append(link)
            
            # Workplace
            if "worksFor" in data:
                wf = data["worksFor"]
                cv.organization = wf.get("name", cv.organization)
            
            # Nationality (if available in JSON-LD)
            if "nationality" in data:
                nat = data["nationality"]
                if isinstance(nat, dict):
                    cv.nationality = nat.get("name", "")
                elif isinstance(nat, str):
                    cv.nationality = nat
                
        except json.JSONDecodeError:
            pass
    
    def _parse_overview(self, cv: CVData, html: str):
        """Extraer texto del overview/resumen."""
        match = re.search(r'id="overview"[^>]*>(.*?)(?:</section|<h[23])', html, re.DOTALL)
        if match:
            text = self._clean_html(match.group(1))
            # Limpiar titulo de seccion que se cuela
            text = re.sub(r'^Perfil\s+Profesional\s*', '', text, flags=re.I).strip()
            text = re.sub(r'^Overview\s*', '', text, flags=re.I).strip()
            # Also strip trailing section headers
            for header in ["Formación Académica", "Education", "Academic Background", "Research Areas", "Research Interests"]:
                text = text.replace(header, "").strip()
            if text and len(text) > 20:
                cv.overview = text
    
    def _parse_education(self, cv: CVData, html: str):
        """Extraer datos de formación académica, ordenados por año descendente."""
        match = re.search(r'id="EducationalTrainingBackground"[^>]*>(.*?)(?:</section|<h[23])', html, re.DOTALL)
        if match:
            items = re.findall(r'<li[^>]*>(.*?)</li>', match.group(1), re.DOTALL)
            raw = []
            for item in items:
                text = self._clean_html(item)
                if text and len(text) > 5:
                    raw.append(text)
            # Sort by year descending (extract year for sorting key)
            def _edu_year(entry_str):
                m = re.search(r'\b(\d{4})\b', entry_str)
                return -int(m.group(1)) if m else 0
            raw.sort(key=_edu_year)
            cv.education = raw

    def _parse_theses(self, cv: CVData, html: str):
        """Extraer tesis dirigidas (Tutorías) del HTML de VIVO."""
        start = html.find('TutorOf-Thesis-List')
        if start == -1:
            return
        chunk = html[start:start + 15000]
        items = re.findall(
            r'<li[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>\s*<span[^>]*>([^<]*)</span>',
            chunk, re.DOTALL
        )
        for href, title, _ in items:
            title = title.strip()
            if not title:
                continue
            year_m = re.search(r'\b((?:19|20)\d{2})\b', title)
            uri_id = href.split("/")[-1] if "/" in href else href
            cv.theses.append(Thesis(
                title=title,
                year=year_m.group(1) if year_m else "",
                uri=uri_id,
            ))
        cv.theses.sort(key=lambda t: -int(t.year) if t.year else 0)

    @staticmethod
    def _clean_html(s: str) -> str:
        s = re.sub(r'<[^>]+>', ' ', s)
        s = re.sub(r'\s+', ' ', s).strip()
        return html_module.unescape(s)
    
    @staticmethod
    def _first(lst: list) -> str:
        return lst[0] if lst else ""
    
    @staticmethod
    def _extract_type(types: list) -> str:
        for t in types:
            if "#" in t:
                return t.split("#")[-1]
            if "/" in t:
                return t.split("/")[-1]
        return ""


# ============================================================
# GENERADOR DE CV
# ============================================================
class CVGenerator:
    """Genera hojas de vida en formato JSON."""
    
    def __init__(self, output_dir: Path = OUTPUT_DIR):
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)
    
    def generate(self, cv: CVData, formats: List[str] = None) -> List[str]:
        """Generar CV en formato JSON. Retorna lista de archivos generados."""
        safe_name = re.sub(r'[^\w\s-]', '', cv.name).strip()
        safe_name = re.sub(r'\s+', '_', safe_name)
        if not safe_name:
            safe_name = "investigador"
        path = self._generate_json(cv, safe_name)
        return [str(path)]
    
    def _generate_json(self, cv: CVData, name: str) -> Path:
        """Generar CV en formato JSON estructurado."""
        path = self.output_dir / f"{name}.json"
        data = asdict(cv)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  [OK] JSON: {path}")
        return path

    # ── API methods ──────────────────────────────────────────────────
    def to_json(self, cv: CVData) -> str:
        """Retorna CV como string JSON."""
        return json.dumps(asdict(cv), ensure_ascii=False, indent=2)
