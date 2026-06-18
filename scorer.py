import json
import re
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple


# =========================
# Results struct
# =========================
@dataclass
class ItemResult:
    section: str
    item: str
    pattern: str
    count: int
    unit_points: float
    raw_points: float
    capped_item_points: float
    item_max_points: float
    evidence: str


# =========================
# IO
# =========================
def load_criteria(path: str = "criteria.json") -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# =========================
# Small helpers
# =========================
def _compile(pattern: str) -> re.Pattern:
    return re.compile(pattern, flags=re.IGNORECASE | re.UNICODE)


def _pick_evidence(text: str, m: re.Match, max_chars: int = 260) -> str:
    start = max(0, m.start() - 80)
    end = min(len(text), m.end() + 120)
    snippet = text[start:end]
    snippet = re.sub(r"\s+", " ", snippet).strip()
    return snippet[:max_chars]


def _norm_spaces(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\u00A0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _norm_key(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[\"'`´]", "", s)
    return s


_RE_CVAR_BOILERPLATE = re.compile(
    r"(?:CVar\s+ES\s+UNA\s+INICIATIVA|MINISTERIO\s+DE\s+CIENCIA|"
    r"Fecha\s+de\s+generaci[oó]n|TECNOLOG[IÍ]A\s+E\s+INNOVACI[ÓO]N)",
    re.IGNORECASE,
)


def _line_at_pos(text: str, pos: int) -> str:
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    if end < 0:
        end = len(text)
    return text[start:end]


def _is_valid_activity_match(text: str, m: re.Match) -> bool:
    """Descarta matches anclados en pies de página del CVAr o regex multilínea demasiado anchos."""
    line = _line_at_pos(text, m.start())
    if re.search(
        r"CVar\s+ES\s+UNA\s+INICIATIVA|Fecha\s+de\s+generaci|MINISTERIO\s+DE\s+CIENCIA",
        line,
        re.IGNORECASE,
    ):
        return False

    if m.end() - m.start() > 900:
        return False

    head = text[m.start() : m.start() + 240]
    if m.end() - m.start() > 500 and re.search(
        r"CONSULTOR\s+DE\s+EMPRESAS|PROGRAMA\s+DE\s+ACTUALIZACION",
        head,
        re.IGNORECASE,
    ):
        return False

    snippet = _pick_evidence(text, m, max_chars=320)
    if _RE_CVAR_BOILERPLATE.search(snippet):
        if re.search(
            r"\b(?:20\d{2}|19\d{2})\s*[-–]\s*(?:20\d{2}|19\d{2}|Actualidad)\b",
            snippet,
        ):
            return True
        if re.search(
            r"\b(?:Evaluaci[oó]n\s+de|Rol:\s|Investigador/a:|Tesista:|"
            r"Direcci[oó]n\s+de|Jurado|Revisor)\b",
            snippet,
            re.IGNORECASE,
        ):
            return True
        return False
    return True


def _tighten_dated_activity_pattern(pattern: str) -> str:
    """
    En patrones (?ims)^ de antecedentes datados, el .*? inicial puede saltar de sección.
    """
    if not pattern.startswith("(?ims)^"):
        return pattern
    return re.sub(r"\?\.\*\?", "?[^\n]{0,260}?", pattern, count=1)


def _regex_match_count(text: str, pattern: str, evidence_max_chars: int = 260) -> Tuple[int, str]:
    if not pattern:
        return 0, ""
    pattern = _tighten_dated_activity_pattern(pattern)
    try:
        rx = _compile(pattern)
    except re.error:
        return 0, ""
    matches = [m for m in rx.finditer(text) if _is_valid_activity_match(text, m)]
    if not matches:
        return 0, ""
    return len(matches), _pick_evidence(text, matches[0], max_chars=evidence_max_chars)


# ==========================================================
# Formación Académica: extracción + parse por entradas
# (evita regex “greedy” que se come 3 doctorados como 1)
# ==========================================================

_FORM_HEADERS = [
    r"\bFORMACI[ÓO]N\s+ACAD[ÉE]MICA\b",
    r"\bFORMACION\s+ACADEMICA\b",
    r"\bFORMACI[ÓO]N\s+ACAD[ÉE]MICA\s+Y\s+COMPLEMENTARIA\b",
    r"\bFORMACION\s+ACADEMICA\s+Y\s+COMPLEMENTARIA\b",
]

_NEXT_MARKERS = [
    r"\n\s*FORMACI[ÓO]N\s+COMPLEMENTARIA\b",
    r"\n\s*FORMACION\s+COMPLEMENTARIA\b",
    r"\n\s*FORMACI[ÓO]N\s+DE\s+RECURSOS\s+HUMANOS\b",
    r"\n\s*RECURSOS\s+HUMANOS\b",
    r"\n\s*RRHH\b",
    r"\n\s*ANTECEDENTES\b",
    r"\n\s*PRODUCCI[ÓO]N\b",
    r"\n\s*PUBLICACIONES\b",
    r"\n\s*ACTIVIDADES\b",
    r"\n\s*EXPERIENCIA\b",
    r"\n\s*CARGOS\b",
    r"\n\s*CURSOS\s+Y\s+CAPACITACIONES\b",
    r"\n\s*CURSOS\s+E\s+CAPACITACIONES\b",
    r"\n\s*CVar\b",
    r"\n\s*Fecha\s+de\s+generaci[oó]n\b",
]

# inicio de entrada (cuando el CVAr viene bien seccionado)
_RE_ENTRY_START = re.compile(
    r"(?im)^\s*(?:[-•·*]|\&\#61485;)?\s*"
    r"("
    r"Diplomatura|Diplomado|Diploma|"
    r"Posdoctorado|Postdoctorado|"
    r"Doctorado|Doctor\s+en|Doctor\s+de\s+la\s+Universidad|Doctor(?:a)?\b|"
    r"Maestr[ií]a|Mag[ií]ster|Magister|"
    r"Especializaci[oó]n|Especialidad|Especialista|"
    r"Profesorado|Profesor\s+Superior|Profesor\s+Universitario|Profesor\s+en|"
    r"Abogad[oa]s?|"
    r"Licenciatura|Licenciad[oa](?:\s+en)?|"
    r"Ingenier[oa]s?|Contador(?:a)?s?|Arquitect[oa]s?|"
    r"Enfermer[ií]a|Enfermer[oa]s?|"
    r"T[eé]cnica\s+Universitaria|Tecnicatura"
    r")\b",
    re.IGNORECASE
)

_RE_ENTRY_HEADER_LINE = re.compile(
    r"(?im)^\s*(?:[-•·*]|\&\#61485;)?\s*"
    r"(?:"
    r"Diplomatura|Diplomado|Diploma|"
    r"Posdoctorado|Postdoctorado|"
    r"Doctorado|Doctor\s+en|Doctor\s+de\s+la\s+Universidad|Doctor(?:a)?\b|"
    r"Maestr[ií]a|Mag[ií]ster|Magister|"
    r"Especializaci[oó]n|Especialidad|Especialista|"
    r"Profesorado|Profesor\s+Superior|Profesor\s+Universitario|Profesor\s+en|"
    r"Abogad[oa]s?|"
    r"Licenciatura|Licenciad[oa](?:\s+en)?|"
    r"Ingenier[oa]s?|Contador(?:a)?s?|Arquitect[oa]s?|"
    r"Enfermer[ií]a|Enfermer[oa]s?|"
    r"T[eé]cnica\s+Universitaria|Tecnicatura"
    r")\b",
    re.IGNORECASE,
)

_RE_IN_PROGRESS = re.compile(
    r"\b(Actualidad|En\s+curso|Cursando|Actualmente|Vigente|Hasta\s+la\s+actualidad|A\s+la\s+fecha)\b",
    re.IGNORECASE
)

_RE_FINISH = re.compile(
    r"A(?:ñ|n)o\s+de\s+(?:finalizaci[oó]n|obtenci[oó]n|graduaci[oó]n)\s*[:\-–]?\s*(?:\d{2}/\d{4}|19\d{2}|20\d{2})",
    re.IGNORECASE
)

_RE_SITUACION_COMPLETO = re.compile(
    r"Situaci[oó]n\s+del\s+nivel\s*[:\-–]?\s*Completo",
    re.IGNORECASE
)

_RE_COMPLETION_CUES = re.compile(
    r"\b(finalizad[oa]|egresad[oa]|graduad[oa]|t[ií]tulo\s+obtenido|t[ií]tulo\s+otorgado|defendid[oa]|complet(?:o|ada))\b",
    re.IGNORECASE
)

# contexto que NO queremos que dispare posdoc (becas/rrhh)
_RE_BECARIO_CONTEXT = re.compile(
    r"\b(becari[oa]s?|beca|direcci[oó]n|co[- ]?direcci[oó]n|tesista|investigador/a|investigador)\b",
    re.IGNORECASE
)

# anclas institucionales típicas (para GRADO genérico)
_RE_INST_ANCHOR = re.compile(
    r"\b(FACULTAD|UNIVERSIDAD|INSTITUTO|ESCUELA|DEPARTAMENTO|CENTRO|COLEGIO)\b",
    re.IGNORECASE
)


def _extract_formacion_block(full_text: str) -> str:
    txt = _norm_spaces(full_text)
    start = None
    for h in _FORM_HEADERS:
        m = re.search(h, txt, flags=re.IGNORECASE)
        if m:
            start = m.end()
            break
    if start is None:
        return ""

    tail = txt[start:]
    end = len(tail)
    for mk in _NEXT_MARKERS:
        m2 = re.search(mk, tail, flags=re.IGNORECASE)
        if m2:
            end = min(end, m2.start())
    return tail[:end].strip()


def _split_entries(block: str) -> List[str]:
    if not block:
        return []

    # normalizamos líneas y eliminamos basura
    lines = [l.strip() for l in block.splitlines()]
    lines = [l for l in lines if l and l.lower() != "null"]

    entries: List[str] = []
    buf: List[str] = []

    for line in lines:
        if _RE_ENTRY_HEADER_LINE.search(line) and buf:
            entries.append("\n".join(buf).strip())
            buf = [line]
        else:
            buf.append(line)

    if buf:
        entries.append("\n".join(buf).strip())

    # fallback si quedó todo pegado (títulos sin viñeta, p. ej. ABOGADO / PROFESOR SUPERIOR)
    if len(entries) <= 1:
        blob = entries[0] if entries else block
        parts = re.split(
            r"(?im)(?=Diplomatura\b|Diplomado\b|Diploma\b|Posdoctorado\b|Postdoctorado\b|"
            r"Doctorado\b|Doctor\s+en\b|Doctor\s+de\s+la\s+Universidad\b|Doctor(?:a)?\b|"
            r"Maestr[ií]a\b|Mag[ií]ster\b|Magister\b|"
            r"Especializaci[oó]n\b|Especialidad\b|Especialista\b|"
            r"Profesorado\b|Profesor\s+Superior\b|Profesor\s+Universitario\b|"
            r"Abogad[oa]s?\b|Licenciad[oa](?:\s+en)?\b|Licenciatura\b|"
            r"Ingenier[oa]s?\b|Contador(?:a)?s?\b|Arquitect[oa]s?\b|"
            r"Tecnicatura\b|T[eé]cnica\s+Universitaria\b)",
            blob,
        )
        split_entries = [p.strip() for p in parts if p.strip()]
        if len(split_entries) > len(entries):
            entries = split_entries

    return entries


def _entry_completed(entry: str) -> bool:
    if _RE_IN_PROGRESS.search(entry):
        return False
    if _RE_FINISH.search(entry):
        return True
    if _RE_SITUACION_COMPLETO.search(entry):
        return True
    if _RE_COMPLETION_CUES.search(entry):
        return True
    return False


def _finish_token(entry: str) -> str:
    m = _RE_FINISH.search(entry)
    if m:
        return re.sub(r"\s+", "", m.group(0))
    if _RE_SITUACION_COMPLETO.search(entry):
        return "COMPLETO"
    if _RE_COMPLETION_CUES.search(entry):
        return "FINALIZADO"
    return ""


def _first_line(entry: str) -> str:
    for l in entry.splitlines():
        l = l.strip()
        if l and l.lower() != "null":
            return l
    return ""


def _has_institution_anchor(entry: str) -> bool:
    return bool(_RE_INST_ANCHOR.search(entry))


def _classify_structural(entry: str) -> str:
    """
    Clasificación estructural CORRECTA para CVAR (Argentina).

    Reglas:
    - Diplomaturas siempre primero (no son grado ni posgrado)
    - Doctorado / Maestría / Especialización explícitos
    - Profesor en Enseñanza Media y Superior = TÍTULO DE GRADO
    - Profesorado SOLO si dice explícitamente 'Profesorado'
    - Grado SOLO si hay FACULTAD/UNIVERSIDAD + finalización
    """

    head = _first_line(entry).lower()

    # 1️⃣ Diplomaturas (siempre excluidas de grado/posgrado)
    if re.search(r"\bdiplomatur|\bdiplomad|\bdiploma\b", head):
        return "diplomatura"

    # 2️⃣ Doctorado
    if re.search(r"\bdoctorad|\bdoctor\b", head):
        return "doctorado"

    # 3️⃣ Maestría
    if re.search(r"\bmaestr[ií]a|\bmag[ií]ster|\bmagister\b", head):
        return "maestria"

    # 4️⃣ Especialización
    if re.search(r"\bespecializaci[oó]n|\bespecialista\b", head):
        return "especializacion"

    # 5️⃣ Profesor superior / profesorado universitario
    if re.search(r"\bprofesor\s+superior\b", head):
        return "profesorado"

    # 6️⃣ PROFESOR EN ENSEÑANZA MEDIA Y SUPERIOR = GRADO
    if re.search(r"\bprofesor\s+en\s+enseñanza\s+media\b", head):
        return "grado"

    # 7️⃣ Profesorado (carreras específicas)
    if re.search(r"\bprofesorado\b", head):
        return "profesorado"

    # 8️⃣ Títulos profesionales de grado (Abogado, Licenciado, Enfermería, etc.)
    if re.search(
        r"\b(abogad[oa]s?|licenciad[oa]s?|ingenier[oa]s?|contador(?:a)?s?|arquitect[oa]s?|"
        r"bioqu[ií]mic[oa]s?|farmac[eé]utic[oa]s?|m[eé]dic[oa]s?|enfermer[ií]a|enfermer[oa]s?)\b",
        head,
    ):
        return "grado"

    # 9️⃣ Grado estructural (cualquier carrera con ancla institucional)
    if _has_institution_anchor(entry) and _entry_completed(entry):
        return "grado"

    return "otro"


# ==========================================================
# Producción: artículos en bloque PUBLICACIONES
# ==========================================================

_PUB_BLOCK_END = [
    r"\n\s*OTROS\s+ANTECEDENTES\b",
    r"\n\s*FORMACI[ÓO]N\s+DE\s+RECURSOS\s+HUMANOS\b",
    r"\n\s*ANTECEDENTES\s+EN\s+CYT\b",
    r"\n\s*ANTECEDENTES\b",
]

def _extract_publicaciones_block(full_text: str) -> str:
    txt = _norm_spaces(full_text)
    m = re.search(r"\bPUBLICACIONES\b", txt, flags=re.IGNORECASE)
    if not m:
        return ""
    tail = txt[m.start():]
    end = len(tail)
    for mk in _PUB_BLOCK_END:
        m2 = re.search(mk, tail, flags=re.IGNORECASE)
        if m2:
            end = min(end, m2.start())
    return tail[:end].strip()


def _merge_publicacion_lines(block: str) -> List[str]:
    """Agrupa líneas del bloque PUBLICACIONES en citas (soporta título en varias líneas)."""
    rows: List[str] = []
    buf = ""
    for raw in block.splitlines():
        line = raw.strip()
        if not line or line.lower() == "null":
            continue
        if re.match(r"^(PUBLICACIONES|Art[ií]culos)\b", line, re.IGNORECASE):
            continue
        if re.match(r"^(CVar\b|Fecha de generaci)", line, re.IGNORECASE):
            continue
        if re.match(r"^L[ÓO]PEZ\s+MORENO", line, re.IGNORECASE):
            continue
        if re.match(r"^\d+\s*$", line):
            continue

        starts_new = bool(
            re.match(
                r"^[A-ZÁÉÍÓÚÜÑ][^\n]{0,120}?\.\s*\"",
                line,
            )
            or re.match(r"^\.\s*\"", line)
        )
        if starts_new and buf:
            rows.append(buf.strip())
            buf = line
        else:
            buf = f"{buf} {line}".strip() if buf else line

        if buf and (
            re.search(r"\(\s*(?:19|20)\d{2}\s*\)", buf)
            or re.search(r":\s*\(\s*(?:19|20)\d{2}\s*\)", buf)
            or re.search(r"Traducci[oó]n\s+publicada\s+en\s+revista", buf, re.IGNORECASE)
        ):
            rows.append(buf.strip())
            buf = ""

    if buf.strip():
        rows.append(buf.strip())
    return rows


def _count_articulos_revistas(full_text: str) -> Tuple[int, str]:
    block = _extract_publicaciones_block(full_text)
    if not block:
        return 0, ""

    seen = set()
    evidence = ""
    count = 0

    for row in _merge_publicacion_lines(block):
        snippet = re.sub(r"\s+", " ", row).strip()
        if '"' not in snippet:
            continue
        if re.search(r"\bTesis\s+de\b", snippet, re.IGNORECASE):
            continue
        if re.search(r"En:\s*\(ed\.?\)", snippet, re.IGNORECASE):
            continue
        if re.match(r'^\.\s*"', snippet):
            continue
        if re.search(r"Traducci[oó]n\s+publicada\s+en\s+libro", snippet, re.IGNORECASE):
            continue
        if re.search(r"Traducci[oó]n\s+publicada", snippet, re.IGNORECASE):
            if not re.search(r"Traducci[oó]n\s+publicada\s+en\s+revista", snippet, re.IGNORECASE):
                continue
        elif not (
            re.search(r"(?:19|20)\d{2}", snippet)
            and re.search(r'\.\s*"', snippet)
        ):
            continue

        key = _norm_key(snippet[:180])
        if key in seen:
            continue
        seen.add(key)
        count += 1
        if not evidence:
            evidence = snippet[:260]

    return count, evidence


def _count_capitulos_libro(full_text: str) -> Tuple[int, str]:
    block = _extract_publicaciones_block(full_text)
    if not block:
        return 0, ""

    count = 0
    evidence = ""
    for row in _merge_publicacion_lines(block):
        snippet = re.sub(r"\s+", " ", row).strip()
        if not (
            re.search(r"En:\s*\(ed\.?\)", snippet, re.IGNORECASE)
            or re.search(r"\bCap[ií]tulo\b", snippet, re.IGNORECASE)
        ):
            continue
        count += 1
        if not evidence:
            evidence = snippet[:260]
    return count, evidence


def _count_formacion(full_text: str) -> Tuple[Dict[str, int], Dict[str, str]]:
    """
    Devuelve:
    - counts por tipo (doctorado, maestria, especializacion, grado, profesorado, posdoc, diplomatura)
    - evidence por tipo (1ra evidencia para mostrar)
    """
    block = _extract_formacion_block(full_text)
    entries = _split_entries(block)

    counts = {
        "doctorado": 0,
        "maestria": 0,
        "especializacion": 0,
        "grado": 0,
        "profesorado": 0,
        "posdoc": 0,
        "diplomatura": 0,
    }
    evidence = {k: "" for k in counts.keys()}

    seen = set()

    for e in entries:
        # posdoc se detecta aparte por texto (no por “grado” genérico)
        if re.search(r"\b(posdoctorado|postdoctorado)\b", e, re.IGNORECASE):
            tipo = "posdoc"
        else:
            tipo = _classify_structural(e)

        if tipo not in counts:
            continue

        # posdoc: evitar falsas detecciones por contexto beca/rrhh
        if tipo == "posdoc" and _RE_BECARIO_CONTEXT.search(e):
            continue

        if not _entry_completed(e):
            continue

        title = _first_line(e)
        fin = _finish_token(e)
        key = (tipo, _norm_key(title), _norm_key(fin))
        if key in seen:
            continue
        seen.add(key)

        counts[tipo] += 1
        if not evidence[tipo]:
            evidence[tipo] = re.sub(r"\s+", " ", e.strip())[:260]

    return counts, evidence


# ==========================================================
# SCORE
# ==========================================================
def score_text(
    text: str,
    criteria: Dict[str, Any],
    evidence_max_chars: int = 260
) -> Tuple[List[ItemResult], Dict[str, float], float, str, Dict[str, Any]]:
    text = _norm_spaces(text)

    sections = criteria.get("sections", {})
    categorias = criteria.get("categorias", {})

    # override SOLO para Formación
    form_counts, form_evidence = _count_formacion(text)
    articulos_count, articulos_evidence = _count_articulos_revistas(text)
    capitulos_count, capitulos_evidence = _count_capitulos_libro(text)

    results: List[ItemResult] = []
    section_totals: Dict[str, float] = {}
    total_points = 0.0

    for section_name, sec in sections.items():
        sec_max = float(sec.get("max_points", 10**9))
        sec_sum = 0.0

        items = sec.get("items", {})
        for item_name, item in items.items():
            pattern = item.get("pattern", "")
            unit_points = float(item.get("unit_points", 0))
            item_max = float(item.get("max_points", 0))

            count = 0
            evidence = ""
            il = item_name.lower()
            sec_l = section_name.strip().lower()
            forma_struct_locked = False  # titulos grandes: solo parser estructural (sin regex de respaldo)
            pub_struct_locked = False

            # =========================
            # OVERRIDE Formación académica y complementaria
            # =========================
            if sec_l.startswith("formación académica") or sec_l.startswith("formacion academica"):

                # Antes que Doctorado: "postdoctorado..." contiene la subcadena "doctorad".
                if il.strip().startswith("postdoctorado"):
                    count = form_counts["posdoc"]
                    evidence = form_evidence["posdoc"]
                    forma_struct_locked = True
                elif "doctorad" in il or il.strip().startswith("doctor"):
                    count = form_counts["doctorado"]
                    evidence = form_evidence["doctorado"]
                    forma_struct_locked = True
                elif "maestr" in il or "magister" in il or "magíster" in il:
                    count = form_counts["maestria"]
                    evidence = form_evidence["maestria"]
                    forma_struct_locked = True
                elif re.match(r"(?i)^especializ", item_name.strip()) or re.match(
                    r"(?i)^especialidad", item_name.strip()
                ):
                    count = form_counts["especializacion"]
                    evidence = form_evidence["especializacion"]
                    forma_struct_locked = True
                elif "título de grado" in il or "titulo de grado" in il or il.strip() == "grado":
                    count = form_counts["grado"]
                    evidence = form_evidence["grado"]
                    forma_struct_locked = True
                elif "profesorado" in il or "docencia universitaria" in il:
                    count = form_counts["profesorado"]
                    evidence = form_evidence["profesorado"]
                    forma_struct_locked = True
                # Solo el fallback "sin horas" usa Diplomatura estructural; "con horas" sigue por regex
                elif "sin horas" in il and "diplom" in il:
                    count = form_counts["diplomatura"]
                    evidence = form_evidence["diplomatura"]
                    forma_struct_locked = True
                else:
                    # otros ítems (cursos con horas, becas línea CONICET, idiomas…) siguen por regex
                    pass

            # =========================
            # OVERRIDE Producción científica (artículos)
            # =========================
            if sec_l.startswith("producción científica") or sec_l.startswith("produccion cientifica"):
                if il.startswith("artículos en revistas") or il.startswith("articulos en revistas"):
                    count = articulos_count
                    evidence = articulos_evidence
                    pub_struct_locked = True
                elif il.startswith("capítulos de libro") or il.startswith("capitulos de libro"):
                    count = capitulos_count
                    evidence = capitulos_evidence
                    pub_struct_locked = True

            # =========================
            # DEFAULT: regex global
            # =========================
            if not forma_struct_locked and not pub_struct_locked and pattern:
                count, evidence = _regex_match_count(
                    text, pattern, evidence_max_chars=evidence_max_chars
                )

            raw_points = count * unit_points
            capped_item_points = min(raw_points, item_max) if item_max >= 0 else raw_points

            results.append(
                ItemResult(
                    section=section_name,
                    item=item_name,
                    pattern=pattern,
                    count=count,
                    unit_points=unit_points,
                    raw_points=raw_points,
                    capped_item_points=capped_item_points,
                    item_max_points=item_max,
                    evidence=evidence[:evidence_max_chars] if evidence else "",
                )
            )
            sec_sum += capped_item_points

        sec_sum = min(sec_sum, sec_max)
        section_totals[section_name] = sec_sum
        total_points += sec_sum

    # categoría por umbral
    category = "VI"
    if categorias:
        ordered = sorted(
            categorias.items(),
            key=lambda kv: float(kv[1].get("min_points", 0)),
            reverse=True
        )
        for cat, info in ordered:
            if total_points >= float(info.get("min_points", 0)):
                category = cat
                break

    return results, section_totals, total_points, category, categorias
