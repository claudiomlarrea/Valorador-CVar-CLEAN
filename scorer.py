import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple, Optional


# =========================
# Result model
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
# Criteria loader
# =========================
def load_criteria(path: str = "criteria.json") -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# =========================
# Text helpers
# =========================
def _strip_accents(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def _normalize_spaces(s: str) -> str:
    s = s.replace("\u00A0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _compile(pattern: str) -> Optional[re.Pattern]:
    try:
        return re.compile(pattern)
    except re.error:
        return None


def _pick_evidence(text: str, m: re.Match, max_chars: int = 260) -> str:
    start = max(0, m.start() - 80)
    end = min(len(text), m.end() + 120)
    snippet = text[start:end]
    snippet = re.sub(r"\s+", " ", snippet).strip()
    return snippet[:max_chars]


# ==========================================================
# Formación: recorte + parseo por entradas (ANTI-REGEX-LARGO)
# ==========================================================
FORMACION_HEADERS = [
    r"\bFORMACI[ÓO]N\s+ACAD[ÉE]MICA\b",
    r"\bFORMACI[ÓO]N\s+ACAD[ÉE]MICA\s+Y\s+COMPLEMENTARIA\b",
    r"\bFORMACION\s+ACADEMICA\b",
    r"\bFORMACION\s+ACADEMICA\s+Y\s+COMPLEMENTARIA\b",
]

# Marcadores de siguiente sección (cortes duros)
NEXT_SECTION_MARKERS = [
    r"\n\s*FORMACI[ÓO]N\s+DE\s+RECURSOS\s+HUMANOS\b",
    r"\n\s*RECURSOS\s+HUMANOS\b",
    r"\n\s*RRHH\b",
    r"\n\s*PUBLICACIONES\b",
    r"\n\s*PRODUCCI[ÓO]N\b",
    r"\n\s*ANTECEDENTES\b",
    r"\n\s*ACTIVIDADES\b",
    r"\n\s*EXPERIENCIA\b",
    r"\n\s*CARGOS\b",
    r"\n\s*CVar\b",
    r"\n\s*Fecha\s+de\s+generaci[oó]n\b",
]

# Si aparecen, NO cortar automáticamente porque a veces están dentro de la lista de formación
SOFT_MARKERS = [
    r"\n\s*FORMACI[ÓO]N\s+COMPLEMENTARIA\b",
    r"\n\s*CURSOS\b",
    r"\n\s*IDIOMAS\b",
]

RE_IN_PROGRESS = re.compile(
    r"\b(Actualidad|En\s+curso|Cursando|Actualmente|Vigente|En\s+desarrollo|Hasta\s+la\s+actualidad|A\s+la\s+fecha)\b",
    re.IGNORECASE
)

RE_FINISH_YEAR = re.compile(
    r"A(?:ñ|n)o\s+de\s+(?:finalizaci[oó]n|obtenci[oó]n|graduaci[oó]n)\s*[:\-–]?\s*([0-3]?\d\s*[/\-]\s*\d{4}|\d{4})",
    re.IGNORECASE
)

RE_SITUACION_COMPLETO = re.compile(
    r"Situaci[oó]n\s+del\s+nivel\s*[:\-–]?\s*Completo",
    re.IGNORECASE
)

RE_COMPLETION_CUES = re.compile(
    r"\b(finalizad[oa]|egresad[oa]|graduad[oa]|t[ií]tulo\s+obtenido|t[ií]tulo\s+otorgado|complet(?:o|ada))\b",
    re.IGNORECASE
)

# Inicio de entrada (incluye variantes frecuentes)
RE_ENTRY_START = re.compile(
    r"^\s*(?:[-•·*]\s*)?"
    r"(Doctorado|Doctor\s+en|Doctor\s+de\s+la\s+Universidad|"
    r"Maestr[ií]a|Mag[ií]ster|Magister|"
    r"Especializaci[oó]n|Especialista|"
    r"Posdoctorado|Postdoctorado|Posdoctoral|Postdoctoral|"
    r"Profesorado|Profesor\s+Universitario|Profesor\s+en|"
    r"Licenciatura|Licenciad[oa]s?|"
    r"Tecnicatura|T[eé]cnica\s+Universitaria|"
    r"Contador(?:a)?|Contadur[ií]a|"
    r"Abogad[oa]|Ingenier[oa]?|Bioqu[ií]mic[oa]?|M[eé]dic[oa]?|Farmac[eé]utic[oa]?|Arquitect[oa]?|Odont[oó]log[oa]?)\b",
    re.IGNORECASE
)

# Contextos que NO son formación (evitar confusiones)
RE_BECARIO_CONTEXT = re.compile(
    r"\b(becari[oa]s?|beca|direcci[oó]n|co[- ]?direcci[oó]n|tesista|investigador/a|investigador)\b",
    re.IGNORECASE
)

def _extract_formacion_block(full_text: str) -> str:
    txt = _normalize_spaces(full_text)
    start_idx = None
    for h in FORMACION_HEADERS:
        m = re.search(h, txt, flags=re.IGNORECASE)
        if m:
            start_idx = m.end()
            break
    if start_idx is None:
        return ""

    tail = txt[start_idx:]

    # candidatos de corte
    candidates: List[Tuple[int, str]] = []
    for mk in NEXT_SECTION_MARKERS + SOFT_MARKERS:
        m2 = re.search(mk, tail, flags=re.IGNORECASE)
        if m2:
            candidates.append((m2.start(), mk))

    if not candidates:
        return tail.strip()

    candidates.sort(key=lambda x: x[0])

    # si el corte es blando y después siguen títulos típicos, lo ignoramos
    for pos, mk in candidates:
        is_soft = any(re.search(sm, mk, flags=re.IGNORECASE) for sm in SOFT_MARKERS)
        if is_soft:
            after = tail[pos:pos + 6000]
            if re.search(r"\b(Doctorado|Doctor\s+en|Maestr[ií]a|Mag[ií]ster|Magister|Especializaci[oó]n|Licenciatura|Licenciad[oa]s?)\b",
                         after, re.IGNORECASE):
                continue
        return tail[:pos].strip()

    return tail.strip()


def _split_entries(block: str) -> List[str]:
    if not block:
        return []
    lines = [l.strip() for l in block.splitlines()]
    lines = [l for l in lines if l and l.lower() != "null"]

    entries: List[str] = []
    buf: List[str] = []
    for line in lines:
        if RE_ENTRY_START.search(line) and buf:
            entries.append("\n".join(buf).strip())
            buf = [line]
        else:
            buf.append(line)
    if buf:
        entries.append("\n".join(buf).strip())
    return entries


def _entry_is_completed(entry: str) -> bool:
    # si dice en curso, NO
    if RE_IN_PROGRESS.search(entry):
        return False
    # evidencias explícitas
    if RE_FINISH_YEAR.search(entry):
        return True
    if RE_SITUACION_COMPLETO.search(entry):
        return True
    if RE_COMPLETION_CUES.search(entry):
        return True
    return False


def _first_line(entry: str) -> str:
    for l in entry.splitlines():
        l = l.strip()
        if l and l.lower() != "null":
            return l
    return ""


def _classify_entry(entry: str) -> str:
    e = entry.lower()

    if re.search(r"\b(posdoctorado|postdoctorado|posdoctoral|postdoctoral)\b", e, re.IGNORECASE):
        return "posdoc"

    if re.search(r"\bdoctorado\b|\bdoctor\s+en\b|\bdoctor\s+de\s+la\s+universidad\b", e, re.IGNORECASE):
        return "doctorado"

    if re.search(r"\bmaestr[ií]a\b|\bmag[ií]ster\b|\bmagister\b", e, re.IGNORECASE):
        return "maestria"

    if re.search(r"\bespecializaci[oó]n\b|\bespecialista\b", e, re.IGNORECASE):
        return "especializacion"

    if re.search(r"\bprofesorado\b|\bprofesor\s+universitario\b|\bprofesor\s+en\b", e, re.IGNORECASE):
        return "profesorado"

    # grado: incluye "Licenciado en ..." (tu caso: Teología Moral)
    if re.search(
        r"\b(licenciatura|licenciad[oa]s?|ingenier[oa]?|abogad[oa]|m[eé]dic[oa]?|contador(?:a)?|"
        r"arquitect[oa]?|bioqu[ií]mic[oa]?|farmac[eé]utic[oa]?|odont[oó]log[oa]?)\b",
        e, re.IGNORECASE
    ):
        return "grado"

    return "otro"


def _count_formacion(full_text: str) -> Tuple[Dict[str, int], Dict[str, List[str]]]:
    """
    Devuelve:
    - counts: cantidades reales (doctorado/maestria/especializacion/grado/profesorado/posdoc)
    - evidences: lista de títulos (1ª línea) por tipo
    """
    block = _extract_formacion_block(full_text)
    entries = _split_entries(block)

    counts = {"doctorado": 0, "maestria": 0, "especializacion": 0, "grado": 0, "profesorado": 0, "posdoc": 0}
    evid = {k: [] for k in counts.keys()}

    seen = set()

    for ent in entries:
        tipo = _classify_entry(ent)

        # posdoc: NO contar si es contexto RRHH/becas
        if tipo == "posdoc":
            if RE_BECARIO_CONTEXT.search(ent):
                continue
            # si querés exigir finalización explícita para posdoc, descomentá:
            # if not _entry_is_completed(ent): continue
            title = _first_line(ent)
            key = (tipo, _strip_accents(title.lower()))
            if key in seen:
                continue
            seen.add(key)
            counts[tipo] += 1
            evid[tipo].append(title)
            continue

        if tipo not in counts:
            continue

        # SOLO títulos finalizados
        if not _entry_is_completed(ent):
            continue

        title = _first_line(ent)
        key = (tipo, _strip_accents(title.lower()))
        if key in seen:
            continue
        seen.add(key)

        counts[tipo] += 1
        evid[tipo].append(title)

    return counts, evid


# =========================
# Scoring
# =========================
def score_text(
    text: str,
    criteria: Dict[str, Any],
    evidence_max_chars: int = 260
) -> Tuple[List[ItemResult], Dict[str, float], float, str, Dict[str, Any]]:

    text = _normalize_spaces(text)
    sections = criteria.get("sections", {})
    categorias = criteria.get("categorias", {})

    # Conteo robusto SOLO para Formación
    form_counts, form_evid = _count_formacion(text)

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

            # Override SOLO en Formación académica y complementaria
            if section_name.strip().lower().startswith("formación académica") or section_name.strip().lower().startswith("formacion academica"):
                il = item_name.lower()

                if "doctor" in il:
                    count = form_counts["doctorado"]
                    evidence = " | ".join(form_evid["doctorado"][:6])
                elif "maestr" in il or "mag" in il:
                    count = form_counts["maestria"]
                    evidence = " | ".join(form_evid["maestria"][:6])
                elif "especial" in il:
                    count = form_counts["especializacion"]
                    evidence = " | ".join(form_evid["especializacion"][:6])
                elif "título de grado" in il or "titulo de grado" in il or il.strip() == "grado":
                    count = form_counts["grado"]
                    evidence = " | ".join(form_evid["grado"][:6])
                elif "profesor" in il:
                    count = form_counts["profesorado"]
                    evidence = " | ".join(form_evid["profesorado"][:6])
                elif "posdoc" in il or "postdoc" in il or "postdoctor" in il or "posdoctor" in il:
                    count = form_counts["posdoc"]
                    evidence = " | ".join(form_evid["posdoc"][:6])
                else:
                    # ítems de cursos/idiomas/etc: usar regex
                    rx = _compile(pattern)
                    if rx:
                        matches = list(rx.finditer(text))
                        count = len(matches)
                        if matches:
                            evidence = _pick_evidence(text, matches[0], max_chars=evidence_max_chars)

            else:
                # resto de secciones: regex normal
                rx = _compile(pattern)
                if rx:
                    matches = list(rx.finditer(text))
                    count = len(matches)
                    if matches:
                        evidence = _pick_evidence(text, matches[0], max_chars=evidence_max_chars)

            raw_points = float(count) * unit_points
            capped_item_points = min(raw_points, item_max) if item_max >= 0 else raw_points

            results.append(
                ItemResult(
                    section=section_name,
                    item=item_name,
                    pattern=pattern,
                    count=int(count),
                    unit_points=unit_points,
                    raw_points=raw_points,
                    capped_item_points=capped_item_points,
                    item_max_points=item_max,
                    evidence=evidence[:evidence_max_chars],
                )
            )

            sec_sum += capped_item_points

        sec_sum = min(sec_sum, sec_max)
        section_totals[section_name] = sec_sum
        total_points += sec_sum

    # categoría por puntos
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
