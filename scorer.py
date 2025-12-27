import json
import re
import unicodedata
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

def load_criteria(path: str = "criteria.json") -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# =========================
# Normalización
# =========================
def _strip_accents(s: str) -> str:
    s = s or ""
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))

def _norm_text(s: str) -> str:
    s = (s or "").replace("\u00A0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

# =========================
# Formación académica STRICT (TXT CLEAN)
# =========================
FORM_HEADERS = [
    r"^\s*FORMACI[ÓO]N\s+ACAD[ÉE]MICA(?:\s+Y\s+COMPLEMENTARIA)?\s*$",
    r"^\s*FORMACION\s+ACADEMICA(?:\s+Y\s+COMPLEMENTARIA)?\s*$",
]

# cortes “seguros” en TXT CLEAN
NEXT_MARKERS = [
    r"^\s*FORMACI[ÓO]N\s+DE\s+RECURSOS\s+HUMANOS\s*$",
    r"^\s*RECURSOS\s+HUMANOS\s*$",
    r"^\s*RRHH\s*$",
    r"^\s*PRODUCCI[ÓO]N\s*$",
    r"^\s*PUBLICACIONES\s*$",
    r"^\s*ANTECEDENTES\s*$",
    r"^\s*ACTIVIDADES\s*$",
    r"^\s*EXPERIENCIA\s*$",
    r"^\s*CARGOS\s*$",
    r"^\s*CVar\b",
    r"^\s*Fecha\s+de\s+generaci[oó]n\b",
]

RE_IN_PROGRESS = re.compile(
    r"\b(Actualidad|En\s+curso|Cursando|Actualmente|Vigente|Hasta\s+la\s+actualidad|A\s+la\s+fecha)\b",
    re.IGNORECASE
)

RE_FINISH_YEAR = re.compile(
    r"A[nñ]o\s+de\s+(finalizaci[oó]n|obtenci[oó]n|graduaci[oó]n)\s*:\s*([0-3]?\d\s*[/\-]\s*\d{4}|\d{4})",
    re.IGNORECASE
)

RE_SITUACION_COMPLETO = re.compile(r"Situaci[oó]n\s+del\s+nivel\s*:\s*Completo", re.IGNORECASE)

RE_COMPLETION_CUES = re.compile(
    r"\b(finalizad[oa]|egresad[oa]|graduad[oa]|t[ií]tulo\s+obtenido|t[ií]tulo\s+otorgado|complet(?:o|ada))\b",
    re.IGNORECASE
)

RE_ENTRY_START = re.compile(
    r"^\s*(?:[-•·*]\s*)?"
    r"(Doctorado|Doctor\s+en|Doctor\s+de\s+la\s+Universidad|"
    r"Maestr[ií]a|Mag[ií]ster|"
    r"Especializaci[oó]n|Especialista|"
    r"Posdoctorado|Postdoctorado|Posdoctoral|"
    r"Profesorado|Profesor\s+Universitario|Profesor\s+en|"
    r"Licenciatura|Licenciad[oa]s?|T[eé]cnica\s+Universitaria|Tecnicatura|"
    r"Contador|Contadora|Contadur[ií]a|"
    r"Abogado|Abogada|Ingenier|Bioqu[ií]mic|M[eé]dic|Farmac[eé]utic|Arquitect|Odont[oó]log)\b",
    re.IGNORECASE
)

def _is_header_line(line: str, header_patterns: List[str]) -> bool:
    for hp in header_patterns:
        if re.search(hp, line, flags=re.IGNORECASE):
            return True
    return False

def extract_formacion_block(text: str) -> str:
    """
    Extrae la sección 'FORMACIÓN ACADÉMICA' del TXT CLEAN.
    Si hay múltiples bloques (por repetición), usa el primero.
    """
    t = _norm_text(text)
    lines = t.splitlines()

    start_idx = None
    for i, ln in enumerate(lines):
        if _is_header_line(ln.strip(), FORM_HEADERS):
            start_idx = i + 1
            break
    if start_idx is None:
        return ""

    end_idx = len(lines)
    for j in range(start_idx, len(lines)):
        if _is_header_line(lines[j].strip(), NEXT_MARKERS):
            end_idx = j
            break

    block = "\n".join(lines[start_idx:end_idx]).strip()
    return block

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
    # si está en curso, nunca
    if RE_IN_PROGRESS.search(entry):
        return False
    # finalización explícita
    if RE_FINISH_YEAR.search(entry):
        return True
    if RE_SITUACION_COMPLETO.search(entry):
        return True
    if RE_COMPLETION_CUES.search(entry):
        return True
    return False

def classify_entry(entry: str) -> str:
    e = entry or ""
    if re.search(r"\b(Posdoctorado|Postdoctorado|Posdoctoral)\b", e, re.IGNORECASE):
        return "posdoc"
    if re.search(r"\bDoctorado\b|\bDoctor\s+en\b|\bDoctor\s+de\s+la\s+Universidad\b", e, re.IGNORECASE):
        return "doctorado"
    if re.search(r"\bMaestr[ií]a\b|\bMag[ií]ster\b", e, re.IGNORECASE):
        return "maestria"
    if re.search(r"\bEspecializaci[oó]n\b|\bEspecialista\b", e, re.IGNORECASE):
        return "especializacion"
    if re.search(r"\bProfesorado\b|\bProfesor\s+Universitario\b|\bProfesor\s+en\b", e, re.IGNORECASE):
        return "profesorado"
    if re.search(
        r"\b(Licenciatura|Licenciad[oa]s?|T[eé]cnica\s+Universitaria|Tecnicatura|"
        r"Contador|Contadora|Contadur[ií]a|Abogado|Abogada|Ingenier|Bioqu[ií]mic|M[eé]dic|Farmac[eé]utic|Arquitect|Odont[oó]log)\b",
        e,
        re.IGNORECASE
    ):
        return "grado"
    return "otro"

def _norm_key(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[\"'`´]", "", s)
    return s

def _pick_entry_evidence(entry: str, max_chars: int = 260) -> str:
    snip = re.sub(r"\s+", " ", (entry or "")).strip()
    return snip[:max_chars]

def compute_formacion_counts(text: str) -> Tuple[Dict[str, int], Dict[str, str]]:
    """
    Devuelve counts por tipo + evidencia (primer match “bueno” por tipo)
    """
    block = extract_formacion_block(text)
    entries = split_entries(block)

    counts = {"doctorado": 0, "maestria": 0, "especializacion": 0, "grado": 0, "profesorado": 0, "posdoc": 0}
    evidence = {k: "" for k in counts.keys()}

    seen = set()
    for e in entries:
        t = classify_entry(e)
        if t not in counts:
            continue
        if not entry_is_completed(e):
            continue

        # dedup por tipo + primeras ~120 chars normalizadas
        k = (t, _norm_key(re.sub(r"\s+", " ", e)[:120]))
        if k in seen:
            continue
        seen.add(k)

        counts[t] += 1
        if not evidence[t]:
            evidence[t] = _pick_entry_evidence(e)

    return counts, evidence

# =========================
# Regex scoring genérico
# =========================
def _compile(pattern: str) -> re.Pattern:
    return re.compile(pattern)

def _pick_evidence(text: str, m: re.Match, max_chars: int = 260) -> str:
    start = max(0, m.start() - 80)
    end = min(len(text), m.end() + 120)
    snippet = text[start:end]
    snippet = re.sub(r"\s+", " ", snippet).strip()
    return snippet[:max_chars]

def _is_formacion_section(section_name: str) -> bool:
    s = _strip_accents(section_name).lower()
    return s.startswith("formacion academica")

def _is_title_item(item_name: str) -> bool:
    s = _strip_accents(item_name).lower()
    return bool(re.search(r"(doctorad|maestr|magister|especializ|posdoc|postdoc|posdoctor|postdoctor|titulo de grado|grado|profesorado)", s))

def _override_key_for_item(item_name: str) -> Optional[str]:
    s = _strip_accents(item_name).lower()
    if "doctorad" in s:
        return "doctorado"
    if "maestr" in s or "magister" in s:
        return "maestria"
    if "especializ" in s or "especialista" in s:
        return "especializacion"
    if "titulo de grado" in s or s.strip() == "grado":
        return "grado"
    if "profesorado" in s or "docencia universitaria" in s:
        return "profesorado"
    if "posdoc" in s or "postdoc" in s or "posdoctor" in s or "postdoctor" in s:
        return "posdoc"
    return None

def score_text(
    text: str,
    criteria: Dict[str, Any],
    evidence_max_chars: int = 260
) -> Tuple[List[ItemResult], Dict[str, float], float, str, Dict[str, Any]]:

    sections = criteria.get("sections", {})
    categorias = criteria.get("categorias", {})

    # STRICT counts para Formación
    form_counts, form_evidence = compute_formacion_counts(text)

    results: List[ItemResult] = []
    section_totals: Dict[str, float] = {}
    total_points = 0.0

    for section_name, sec in sections.items():
        sec_max = float(sec.get("max_points", 10**9))
        sec_sum = 0.0

        items = sec.get("items", {})
        for item_name, item in items.items():
            pattern = item.get("pattern", "")
            if not pattern:
                continue

            unit_points = float(item.get("unit_points", 0))
            item_max = float(item.get("max_points", 0))

            # ===== Overrides STRICT para títulos SOLO en Formación =====
            count = 0
            evidence = ""
            used_override = False

            if _is_formacion_section(section_name):
                k = _override_key_for_item(item_name)
                if k:
                    count = int(form_counts.get(k, 0))
                    evidence = form_evidence.get(k, "")[:evidence_max_chars]
                    used_override = True
                    pattern_used = "<OVERRIDE_FORMACION_STRICT>"
                else:
                    pattern_used = pattern
            else:
                # bloqueo: si es un ítem de títulos, NO se cuenta fuera de Formación
                if _is_title_item(item_name):
                    count = 0
                    evidence = ""
                    used_override = True
                    pattern_used = "<BLOCKED_OUTSIDE_FORMACION>"
                else:
                    pattern_used = pattern

            if not used_override:
                rx = _compile(pattern)
                matches = list(rx.finditer(text))
                count = len(matches)
                if matches:
                    evidence = _pick_evidence(text, matches[0], max_chars=evidence_max_chars)

            raw_points = count * unit_points
            capped_item_points = min(raw_points, item_max) if item_max >= 0 else raw_points

            results.append(
                ItemResult(
                    section=section_name,
                    item=item_name,
                    pattern=pattern_used,
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

    # categoría
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
