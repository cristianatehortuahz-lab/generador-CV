# -*- coding: utf-8 -*-
"""
verify_fidelity.py -- Scorecard de fidelidad para CVs generados.

Compara un PDF generado contra el PDF oficial de referencia, midiendo
con PyMuPDF: tamano de pagina, fuentes, tamanos, colores y estructura.

Uso:
  python scripts_dev/verify_fidelity.py [--format europass|harvard] [--generated PATH]
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fitz  # PyMuPDF


# Los PDF oficiales de referencia NO se incluyen en el paquete (contienen datos
# personales reales). Colócalos localmente y apunta a ellos con variables de
# entorno; si no están, el scorecard hace SKIP en lugar de fallar.
OFFICIAL_EUROPASS = os.environ.get(
    "OFFICIAL_EUROPASS",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "referencia_europass.pdf"),
)

OFFICIAL_HARVARD = os.environ.get(
    "OFFICIAL_HARVARD",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "referencia_harvard.pdf"),
)


def extract_spans(pdf_path, max_blocks=30):
    """Extract text spans from first page of a PDF."""
    doc = fitz.open(pdf_path)
    page = doc[0]
    page_size = (round(page.rect.width, 1), round(page.rect.height, 1))
    blocks = page.get_text("dict")["blocks"]
    spans = []
    for b in blocks[:max_blocks]:
        if "lines" not in b:
            continue
        for line in b["lines"]:
            for span in line["spans"]:
                spans.append({
                    "font": span["font"],
                    "size": round(span["size"], 1),
                    "color": "#%06X" % span.get("color", 0),
                    "text": span["text"].strip(),
                    "bold": "Bold" in span["font"] or "bold" in span["font"],
                    "x0": round(span["bbox"][0], 1),
                })
    doc.close()
    return page_size, spans


def find_span(spans, predicate):
    """Find first span matching predicate."""
    for s in spans:
        if predicate(s):
            return s
    return None


def check(label, expected, actual, results):
    ok = expected == actual
    status = "PASS" if ok else "FAIL"
    results.append((status, label, str(expected), str(actual)))
    return ok


def check_approx(label, expected, actual, tolerance, results):
    ok = abs(expected - actual) <= tolerance
    status = "PASS" if ok else "FAIL"
    results.append((status, label, str(expected), str(actual)))
    return ok


def _layout_metrics(pdf_path):
    """Métricas de layout de la página 1: tamaño, spans con bbox completo y la
    varianza de fin-de-línea de cada párrafo multilínea (para detectar justificado).
    """
    doc = fitz.open(pdf_path)
    page = doc[0]
    W, H = page.rect.width, page.rect.height
    spans, para_endvars = [], []
    for b in page.get_text("dict")["blocks"]:
        if "lines" not in b:
            continue
        for line in b["lines"]:
            for s in line["spans"]:
                if s["text"].strip():
                    spans.append({"text": s["text"].strip(),
                                  "size": round(s["size"], 1),
                                  "x0": s["bbox"][0], "x1": s["bbox"][2]})
        # Párrafo justificado: todas las líneas (menos la última) terminan casi en
        # el mismo x1. Ragged-right: los x1 varían. Medimos el rango de esos x1.
        if len(b["lines"]) >= 3:
            x1s = [max(s["bbox"][2] for s in l["spans"])
                   for l in b["lines"][:-1] if l["spans"]]
            if len(x1s) >= 2:
                para_endvars.append(max(x1s) - min(x1s))
    doc.close()
    return W, H, spans, para_endvars


def check_margins_alignment(pdf_path, exp_left_pt, tol, results,
                            dates_right=False):
    """Checks técnicos pedidos por el jefe: margen izquierdo, no-justificación y
    (Harvard) fechas alineadas a la derecha."""
    import re
    if not os.path.exists(pdf_path):
        return
    W, H, spans, para_endvars = _layout_metrics(pdf_path)
    body = [s for s in spans if s["size"] <= 11.5]
    if body:
        left = round(min(s["x0"] for s in body), 1)
        check_approx("Left margin (pt)", exp_left_pt, left, tol, results)
    if para_endvars:
        max_var = round(max(para_endvars), 1)
        ok = max_var > 20  # hay al menos un párrafo ragged-right => no justificado
        results.append(("PASS" if ok else "FAIL", "Body not justified",
                        ">20pt end-of-line var", "%.1fpt" % max_var))
    if dates_right:
        dspan = next((s for s in spans
                      if re.fullmatch(r'(19|20)\d{2}', s["text"])), None)
        if dspan:
            pct = 100 * dspan["x1"] / W
            ok = dspan["x1"] > W * 0.6
            results.append(("PASS" if ok else "FAIL", "Dates right-aligned",
                            "x1 > 60% width", "%.0f%%" % pct))


def _first_color(spans_full, predicate):
    for s in spans_full:
        if predicate(s):
            return s["color"]
    return None


def check_europass_fine(official_path, generated_path, results):
    """Checks de fidelidad fina (color/banda/logo) medidos contra el oficial."""
    def load(path):
        doc = fitz.open(path)
        pg = doc[0]
        W, H = pg.rect.width, pg.rect.height
        spans = []
        for b in pg.get_text("dict")["blocks"]:
            if "lines" not in b:
                continue
            for line in b["lines"]:
                for s in line["spans"]:
                    if s["text"].strip():
                        spans.append({"text": s["text"].strip(),
                                      "size": round(s["size"], 1),
                                      "color": "#%06X" % s.get("color", 0)})
        draws = pg.get_drawings()
        imgs = pg.get_images(full=True)
        doc.close()
        return W, H, spans, draws, imgs

    ow, oh, ospans, odraws, oimgs = load(official_path)
    gw, gh, gspans, gdraws, gimgs = load(generated_path)

    # Color del nombre (span >= 14pt) oficial vs generado
    oname = _first_color(ospans, lambda s: s["size"] >= 14)
    gname = _first_color(gspans, lambda s: s["size"] >= 14)
    if oname and gname:
        results.append(("PASS" if oname == gname else "FAIL", "Name color",
                        oname, gname))

    # Color de título de sección (MAYÚSCULAS con palabra clave)
    _kw = {"EDUCATION", "TRAINING", "WORK", "EXPERIENCE", "SKILLS", "PUBLICATIONS",
           "ABOUT", "RESEARCH", "PROJECTS"}
    def _title(s):
        return s["text"].isupper() and any(w in _kw for w in s["text"].split())
    otitle = _first_color(ospans, _title)
    gtitle = _first_color(gspans, _title)
    if otitle and gtitle:
        results.append(("PASS" if otitle == gtitle else "FAIL", "Section title color",
                        otitle, gtitle))

    # Banda superior full-bleed: rect de relleno con h>100 tocando bordes
    def band(draws, W):
        for d in draws:
            r = d["rect"]
            if d.get("fill") and r.height > 100 and r.x0 < 3 and r.width > W - 6:
                return "#%02X%02X%02X" % tuple(int(c * 255) for c in d["fill"])
        return None
    oband, gband = band(odraws, ow), band(gdraws, gw)
    if oband:
        ok = gband == oband
        results.append(("PASS" if ok else "FAIL", "Header band (full-bleed+color)",
                        oband, str(gband)))

    # Color de reglas horizontales (líneas finas anchas)
    def rule_color(draws, W):
        for d in draws:
            r = d["rect"]
            col = d.get("fill") or d.get("color")
            if col and r.width > W * 0.5 and r.height <= 2:
                return "#%02X%02X%02X" % tuple(int(c * 255) for c in col)
        return None
    orule, grule = rule_color(odraws, ow), rule_color(gdraws, gw)
    if orule and grule:
        results.append(("PASS" if orule == grule else "FAIL", "Rule color",
                        orule, grule))

    # Logo presente en el cuadrante superior derecho (oficial es vector; el
    # generado usa imagen — se acepta como equivalente si está bien ubicado)
    doc = fitz.open(generated_path)
    pg = doc[0]
    logo_ok = False
    for im in pg.get_images(full=True):
        for r in pg.get_image_rects(im[0]):
            if r.x1 > gw * 0.6 and r.y0 < gh * 0.3:
                logo_ok = True
    doc.close()
    results.append(("PASS" if logo_ok else "FAIL", "Logo arriba-derecha",
                    "presente", "sí" if logo_ok else "no"))


def verify_europass(generated_path):
    results = []
    if not os.path.exists(OFFICIAL_EUROPASS):
        print("SKIP: official Europass PDF not found at", OFFICIAL_EUROPASS)
        return results
    if not os.path.exists(generated_path):
        print("SKIP: generated PDF not found at", generated_path)
        return results

    off_size, off_spans = extract_spans(OFFICIAL_EUROPASS)
    gen_size, gen_spans = extract_spans(generated_path)

    # Page size (A4 = 595 x 842, tolerance for rounding)
    check_approx("Page width (A4)", off_size[0], gen_size[0], 1.0, results)
    check_approx("Page height (A4)", off_size[1], gen_size[1], 1.0, results)

    # Name span (first large text)
    off_name = find_span(off_spans, lambda s: s["size"] >= 14)
    gen_name = find_span(gen_spans, lambda s: s["size"] >= 14)
    if off_name and gen_name:
        check_approx("Name font size", off_name["size"], gen_name["size"], 0.5, results)
        # Font family check (Open Sans vs Arial fallback is acceptable)
        font_ok = ("Open Sans" in gen_name["font"] or "Arial" in gen_name["font"])
        results.append(("PASS" if font_ok else "FAIL", "Name font family",
                        "Open Sans or Arial", gen_name["font"]))

    # Section title (ALL CAPS text like "EDUCATION & TRAINING", "ABOUT ME", etc.)
    _section_names = {"EDUCATION", "TRAINING", "WORK", "EXPERIENCE", "SKILLS",
                      "PUBLICATIONS", "ABOUT", "RESEARCH", "PROJECTS"}
    def _is_section_title(s):
        words = s["text"].split()
        return s["text"].isupper() and len(s["text"]) > 3 and any(w in _section_names for w in words)
    off_title = find_span(off_spans, _is_section_title)
    gen_title = find_span(gen_spans, _is_section_title)
    if off_title and gen_title:
        check_approx("Section title size", off_title["size"], gen_title["size"], 0.5, results)

    # Meta line (first span with size <= 9.5 and date-like content)
    off_meta = find_span(off_spans, lambda s: s["size"] <= 9.5 and ("/" in s["text"] or "-" in s["text"]))
    gen_meta = find_span(gen_spans, lambda s: s["size"] <= 9.5 and len(s["text"]) > 3)
    if off_meta and gen_meta:
        check_approx("Meta line size", off_meta["size"], gen_meta["size"], 0.5, results)

    # Márgenes y alineación (norma Europass: A4, cuerpo a la izquierda, no justificado).
    # Izquierdo esperado 1.38 cm = 39.1 pt (medido del PDF oficial).
    check_margins_alignment(generated_path, 39.1, 4.0, results)

    # Fidelidad fina: colores, banda, reglas, logo (medido contra el oficial).
    check_europass_fine(OFFICIAL_EUROPASS, generated_path, results)

    return results


def verify_harvard(generated_path):
    results = []
    if not os.path.exists(OFFICIAL_HARVARD):
        print("INFO: official Harvard PDF not found at", OFFICIAL_HARVARD)
        print("      Checking generated PDF structure only.")

    if not os.path.exists(generated_path):
        print("SKIP: generated PDF not found at", generated_path)
        return results

    gen_size, gen_spans = extract_spans(generated_path)

    # Page size (Letter = 612 x 792)
    check_approx("Page width (Letter)", 612.0, gen_size[0], 2, results)
    check_approx("Page height (Letter)", 792.0, gen_size[1], 2, results)

    # Name should be first text span, Calibri ~11pt
    if gen_spans:
        name_span = gen_spans[0]
        check_approx("Name font size", 11.0, name_span["size"], 0.5, results)
        font_ok = "Calibri" in name_span["font"]
        results.append(("PASS" if font_ok else "FAIL", "Name font family",
                        "Calibri", name_span["font"]))

    # Check for centered section titles (look for x0 position > 100pt suggesting centering)
    title_spans = [s for s in gen_spans if s["text"].isupper() or
                   s["text"] in ("Education", "Experience", "Skills & Interests")]
    if title_spans:
        centered = any(s["x0"] > 100 for s in title_spans[:3])
        results.append(("PASS" if centered else "FAIL",
                        "Section titles centered", "x0 > 100pt",
                        "x0=%.1f" % title_spans[0]["x0"]))

    # Márgenes y alineación (norma Harvard: izquierda + fechas a la derecha, no
    # justificado). Izquierdo esperado 0.42 in = 30.2 pt.
    check_margins_alignment(generated_path, 30.2, 4.0, results, dates_right=True)

    return results


def print_scorecard(results, fmt_name):
    print("\n" + "=" * 70)
    print("  SCORECARD: %s" % fmt_name)
    print("=" * 70)
    passes = sum(1 for r in results if r[0] == "PASS")
    fails = sum(1 for r in results if r[0] == "FAIL")
    for status, label, expected, actual in results:
        marker = "OK" if status == "PASS" else "XX"
        print("  [%s] %-30s expected=%-20s actual=%s" % (marker, label, expected, actual))
    print("-" * 70)
    print("  %d/%d checks passed" % (passes, passes + fails))
    if fails:
        print("  ** %d FAILURES **" % fails)
    else:
        print("  ALL CHECKS PASSED")
    print("=" * 70)
    return fails == 0


def main():
    parser = argparse.ArgumentParser(description="CV fidelity verification")
    parser.add_argument("--format", choices=["europass", "harvard", "both"],
                        default="both")
    parser.add_argument("--generated-europass",
                        default=os.path.join(os.path.dirname(os.path.dirname(
                            os.path.abspath(__file__))),
                            "Nuevo_entorno_local", "formatos",
                            "EJEMPLO_generado_Europass.pdf"))
    parser.add_argument("--generated-harvard",
                        default=os.path.join(os.path.dirname(os.path.dirname(
                            os.path.abspath(__file__))),
                            "Nuevo_entorno_local", "formatos",
                            "EJEMPLO_generado_Harvard.pdf"))
    args = parser.parse_args()

    all_pass = True
    if args.format in ("europass", "both"):
        results = verify_europass(args.generated_europass)
        if results:
            if not print_scorecard(results, "Europass"):
                all_pass = False

    if args.format in ("harvard", "both"):
        results = verify_harvard(args.generated_harvard)
        if results:
            if not print_scorecard(results, "Harvard"):
                all_pass = False

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
