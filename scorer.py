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


# ==========================================================
# Formación Académica (ESTRUCTURAL, universal)
# - NO usa listas de profesiones
# - Detecta títulos por anclas: FACULTAD/UNIVERSIDAD + "Año de finalización"
# - Diplomaturas NO se consideran títulos de grado/posgrado
# ==========================================================

_FORM_HEADERS = [
    r"\bFORMACI[ÓO]N\s+ACAD[ÉE]MICA\b",
    r"\bFORMACION\s+ACADEMICA\b",
    r"\bFORMACI[ÓO]N\s+ACAD[ÉE]MICA\s+Y\s+COMPLEMENTARIA\b",
    r"\bFORMACION\s+ACADEMICA\s+Y\s+COMPLEMENTARIA\b",
]

_NEXT_MARKERS = [
    r"\n\s*FORMACI[ÓO]N\s+DE\s+RECURSOS\s+HUMANOS\b",
    r"\n\s*RECURSOS\s+HUMANOS\b",
    r"\n\s*RRHH\b",
    r"\n\s*ANTECEDENTES\b",
    r"\n\s*PRODUCCI[ÓO]N\b",
    r"\n\s*PUBLICACIONES\b",
    r"\n\s*ACTIVIDADES\b",
    r"\n\s*EXPERIENCIA\b",
    r"\n\s*CARGOS\b",
    r"\n\s*CVar\b",
    r"\n\s*Fecha\s+de\s+generaci[oó]n\b",
]

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

# Ancla institucional
_RE_INSTIT_ANCHOR = re.compile(r"\b(FACULTAD|UNIVERSIDAD|INSTITUTO|SEDE|CONICET)\b", re.IGNORECASE)

