"""
HUB-UR — Backend de Hojas de Vida
==================================
Servidor HTTP que expone la generación de hojas de vida a partir de los datos
de un investigador indexados en Solr.

Endpoints:
  GET /api/cv/generate?uri=<uri>&format=<harvard-pdf|europass-pdf>
  GET /health

La extracción de datos vive en `cv_generator.py`; la construcción de cada
formato en `harvard_cv.py` (Harvard) y `pdf_filler.py` (Europass).
"""
import json
import os
import re
import time
import socket
import subprocess
import threading
import uuid
import requests
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, quote

from dotenv import load_dotenv

load_dotenv()

# ═════════════════════════════════════════════════════════════════════════════
# Configuración
# ═════════════════════════════════════════════════════════════════════════════

PORT = int(os.environ.get('PORT', '3001'))
SOLR_URL = os.environ.get('SOLR_URL', 'http://localhost:8983/solr/vivocore/select').strip()

ALLOWED_ORIGINS = [x.strip() for x in os.environ.get(
    'ALLOWED_ORIGINS',
    'http://localhost:8080,http://127.0.0.1:8080,http://localhost:3000,'
    'http://research-hub.urosario.edu.co,https://research-hub.urosario.edu.co'
).split(',')]
ALLOWED_METHODS = ['GET', 'OPTIONS']
ALLOWED_HEADERS = ['Content-Type']

# El servicio no pide clave de API. El control de acceso lo da la red: el
# servidor escucha solo en la interfaz de loopback (BIND_HOST, 127.0.0.1 por
# defecto), asi que unicamente los procesos del propio servidor pueden
# alcanzarlo. Desde fuera se llega a traves del proxy de Tomcat.
# Si algun dia se expone el puerto a otras maquinas, habra que reintroducir
# autenticacion.

# Rate limiting por IP: la generación de PDF es costosa (conversión a documento).
CV_RATE_LIMIT = int(os.environ.get('CV_RATE_LIMIT', '5'))     # peticiones
CV_RATE_WINDOW = int(os.environ.get('CV_RATE_WINDOW', '60'))  # segundos


# ═════════════════════════════════════════════════════════════════════════════
# Componentes de generación
# ═════════════════════════════════════════════════════════════════════════════

try:
    from cv_generator import CVExtractor, CVGenerator
    CV_AVAILABLE = True
    cv_extractor = CVExtractor()
    cv_generator = CVGenerator()
    print("  [INFO] Extractor de datos cargado correctamente.")
except ImportError:
    CV_AVAILABLE = False
    cv_extractor = None
    cv_generator = None
    print("  [INFO] Extractor de datos no disponible.")

try:
    from harvard_cv import generate_harvard_pdf
    HARVARD_AVAILABLE = True
    print("  [INFO] Generador Harvard cargado correctamente.")
except ImportError:
    HARVARD_AVAILABLE = False
    generate_harvard_pdf = None
    print("  [INFO] Generador Harvard no disponible.")

try:
    from pdf_filler import fill_europass as fill_europass_pdf
    # Ruta de la plantilla Europass configurable por entorno; por defecto una
    # plantilla genérica (sin datos personales) junto al script.
    _europass_template = os.environ.get('EUROPASS_TEMPLATE', '').strip()
    if not _europass_template:
        _europass_template = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                          'formatos', 'europass_template.pdf')
    EUROPASS_PDF_AVAILABLE = os.path.exists(_europass_template)
    if EUROPASS_PDF_AVAILABLE:
        print(f"  [INFO] Generador Europass cargado. Plantilla: {_europass_template}")
    else:
        print(f"  [WARN] Plantilla Europass no encontrada: {_europass_template}")
