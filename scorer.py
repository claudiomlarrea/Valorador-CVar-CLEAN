import json
import re
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple, Optional

# =========================
# Data model
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
# Criteria IO
# =========================
def load_criteria(path: str = "criteria.json") -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _compile(pattern: str) -> re.Pattern:
    # patrones ya vienen con (?is) en la mayoría de los casos
    return re.compile(pattern)

def _pick_evidence(text: str, m: re.Match, max_chars: int = 260) -> str:
    start = max(0, m.start() - 80)
    end = min(len(text), m.end() + 120)
    snippet = text[start:end]
    snippet = re.sub(r"\s+", " ", snippet).strip()
    return snippet[:max_chars]

# ==========================================================
# Formación académica: recorte + parseo + regla dura
# ==========================================================
FORMACION_HEADERS = [
    r"\bFORMACI[ÓO]N\s+ACAD[ÉE]MICA\b",
    r"\bFORMACION\s+ACADEMICA\b",
]

NEXT_SECTION_MARKERS = [
    r"\n\s*FORMACI[ÓO]N\s+DE\s+RECURSOS\s+HUMANOS\b",
    r"\n\s*RECURSOS\s+HUMANOS\b",
    r"\n\s*RRHH\b",
    r"\n\s*ANTECEDENTES\b",
    r"\n\s*FINANCIAMIENTO\b",
    r"\n\s*ACTIVIDADES\b",
    r"\n\s*PUBLICACIONES\b",
    r"\n\s*PRODUCCI[ÓO]N\b",
    r"\n\s*OTROS\s+ANTECEDENTES\b",
    r"\n\s*CVar\s*\b",
    r"\n\s*Fecha\s+de\s+generaci[oó]n\b",
]

RE_IN_PROGRESS = re.compile(
    r"\b(Actualidad|En\s+curso|Cursando|Actualmente|Vigente|Hasta\s+la\s+actualidad|A\s+la\s+fecha)\b",
    re.IGNORECASE
)

RE_FINISH_YEAR = re.compile(
    r"A[nñ]o\s+de\s+(finalizaci[oó]n|obtenci[oó]n|graduaci[oó]n)\s*:\s*([0-3]?\d\s*[/\-]\s*\d{4}|\d{4})",
    re.IGNORECASE
)

RE_SITUACION_COMPLETO = re.compile(
    r"Situaci[oó]n\s+del\s+nivel\s*:\s*Completo",
    re.IGNORECASE
)

RE_COMPLETION_CUES = re.compile(
    r"\b(finalizad[oa]|egresad[oa]|graduad[oa]|t[ií]tulo\s+obtenido|t[ií]tulo\s+otorgado|complet(?:o|ada))\b",
    re.IGNORECASE
)

RE_ENTRY_START = re.compile(
    r"^\s*(?:[-•·*]\s*)?"
    r"(Doctorado|Doctor\s+en|Doctor\s+de\s+la\s+Universidad|Doctor\b|"
    r"Maestr[ií]a|"
    r"Especializaci[oó]n|Especialista|"
    r"Posdoctorado|Postdoctorado|"
    r"Profesorado|Profesor\s+Universitario|"
    r"Licenciatura|Licenciad[oa]s?|Tecnicatura|T[eé]cnica\s+Universitaria|"
    r"Contador|Contadora|Abogado|Abogada|Ingenier|Bioqu[ií]mic|M[eé]dic|Farmac[eé]utic|Arquitect|Odont[oó]log)\b",
    re.IGNORECASE
)