# Líneas que NO pueden ser "título" (para el splitter)
_RE_NOT_TITLE_LINE = re.compile(
    r"^(?:FACULTAD|UNIVERSIDAD|INSTITUTO|SEDE|CONICET|A(?:ñ|n)o\s+de\s+finalizaci[oó]n|"
    r"Situaci[oó]n\s+del\s+nivel|Direcci[oó]n|Ejecutada\s+en|Financiada\s+por|"
    r"\d{2}/\d{4}\s*[-–]\s*(?:\d{2}/\d{4}|Actualidad)|\d{4}\s*[-–]\s*(?:\d{4}|Actualidad))\b",
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

def _is_title_line(line: str) -> bool:
    """
    Heurística: una línea "título" suele ser una frase (p.ej. "Farmacéutico", "Doctor en X")
    y NO empieza con FACULTAD / Año de finalización / fechas / etc.
    """
    if not line:
        return False
    l = line.strip()
    if not l:
        return False

    # limpiar bullets típicos
    l2 = re.sub(r"^\s*(?:[-•·*]|\&\#61485;|\u2022)\s*", "", l).strip()

    # si es claramente un campo, no es título
    if _RE_NOT_TITLE_LINE.search(l2):
        return False

    # si es demasiado "vacía" o muy corta
    if len(l2) < 3:
        return False

    # si empieza con mayúscula o letra (típico en títulos)
    return bool(re.match(r"^[A-ZÁÉÍÓÚÜÑa-záéíóúüñ]", l2))

def _split_entries_structural(block: str) -> List[str]:
    """
    Split estructural: comienza una entrada cuando aparece una línea que parece título.
    Esto permite contar cualquier profesión (sin listas).
    """
    if not block:
        return []
    lines = [ln.strip() for ln in block.splitlines()]
    lines = [ln for ln in lines if ln and ln.lower() != "null"]

    entries: List[str] = []
    buf: List[str] = []

    for line in lines:
        if _is_title_line(line):
            # si ya estamos acumulando, cerramos entrada anterior
            if buf:
                entries.append("\n".join(buf).strip())
                buf = [line]
            else:
                buf = [line]
        else:
            # continuidad
            if buf:
                buf.append(line)
            else:
                # si no empezó aún una entrada, ignoramos basura hasta primer título
                continue

    if buf:
        entries.append("\n".join(buf).strip())

    # filtro de entradas demasiado pobres (p.ej. una sola palabra suelta sin anclas)
    cleaned = []
    for e in entries:
        if len(e) < 10:
            continue
        cleaned.append(e)
    return cleaned

def _entry_completed(entry: str) -> bool:
    """
    Regla robusta:
    - Si hay evidencia explícita de finalización → ES FINALIZADO (aunque diga "Actualidad" en otra línea).
    - Si NO hay evidencia explícita y dice "Actualidad/En curso" → NO finalizado.
    """
    # ✅ Evidencias explícitas primero (ganan siempre)
    if _RE_FINISH.search(entry):
        return True
    if _RE_SITUACION_COMPLETO.search(entry):
        return True
    if _RE_COMPLETION_CUES.search(entry):
        return True

    # 🚫 Si solo dice Actualidad / En curso y no hay evidencia explícita → NO finalizado
    if _RE_IN_PROGRESS.search(entry):
        return False

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
    return bool(_RE_INSTIT_ANCHOR.search(entry))

def _classify_structural(entry: str) -> str:
    """
    Orden CRÍTICO:
    - Diplomatura primero (aunque diga "Especialización en 'Diplomatura...'", NO es especialización)
    - Luego doctorado/maestría/especialización/profesorado
    - Luego: si tiene ancla institucional y está completado => GRADO (cualquier profesión)
    """
    head = _first_line(entry).lower()

    if "diplomatura" in head or "diplomado" in head or "diploma" in head:
        return "diplomatura"

    if re.search(r"\bdoctorad\b|\bdoctor\b", head):
        return "doctorado"

    if re.search(r"\bmaestr[ií]a\b|\bmag[ií]ster\b|\bmagister\b", head):
        return "maestria"

    if re.search(r"\bespecializaci[oó]n\b|\bespecialidad\b|\bespecialista\b", head):
        return "especializacion"

    if re.search(r"\bprofesorado\b|\bprofesor universitario\b", head):
        return "profesorado"

    # Estructural: cualquier otro título finalizado con FACULTAD/UNIVERSIDAD => grado
    if _has_institution_anchor(entry):
        return "grado"

    return "otro"

def _count_formacion(full_text: str) -> Tuple[Dict[str, int], Dict[str, str]]:
    """
    Devuelve:
    - counts por tipo (doctorado, maestria, especializacion, grado, profesorado)
    - evidence por tipo (1ra evidencia para mostrar)
    NOTA: posdoc NO se cuenta en Formación (se maneja como Estancia en otra sección).
    NOTA: diplomaturas NO cuentan como títulos; se puntúan por ítems de Cursos/Diplomaturas del criteria.
    """
    block = _extract_formacion_block(full_text)
    entries = _split_entries_structural(block)

    counts = {
        "doctorado": 0,
        "maestria": 0,
        "especializacion": 0,
        "grado": 0,
        "profesorado": 0,
    }
    evidence = {k: "" for k in counts.keys()}

    seen = set()

    for e in entries:
        # NO puntuar posdoctorado desde Formación
        if re.search(r"\b(posdoctor|postdoctor)\b", e, re.IGNORECASE):
            continue

        # diplomaturas NO son títulos (se van por Cursos/Diplomaturas)
        if re.search(r"\b(diplomatura|diplomado|diploma)\b", _first_line(e), re.IGNORECASE):
            continue

        if not _entry_completed(e):
            continue

        tipo = _classify_structural(e)
        if tipo not in counts:
            continue

        title = _first_line(e)
        fin = _finish_token(e)
        inst = "INST" if _has_institution_anchor(e) else ""

        key = (tipo, _norm_key(title), _norm_key(inst), _norm_key(fin))
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
):
    text = _norm_spaces(text)

    sections = criteria.get("sections", {})
    categorias = criteria.get("categorias", {})

    # ✅ override SOLO para Formación (estructural universal)
    form_counts, form_evidence = _count_formacion(text)

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

            count: int = 0
            evidence: str = ""

            # =========================
            # OVERRIDE Formación académica y complementaria
            # =========================
            if section_name.strip().lower().startswith("formación académica") or section_name.strip().lower().startswith("formacion academica"):
                il = item_name.lower()

                if "doctorad" in il:
                    count = form_counts.get("doctorado", 0)
                    evidence = form_evidence.get("doctorado", "")
                elif "maestr" in il or "magister" in il or "magíster" in il:
                    count = form_counts.get("maestria", 0)
                    evidence = form_evidence.get("maestria", "")
                elif "especializ" in il or "especialista" in il or "especialidad" in il:
                    count = form_counts.get("especializacion", 0)
                    evidence = form_evidence.get("especializacion", "")
                elif "título de grado" in il or "titulo de grado" in il or il.strip() == "grado":
                    count = form_counts.get("grado", 0)
                    evidence = form_evidence.get("grado", "")
                elif "profesorado" in il or "docencia universitaria" in il:
                    count = form_counts.get("profesorado", 0)
                    evidence = form_evidence.get("profesorado", "")
                else:
                    # cursos/idiomas/becas siguen por regex
                    pass

            # =========================
            # DEFAULT: regex global
            # =========================
            if evidence == "" and pattern:
                try:
                    rx = _compile(pattern)
                    matches = list(rx.finditer(text))
                    count = len(matches)
                    if matches:
                        evidence = _pick_evidence(text, matches[0], max_chars=evidence_max_chars)
                except re.error:
                    count = 0
                    evidence = ""

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