except ImportError as e:
    EUROPASS_PDF_AVAILABLE = False
    fill_europass_pdf = None
    _europass_template = None
    print(f"  [INFO] Generador Europass no disponible: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# Caché, límites y utilidades
# ═════════════════════════════════════════════════════════════════════════════

_cv_cache = {}  # uri -> (timestamp, cv)
CV_CACHE_TTL = 300   # 5 minutos
CV_CACHE_MAX = 200
_cv_cache_lock = threading.Lock()


def get_cached_cv(uri):
    """Devuelve el CV cacheado, o None si expiró o no existe."""
    with _cv_cache_lock:
        if uri in _cv_cache:
            ts, cv = _cv_cache[uri]
            if time.time() - ts < CV_CACHE_TTL:
                return cv
    return None


def set_cached_cv(uri, cv):
    """Guarda el CV en caché con la marca de tiempo actual."""
    with _cv_cache_lock:
        _cv_cache[uri] = (time.time(), cv)
        # Purgar entradas si la caché crece demasiado
        if len(_cv_cache) > CV_CACHE_MAX:
            cutoff = time.time() - CV_CACHE_TTL
            for k in [k for k, (ts, _) in _cv_cache.items() if ts < cutoff]:
                del _cv_cache[k]
            # Si aún supera el tope (nada expirado), eliminar los más antiguos.
            if len(_cv_cache) > CV_CACHE_MAX:
                for k, _ in sorted(_cv_cache.items(), key=lambda kv: kv[1][0])[
                        :len(_cv_cache) - CV_CACHE_MAX]:
                    del _cv_cache[k]


# Lock global para la generación: la conversión a documento no es reentrante,
# así que serializamos las generaciones Harvard/Europass entre hilos.
_pdf_gen_lock = threading.Lock()

_cv_rate = {}  # ip -> [timestamps]
_cv_rate_lock = threading.Lock()


def cv_rate_limit_ok(ip):
    """True si la IP está dentro del límite; registra la petición actual."""
    now = time.time()
    with _cv_rate_lock:
        hits = [t for t in _cv_rate.get(ip, []) if now - t < CV_RATE_WINDOW]
        if len(hits) >= CV_RATE_LIMIT:
            _cv_rate[ip] = hits
            return False
        hits.append(now)
        _cv_rate[ip] = hits
        return True


def content_disposition(filename):
    """Content-Disposition robusto para nombres con acentos/Unicode.

    Los headers HTTP se codifican en latin-1; un nombre con caracteres fuera de
    ese rango rompería send_header. Emitimos un `filename=` ASCII de respaldo y
    un `filename*=UTF-8''` (RFC 5987) con el nombre completo percent-encoded.
    """
    ascii_fallback = filename.encode('ascii', 'ignore').decode('ascii') or 'cv.pdf'
    encoded = quote(filename, safe='')
    return 'attachment; filename="{0}"; filename*=UTF-8\'\'{1}'.format(
        ascii_fallback, encoded)


def purge_cv_output(max_age_hours=24):
    """Eliminar archivos antiguos acumulados en cv_output/ al arrancar."""
    if not cv_generator:
        return
    try:
        cutoff = time.time() - max_age_hours * 3600
        removed = 0
        for f in cv_generator.output_dir.iterdir():
            if f.is_file() and f.stat().st_mtime < cutoff:
                try:
                    f.unlink()
                    removed += 1
                except OSError:
                    pass
        if removed:
            print(f"  [CLEANUP] cv_output: {removed} archivo(s) antiguo(s) eliminado(s).")
    except Exception as e:
        print(f"  [CLEANUP] Error purgando cv_output: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# RobustHTTPServer: ThreadingHTTPServer que no muere por un client disconnect
# ═════════════════════════════════════════════════════════════════════════════

class RobustHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    allow_reuse_port = True

    def process_request_thread(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except (ConnectionAbortedError, BrokenPipeError, OSError) as e:
            print(f"   [CONN] Cliente {client_address} desconectado: {e}")
        except Exception as e:
            print(f"   [ERROR] Excepción en request de {client_address}: {type(e).__name__}: {e}")
        finally:
            try:
                self.shutdown_request(request)
            except Exception:
                self.close_request(request)


# ═════════════════════════════════════════════════════════════════════════════
# CVHandler: manejador HTTP
# ═════════════════════════════════════════════════════════════════════════════

class CVHandler(BaseHTTPRequestHandler):

    # ── CORS ─────────────────────────────────────────────────────────────
    def do_OPTIONS(self):
        self.send_response(200)
        origin = self.headers.get('Origin', '')
        allowed_origin = origin if origin in ALLOWED_ORIGINS else ALLOWED_ORIGINS[0]
        self.send_header('Access-Control-Allow-Origin', allowed_origin)
        self.send_header('Access-Control-Allow-Methods', ', '.join(ALLOWED_METHODS))
        self.send_header('Access-Control-Allow-Headers', ', '.join(ALLOWED_HEADERS))
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()

    def set_cors(self, origin=None):
        allowed_origin = origin if origin and origin in ALLOWED_ORIGINS else ALLOWED_ORIGINS[0]
        self.send_header('Access-Control-Allow-Origin', allowed_origin)

    # ── IP real del cliente ──────────────────────────────────────────────
    def _real_client_ip(self):
        """IP real del cliente. El backend escucha en 127.0.0.1 detrás del
        proxy Tomcat, que reenvía la IP original en X-Forwarded-For."""
        xff = self.headers.get('X-Forwarded-For', '')
        if xff.strip():
            return xff.split(',')[0].strip()
        return self.client_address[0] if self.client_address else 'unknown'

    def _send_json(self, status, payload):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.set_cors()
        self.end_headers()
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode('utf-8'))

    # ── Generación de la hoja de vida ────────────────────────────────────
    def _handle_cv_generate(self):
        """Generar el PDF de un investigador."""
        if not CV_AVAILABLE:
            self._send_json(503, {'error': 'Extractor de datos no disponible'})
            return

        # Rate limiting por IP: la generación es costosa. Se usa la IP real
        # reenviada por el proxy (X-Forwarded-For); de otro modo todas las
        # peticiones llegarían como 127.0.0.1 y el límite sería global.
        client_ip = self._real_client_ip()
        if not cv_rate_limit_ok(client_ip):
            self.send_response(429)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Retry-After', str(CV_RATE_WINDOW))
            self.set_cors()
            self.end_headers()
            self.wfile.write(json.dumps(
                {'error': f'Demasiadas solicitudes. Intente de nuevo en {CV_RATE_WINDOW} segundos.'}
            ).encode('utf-8'))
            return

        qs = parse_qs(urlparse(self.path).query)
        name = qs.get('name', [''])[0]
        uri = qs.get('uri', [''])[0]
        fmt = qs.get('format', ['harvard-pdf'])[0]
        if not name and not uri:
            self._send_json(400, {'error': 'Parámetro name o uri requerido'})
            return

        if fmt not in ('harvard-pdf', 'harvard_pdf', 'europass-pdf', 'europass_pdf'):
            self._send_json(400, {'error': 'Solo se soportan formatos PDF',
                                  'formats': ['harvard-pdf', 'europass-pdf']})
            return

        try:
            from dataclasses import asdict

            cache_key = uri or name
            cv = get_cached_cv(cache_key)
            if cv is None:
                if uri:
                    cv = cv_extractor.extract_by_uri(uri)
                else:
                    cv = cv_extractor.extract_by_name(name)
                if cv:
                    set_cached_cv(cache_key, cv)
            if not cv:
                self._send_json(404, {'error': 'Investigador no encontrado'})
                return

            # No generar un CV sin titular identificado.
            if not (cv.name or "").strip():
                self._send_json(422, {
                    'error': 'No se pudo determinar el nombre del titular; el CV no se generó.'
                })
                return

            data = asdict(cv)
            # Nombre para el archivo: conserva letras (incl. acentuadas) y quita
            # signos de puntuación / caracteres no seguros.
            safe_name = re.sub(r'[^\w\sÀ-ɏ-]', '', cv.name).strip().replace(' ', '_')
            if not safe_name:
                safe_name = 'hoja_de_vida'

            # ── Harvard ──────────────────────────────────────────────
            if fmt in ('harvard-pdf', 'harvard_pdf'):
                if not HARVARD_AVAILABLE:
                    self._send_json(503, {'error': 'Generador Harvard no disponible'})
                    return
                try:
                    with _pdf_gen_lock:
                        pdf_bytes = generate_harvard_pdf(data)
                except Exception as gen_err:
                    print(f"   [CV] Error Harvard: {type(gen_err).__name__}: {gen_err}")
                    self._send_json(500, {'error': 'Error generando el PDF Harvard'})
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'application/pdf')
                self.send_header('Content-Disposition', content_disposition(f'{safe_name}_Harvard.pdf'))
                self.send_header('Content-Length', str(len(pdf_bytes)))
                self.set_cors()
                self.send_header('Access-Control-Expose-Headers', 'Content-Disposition, Content-Length')
                self.end_headers()
                self.wfile.write(pdf_bytes)

            # ── Europass (plantilla oficial) ─────────────────────────
            elif fmt in ('europass-pdf', 'europass_pdf'):
                if not EUROPASS_PDF_AVAILABLE:
                    self._send_json(503, {'error': 'Europass no disponible. Plantilla no encontrada.'})
                    return
                unique_id = uuid.uuid4().hex[:8]
                out_path = str(cv_generator.output_dir / f"{safe_name}_Europass_{unique_id}.pdf")
                try:
                    with _pdf_gen_lock:
                        fill_europass_pdf(data, _europass_template, out_path)
                except Exception as gen_err:
                    print(f"   [CV] Error Europass: {type(gen_err).__name__}: {gen_err}")
                    self._send_json(500, {'error': 'Error generando el PDF Europass'})
                    return
                try:
                    with open(out_path, 'rb') as f:
                        pdf_data = f.read()
                finally:
                    if os.path.exists(out_path):
                        try:
                            os.remove(out_path)
                        except Exception:
                            pass
                self.send_response(200)
                self.send_header('Content-Type', 'application/pdf')
                self.send_header('Content-Disposition', content_disposition(f'{safe_name}_Europass.pdf'))
                self.send_header('Content-Length', str(len(pdf_data)))
                self.set_cors()
                self.send_header('Access-Control-Expose-Headers', 'Content-Disposition, Content-Length')
                self.end_headers()
                self.wfile.write(pdf_data)

        except Exception as e:
            print(f"   [CV] Error generando CV: {type(e).__name__}: {e}")
            self._send_json(500, {'error': 'Error interno generando el CV'})

    # ── Rutas ────────────────────────────────────────────────────────────
    def do_POST(self):
        self._send_json(404, {'error': 'Endpoint no encontrado'})

    def do_GET(self):
        if self.path == '/health':
            solr_ok = False
            try:
                r = requests.get(SOLR_URL.replace('/select', '/admin/ping'), timeout=3)
                solr_ok = r.status_code == 200
            except Exception:
                pass
            self._send_json(200, {
                "status": "ok" if solr_ok else "degraded",
                "services": {
                    "solr": "ok" if solr_ok else "unavailable",
                    "harvard": "ok" if HARVARD_AVAILABLE else "unavailable",
                    "europass": "ok" if EUROPASS_PDF_AVAILABLE else "unavailable",
                    "api": "ok",
                },
                "cache_size": len(_cv_cache),
            })
            return

        base_path = self.path.split('?')[0]
        if base_path in ('/', '/index.html'):
            self.send_response(302)
            self.send_header('Location', os.environ.get('VIVO_BASE_URL', 'http://localhost:8080'))
            self.set_cors()
            self.end_headers()
            return

        if self.path.startswith('/api/cv/generate'):
            return self._handle_cv_generate()

        self._send_json(404, {'error': 'Endpoint no encontrado'})


# ═════════════════════════════════════════════════════════════════════════════
# Arranque: limpieza de puerto y auto-reinicio
# ═════════════════════════════════════════════════════════════════════════════

def kill_stale_processes(port):
    try:
        result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True, timeout=5)
        for line in result.stdout.splitlines():
            if f':{port}' in line and 'LISTENING' in line:
                pid = line.split()[-1]
                subprocess.run(['taskkill', '/F', '/PID', pid],
                               capture_output=True, timeout=5)
                print(f"  [CLEANUP] Proceso previo (PID {pid}) terminado.")
    except Exception:
        pass