def _normalize_spaces(s: str) -> str:
    s = (s or "").replace("\u00A0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def extract_formacion_academica_block(full_text: str) -> str:
    txt = _normalize_spaces(full_text)
    start_idx: Optional[int] = None
    for h in FORMACION_HEADERS:
        m = re.search(h, txt, flags=re.IGNORECASE)
        if m:
            start_idx = m.end()
            break
    if start_idx is None:
        return ""

    tail = txt[start_idx:]
    end = len(tail)
    for mk in NEXT_SECTION_MARKERS:
        m2 = re.search(mk, tail, flags=re.IGNORECASE)
        if m2:
            end = min(end, m2.start())
    return tail[:end].strip()

def split_entries(block: str) -> List[str]:
    if not block:
        return []
    lines = [l.strip() for l in block.split("\n")]
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

def entry_is_completed(entry: str) -> bool:
    # regla dura: Actualidad/en curso invalida siempre
    if RE_IN_PROGRESS.search(entry):
        return False
    if RE_FINISH_YEAR.search(entry):
        return True
    if RE_SITUACION_COMPLETO.search(entry):
        return True
    if RE_COMPLETION_CUES.search(entry):
        return True
    return False

def classify_entry(entry: str) -> str:
    e = entry or ""
    if re.search(r"\bPosdoctorado\b|\bPostdoctorado\b", e, re.IGNORECASE):
        return "posdoc"
    if re.search(r"\bDoctorado\b|\bDoctor\s+en\b|\bDoctor\s+de\s+la\s+Universidad\b|\bDoctor\b", e, re.IGNORECASE):
        return "doctorado"
    # IMPORTANTÍSIMO: acá NO contamos "Magister" como maestría (decisión institucional)
    if re.search(r"\bMaestr[ií]a\b", e, re.IGNORECASE):
        return "maestria"
    if re.search(r"\bEspecializaci[oó]n\b|\bEspecialista\b", e, re.IGNORECASE):
        return "especializacion"
    if re.search(r"\bProfesorado\b|\bProfesor\s+Universitario\b", e, re.IGNORECASE):
        return "profesorado"
    if re.search(
        r"\b(Licenciatura|Licenciad[oa]s?|Tecnicatura|T[eé]cnica\s+Universitaria|"
        r"Contador|Contadora|Abogado|Abogada|Ingenier|Bioqu[ií]mic|M[eé]dic|Farmac[eé]utic|Arquitect|Odont[oó]log)\b",
        e, re.IGNORECASE
    ):
        return "grado"
    return "otro"

def count_formacion_completed(full_text: str) -> Dict[str, int]:
    block = extract_formacion_academica_block(full_text)
    entries = split_entries(block)

    counts = {
        "doctorado": 0,
        "maestria": 0,
        "especializacion": 0,
        "grado": 0,
        "profesorado": 0,
        "posdoc": 0,
    }

    # dedupe simple por primeras ~350 chars normalizadas
    seen = set()
    for e in entries:
        t = classify_entry(e)
        if t not in counts:
            continue
        if not entry_is_completed(e):
            continue
        key = re.sub(r"\s+", " ", e.lower()).strip()[:350]
        if key in seen:
            continue
        seen.add(key)
        counts[t] += 1

    return counts

# ==========================================================
# Scoring
# ==========================================================
def score_text(
    text: str,
    criteria: Dict[str, Any],
    evidence_max_chars: int = 260
) -> Tuple[List[ItemResult], Dict[str, float], float, str, Dict[str, Any]]:

    sections = criteria.get("sections", {})
    categorias = criteria.get("categorias", {})

    # ✅ Conteos robustos SOLO para Formación
    form_counts = count_formacion_completed(text)

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

            # -------------------------
            # OVERRIDE Formación Académica
            # -------------------------
            count = 0
            evidence = ""

            if section_name.strip().lower().startswith("formación académica") or section_name.strip().lower().startswith("formacion academica"):
                il = item_name.lower()

                if "doctor" in il:
                    count = form_counts.get("doctorado", 0)
                elif "maestr" in il:
                    count = form_counts.get("maestria", 0)
                elif "especial" in il:
                    count = form_counts.get("especializacion", 0)
                elif "título de grado" in il or "titulo de grado" in il:
                    count = form_counts.get("grado", 0)
                elif "profesorado" in il or "docencia universitaria" in il:
                    count = form_counts.get("profesorado", 0)
                elif "posdoctor" in il or "posdoc" in il or "postdoc" in il:
                    count = form_counts.get("posdoc", 0)
                else:
                    # para cursos/idiomas/etc usamos regex normal
                    count = -1  # marcador para seguir por regex

                if count >= 0:
                    # evidencia: no hay "match" aquí porque no usamos regex del item
                    evidence = "Conteo por parseo de FORMACION ACADEMICA (regla dura de finalización)."

            # -------------------------
            # Regex normal (o fallback de Formación para ítems no override)
            # -------------------------
            if count == -1:
                if not pattern:
                    count = 0
                else:
                    try:
                        rx = _compile(pattern)
                        matches = list(rx.finditer(text))
                        count = len(matches)
                        if matches:
                            evidence = _pick_evidence(text, matches[0], max_chars=evidence_max_chars)
                    except re.error:
                        count = 0
                        evidence = "Regex inválida (no se pudo compilar)."

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
                    evidence=evidence,
                )
            )

            sec_sum += capped_item_points

        sec_sum = min(sec_sum, sec_max)
        section_totals[section_name] = sec_sum
        total_points += sec_sum

    # Categoría
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
