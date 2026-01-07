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

# inicio de entrada (cuando el CVAr viene bien seccionado)
_RE_ENTRY_START = re.compile(
    r"(?im)^\s*(?:[-•·*]|\&\#61485;)?\s*"
    r"("
    r"Diplomatura|Diplomado|Diploma|"
    r"Posdoctorado|Postdoctorado|"
    r"Doctorado|Doctor\s+en|Doctor\s+de\s+la\s+Universidad|Doctor(?:a)?\b|"
    r"Maestr[ií]a|Mag[ií]ster|Magister|"
    r"Especializaci[oó]n|Especialidad|Especialista|"
    r"Profesorado|Profesor\s+Universitario|Profesor\s+en|"
    r"Licenciatura|Licenciad[oa]\s+en|"
    r"T[eé]cnica\s+Universitaria|Tecnicatura|"
    r")\b",
    re.IGNORECASE
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
        if _RE_ENTRY_START.search(line) and buf:
            entries.append("\n".join(buf).strip())
            buf = [line]
        else:
            buf.append(line)

    if buf:
        entries.append("\n".join(buf).strip())

    # fallback si quedó todo pegado
    if len(entries) == 1 and len(entries[0]) > 1500:
        parts = re.split(
            r"(?i)(?=Diplomatura\b|Diplomado\b|Diploma\b|Posdoctorado\b|Postdoctorado\b|Doctorado\b|Doctor\s+en\b|Doctor\s+de\s+la\s+Universidad\b|Doctor(?:a)?\b|"
            r"Maestr[ií]a\b|Mag[ií]ster\b|Magister\b|Especializaci[oó]n\b|Especialidad\b|Especialista\b|Profesorado\b|Licenciad[oa]\s+en\b|Licenciatura\b|Tecnicatura\b|T[eé]cnica\s+Universitaria\b)",
            entries[0]
        )
        entries = [p.strip() for p in parts if p.strip()]

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
    Orden CRÍTICO:
    - Diplomatura primero
    - Luego doctorado/maestría/especialización/profesorado
    - "Profesor en ..." con ancla institucional => GRADO (caso típico CVAR)
    - GRADO: SOLO si parece un título (no "Lugar de trabajo", no "CVar ES...", no "Fecha de generación")
             y tiene ancla institucional.
    """
    head_raw = _first_line(entry)
    head = (head_raw or "").strip().lower()

    # --- Basura/ruido típico de CVAR (NO es formación) ---
    if re.search(r"^(lugar de trabajo|cvar\s+es\s+una\s+iniciativa|fecha de generación)\b", head, re.IGNORECASE):
        return "otro"
    if re.fullmatch(r"\d{1,3}", head):  # números de página sueltos
        return "otro"

    # 1) Diplomatura (aunque diga "Especialización en 'Diplomatura...'", NO es posgrado)
    if "diplomatura" in head or "diplomado" in head or "diploma" in head:
        return "diplomatura"

    # 2) Doctorado
    if re.search(r"\bdoctorad\b|\bdoctor\b", head, re.IGNORECASE):
        return "doctorado"

    # 3) Maestría / Magíster
    if re.search(r"\bmaestr[ií]a\b|\bmag[ií]ster\b|\bmagister\b", head, re.IGNORECASE):
        return "maestria"

    # 4) Especialización / Especialista / Especialidad
    # (esto no lo arregla si CONICET no pone FACULTAD/UNIVERSIDAD, pero tu decisión es NO tocar eso)
    if re.search(r"\bespecializaci[oó]n\b|\bespecialidad\b|\bespecialista\b", head, re.IGNORECASE):
        return "especializacion"

    # 5) Profesorado explícito (solo si dice "Profesorado" o "Profesor Universitario")
    if re.search(r"\bprofesorado\b|\bprofesor\s+universitario\b", head, re.IGNORECASE):
        return "profesorado"

    # 6) Caso CLAVE: "Profesor en ..." (en CVAR muchas veces ES un título de grado)
    if re.search(r"\bprofesor(a)?\s+en\b", head, re.IGNORECASE) and _has_institution_anchor(entry):
        return "grado"

    # 7) GRADO genérico: SOLO si parece un título (no frases administrativas)
    #    y tiene ancla institucional (FACULTAD/UNIVERSIDAD/INSTITUTO)
    #    Importante: acá NO buscamos profesión; funciona para Veterinario, Enfermero, Bromatólogo, Programador, etc.
    if _has_institution_anchor(entry):
        # si el head es demasiado "administrativo", lo descartamos
        if re.search(r"\b(ciencias|área|disciplinas|línea|especializado|investigador|lugar|trabajo)\b", head, re.IGNORECASE):
            return "otro"
        return "grado"

    return "otro"


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

            # =========================
            # OVERRIDE Formación académica y complementaria
            # =========================
            sec_l = section_name.strip().lower()
            if sec_l.startswith("formación académica") or sec_l.startswith("formacion academica"):
                il = item_name.lower()

                if "doctorad" in il or il.strip().startswith("doctor"):
                    count = form_counts["doctorado"]
                    evidence = form_evidence["doctorado"]
                elif "maestr" in il or "magister" in il or "magíster" in il:
                    count = form_counts["maestria"]
                    evidence = form_evidence["maestria"]
                elif "especializ" in il or "especialidad" in il or "especialista" in il:
                    count = form_counts["especializacion"]
                    evidence = form_evidence["especializacion"]
                elif "título de grado" in il or "titulo de grado" in il or il.strip() == "grado":
                    count = form_counts["grado"]
                    evidence = form_evidence["grado"]
                elif "profesorado" in il or "docencia universitaria" in il:
                    count = form_counts["profesorado"]
                    evidence = form_evidence["profesorado"]
                elif "posdoctor" in il or "posdoc" in il or "postdoc" in il:
                    count = form_counts["posdoc"]
                    evidence = form_evidence["posdoc"]
                elif "diplom" in il:
                    count = form_counts["diplomatura"]
                    evidence = form_evidence["diplomatura"]
                else:
                    # otros ítems (cursos/idiomas/etc.) siguen por regex
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