def cleanup_port_with_socket(port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', port))
        s.close()
        return True
    except OSError:
        return False


if __name__ == '__main__':
    print(f"HUB-UR — Backend de Hojas de Vida | Puerto {PORT}")
    print("  /api/cv/generate -> Generar hoja de vida (harvard-pdf, europass-pdf)")
    print("  /health          -> Estado de servicios")
    print(f"  Límite: {CV_RATE_LIMIT} peticiones / {CV_RATE_WINDOW}s por IP | Caché: {CV_CACHE_TTL}s")

    kill_stale_processes(PORT)
    purge_cv_output()
    time.sleep(1)

    restart_count = 0
    MAX_RESTARTS = 10

    while restart_count <= MAX_RESTARTS:
        try:
            if not cleanup_port_with_socket(PORT):
                print(f"  [WARN] Puerto {PORT} ocupado, limpiando...")
                kill_stale_processes(PORT)
                time.sleep(2)

            # Escuchar solo en loopback: el acceso público llega vía el proxy
            # de Tomcat (same-origin). Configurable con BIND_HOST si se necesita.
            bind_host = os.environ.get('BIND_HOST', '127.0.0.1')
            server = RobustHTTPServer((bind_host, PORT), CVHandler)
            print(f"  [OK] Servidor escuchando en {bind_host}:{PORT}")
            server.serve_forever()

        except KeyboardInterrupt:
            print("\n  [SHUTDOWN] Ctrl+C recibido. Cerrando servidor...")
            try:
                server.shutdown()
            except Exception:
                pass
            break

        except Exception as e:
            restart_count += 1
            print(f"  [FATAL] Servidor murió: {e}")
            if restart_count <= MAX_RESTARTS:
                print(f"  [RESTART] Reiniciando ({restart_count}/{MAX_RESTARTS}) en 3s...")
                time.sleep(3)
            else:
                print(f"  [ABORT] Máximo de reinicios alcanzado ({MAX_RESTARTS}). Abortando.")
                break
