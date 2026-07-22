package co.edu.urosario.hubur;

import javax.servlet.http.*;
import javax.servlet.*;
import java.io.*;
import java.net.*;

/**
 * Reverse proxy que reenvía /api/cv/generate (GET) al backend de hojas de vida
 * que escucha en localhost:3001.
 *
 * Por qué hace falta un proxy: el backend escucha solo en loopback, de modo que
 * no es alcanzable desde fuera del servidor. El navegador habla con Tomcat y
 * Tomcat reenvía la petición, evitando además peticiones entre orígenes.
 *
 * Qué hace:
 *  - Solo acepta la ruta /generate y el método GET; el resto -> 400/405.
 *  - Reenvía X-Forwarded-For con la IP real del cliente, para que el límite de
 *    peticiones del backend no vea siempre 127.0.0.1.
 *  - Fuerza la respuesta a application/pdf con X-Content-Type-Options: nosniff.
 *  - No reenvía el cuerpo de error del backend (evita filtrar trazas internas).
 *
 * Sobre el parámetro 'format': este proxy NO lo valida. El backend es la única
 * fuente de verdad sobre qué formatos existen, así que añadir uno nuevo solo
 * requiere tocar el código Python; este servlet no se recompila.
 */
public class CVProxyServlet extends HttpServlet {

    private static final String BACKEND = "http://localhost:3001";

    @Override
    protected void service(HttpServletRequest req, HttpServletResponse resp)
            throws ServletException, IOException {

        String method = req.getMethod();

        // Petición same-origin: no se requieren cabeceras CORS.
        if ("OPTIONS".equalsIgnoreCase(method)) {
            resp.setStatus(204);
            return;
        }

        // Solo se permite GET para la descarga del CV.
        if (!"GET".equalsIgnoreCase(method)) {
            resp.setHeader("Allow", "GET");
            sendError(resp, 405, "Método no permitido.");
            return;
        }

        // Lista blanca de ruta: únicamente /api/cv/generate.
        String pathInfo = req.getPathInfo() != null ? req.getPathInfo() : "";
        if (!"/generate".equals(pathInfo)) {
            sendError(resp, 400, "Ruta no válida.");
            return;
        }

        // El parámetro 'format' se reenvía sin validar: el backend decide qué
        // formatos acepta y responde 400 si no reconoce el solicitado. Así un
        // formato nuevo no obliga a recompilar este servlet.

        // Construir URL del backend reusando el query string original.
        String queryString = req.getQueryString();
        String backendUrl = BACKEND + "/api/cv/generate";
        if (queryString != null && !queryString.isEmpty()) {
            backendUrl += "?" + queryString;
        }

        HttpURLConnection conn = null;
        try {
            conn = (HttpURLConnection) new URL(backendUrl).openConnection();
            conn.setRequestMethod("GET");
            conn.setConnectTimeout(10000);
            // La generación Harvard convierte DOCX->PDF (LibreOffice/Word) y puede
            // tardar cuando arranca en frío; damos margen amplio.
            conn.setReadTimeout(90000);
            conn.setInstanceFollowRedirects(false);

            String accept = req.getHeader("Accept");
            if (accept != null) {
                conn.setRequestProperty("Accept", accept);
            }
            // IP real del cliente para que el rate-limit del backend no vea 127.0.0.1.
            conn.setRequestProperty("X-Forwarded-For", clientIp(req));

            int status = conn.getResponseCode();

            if (status >= 200 && status < 300) {
                // Descarga válida: forzar tipo PDF y evitar content-sniffing.
                resp.setStatus(status);
                resp.setContentType("application/pdf");
                resp.setHeader("X-Content-Type-Options", "nosniff");
                String contentDisposition = conn.getHeaderField("Content-Disposition");
                if (contentDisposition != null) {
                    resp.setHeader("Content-Disposition", contentDisposition);
                }
                copy(conn.getInputStream(), resp.getOutputStream());
            } else {
                // No reenviar el cuerpo de error del backend (posibles trazas/rutas).
                log("CVProxyServlet: backend respondió " + status + " para " + pathInfo);
                sendError(resp, status >= 400 && status < 600 ? status : 502,
                          "No se pudo generar la hoja de vida.");
            }
        } catch (IOException e) {
            log("CVProxyServlet: error contactando el backend: " + e.getMessage());
            sendError(resp, 502, "Servicio de hojas de vida no disponible.");
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
    }

    /** Devuelve la IP del cliente, respetando un X-Forwarded-For entrante si existe. */
    private String clientIp(HttpServletRequest req) {
        String xff = req.getHeader("X-Forwarded-For");
        if (xff != null && !xff.trim().isEmpty()) {
            // Primer valor de la cadena = cliente original.
            return xff.split(",")[0].trim();
        }
        return req.getRemoteAddr();
    }

    private void copy(InputStream is, OutputStream out) throws IOException {
        if (is == null) return;
        byte[] buffer = new byte[4096];
        int len;
        while ((len = is.read(buffer)) != -1) {
            out.write(buffer, 0, len);
        }
        out.flush();
    }

    /** Respuesta de error genérica en JSON (sin filtrar detalles internos). */
    private void sendError(HttpServletResponse resp, int status, String message)
            throws IOException {
        if (resp.isCommitted()) return;
        resp.setStatus(status);
        resp.setContentType("application/json; charset=UTF-8");
        resp.setHeader("X-Content-Type-Options", "nosniff");
        String safe = message.replace("\"", "'");
        resp.getWriter().write("{\"error\":\"" + safe + "\"}");
    }
}
