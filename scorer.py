No, sigue mal, García tiene: 3 Doctorados 1 Maestría como Magister 1 Título de grado INSTITUTO DE HISTORIA ; FACULTAD DE FILOSOFIA Y LETRAS ; UNIVERSIDAD NACIONAL DE CUYO Año de finalización: 2012 &#61485;Doctor en Filosofía UNIVERSIDAD NACIONAL DE CUYO (UNCU) Año de finalización: 2000 &#61485;Doctor en Teología. PONTIFICIA UNIVERSIDAD GREGORIANA Año de finalización: 1994 CVar ES UNA INICIATIVA DEL MINISTERIO DE CIENCIA, Fecha de generación: 21/10/2021 2 GARCÍA, JOSÉ JUAN Magister en Bioética Año de finalización: 1993 &#61485;Perito en Ecumenismo UNIVERSIDAD DE SAN BUENAVENTURA Año de finalización: 1987 Licenciado en Teología Moral PONTIFICIA UNIVERSIDAD LATERANENSE Año de finalización: 05/1993No, sigue mal, García tiene: 3 Doctorados 1 Maestría como Magister 1 Título de grado INSTITUTO DE HISTORIA ; FACULTAD DE FILOSOFIA Y LETRAS ; UNIVERSIDAD NACIONAL DE CUYO Año de finalización: 2012 &#61485;Doctor en Filosofía UNIVERSIDAD NACIONAL DE CUYO (UNCU) Año de finalización: 2000 &#61485;Doctor en Teología. PONTIFICIA UNIVERSIDAD GREGORIANA Año de finalización: 1994 CVar ES UNA INICIATIVA DEL MINISTERIO DE CIENCIA, Fecha de generación: 21/10/2021 2 GARCÍA, JOSÉ JUAN Magister en Bioética Año de finalización: 1993 &#61485;Perito en Ecumenismo UNIVERSIDAD DE SAN BUENAVENTURA Año de finalización: 1987 Licenciado en Teología Moral PONTIFICIA UNIVERSIDAD LATERANENSE Año de finalización: 05/1993import json
import re
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple, Optional
import unicodedata


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


def _compile(pattern: str) -> re.Pattern:
    return re.compile(pattern)


def _pick_evidence(text: str, m: re.Match, max_chars: int = 260) -> str:
    start = max(0, m.start() - 80)
    end = min(len(text), m.end() + 120)
    snippet = text[start:end]
    snippet = re.sub(r"\s+", " ", snippet).strip()
    return snippet[:max_chars]


# =========================
# Helpers de normalización
# =========================
def _strip_accents(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def _norm_spaces(s: str) -> str:
    s = s.replace("\u00A0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _norm_key(s: str) -> str:
    s = (s or "").lower().strip()
    s = _strip_accents(s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[\"'`´]", "", s)
    return s


# ==========================================================
#  OVERRIDE: Conteo real de títulos en "Formación académica"
#  (sin cambiar puntajes; solo corrige Ocurrencias + evidencia)
# ==========================================================
FORM_HEADERS = [
    r"FORMACI[ÓO]N\s+ACAD[ÉE]MICA",
    r"FORMACI[ÓO]N\s+ACAD[ÉE]MICA\s+Y\s+COMPLEMENTARIA",
    r"FORMACION\s+ACADEMICA",
    r"FORMACION\s+ACADEMICA\s+Y\s+COMPLEMENTARIA",
]

FORM_NEXT_MARKERS = [
    r"\n\s*FORMACI[ÓO]N\s+DE\s+RECURSOS\s+HUMANOS\b",
    r"\n\s*RECURSOS\s+HUMANOS\b",
    r"\n\s*RRHH\b",
    r"\n\s*PUBLICACIONES\b",
    r"\n\s*PRODUCCI[ÓO]N\b",
    r"\n\s*ANTECEDENTES\b",
    r"\n\s*ACTIVIDADES\b",
    r"\n\s*CVar\b",
    r"\n\s*Fecha\s+de\s+generaci[oó]n\b",
]

RE_IN_PROGRESS = re.compile(
    r"\b(Actualidad|En\s+curso|Cursando|Actualmente|Vigente|En\s+desarrollo|Hasta\s+la\s+actualidad|A\s+la\s+fecha)\b",
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

# En CVar aparecen bullets raros tipo &#61485; o viñetas
RE_BULLET = re.compile(r"^\s*(?:&#\d+;|[-•·*]\s*)\s*", re.IGNORECASE)

RE_ENTRY_START = re.compile(
    r"^\s*(?:&#\d+;|[-•·*]\s*)?\s*"
    r"(Doctorado|Doctor\s+en|Doctor\s+de\s+la\s+Universidad|"
    r"Maestr[ií]a|Mag[ií]ster|Magister|"
    r"Especializaci[oó]n|Especialista|"
    r"Posdoctorado|Postdoctorado|"
    r"Licenciatura|Licenciad[oa]s?\s+en|Licenciad[oa]s?|"
    r"Tecnicatura|T[eé]cnica\s+Universitaria|"
    r"Profesorado|Profesor\s+Universitario|"
    r"Contador|Contadora|Contadur[ií]a|"
    r"Abogad[oa]|Ingenier|Bioqu[ií]mic|M[eé]dic|Farmac[eé]utic|Arquitect|Odont[oó]log)\b",
    re.IGNORECASE
)

RE_BECARIO_CONTEXT = re.compile(
    r"\b(becari[oa]s?|beca|direcci[oó]n|co[- ]?direcci[oó]n|tesista|investigador/a|investigador)\b",
    re.IGNORECASE
)


def _extract_form_block(full_text: str) -> str:
    txt = _norm_spaces(full_text)
    start_idx = None
    for h in FORM_HEADERS:
        m = re.search(h, txt, flags=re.IGNORECASE)
        if m:
            start_idx = m.end()
            break
    if start_idx is None:
        return ""

    tail = txt[start_idx:]
    cut = None
    for mk in FORM_NEXT_MARKERS:
        m2 = re.search(mk, tail, flags=re.IGNORECASE)
        if m2:
            cut = m2.start() if cut is None else min(cut, m2.start())
    return tail[:cut].strip() if cut is not None else tail.strip()


def _split_entries(block: str) -> List[str]:
    if not block:
        return []
    lines = [l.rstrip() for l in block.splitlines()]
    lines = [l for l in lines if l and l.strip().lower() != "null"]

    entries: List[str] = []
    buf: List[str] = []
    for ln in lines:
        if RE_ENTRY_START.search(ln) and buf:
            entries.append("\n".join(buf).strip())
            buf = [ln]
        else:
            buf.append(ln)
    if buf:
        entries.append("\n".join(buf).strip())

    return entries


def _entry_is_completed(entry: str) -> bool:
    # Regla dura:
    # - si hay "Actualidad/En curso" => NO finalizado
    # - solo finaliza si hay evidencia explícita (año de finalización / situacion completo / cues)
    if RE_IN_PROGRESS.search(entry):
        return False
    if RE_FINISH_YEAR.search(entry):
        return True
    if RE_SITUACION_COMPLETO.search(entry):
        return True
    if RE_COMPLETION_CUES.search(entry):
        return True
    return False


def _classify(entry: str) -> str:
    e = entry
    if re.search(r"\b(Doctorado|Doctor\s+en|Doctor\s+de\s+la\s+Universidad)\b", e, re.IGNORECASE):
        return "doctorado"
    if re.search(r"\b(Maestr[ií]a|Mag[ií]ster|Magister)\b", e, re.IGNORECASE):
        return "maestria"
    if re.search(r"\b(Especializaci[oó]n|Especialista)\b", e, re.IGNORECASE):
        return "especializacion"
    if re.search(r"\b(Posdoctorado|Postdoctorado)\b", e, re.IGNORECASE):
        return "posdoc"
    if re.search(r"\b(Profesorado|Profesor\s+Universitario)\b", e, re.IGNORECASE):
        return "profesorado"
    # Grado: incluye "Licenciado en ..." (caso García: Licenciado en Teología Moral)
    if re.search(r"\b(Licenciatura|Licenciad[oa]s?\s+en|Licenciad[oa]s?)\b", e, re.IGNORECASE):
        return "grado"
    if re.search(r"\b(Contador|Contadora|Contadur[ií]a|Abogad[oa]|Ingenier|Bioqu[ií]mic|M[eé]dic|Farmac[eé]utic|Arquitect|Odont[oó]log)\b", e, re.IGNORECASE):
        return "grado"
    return "otro"


def _title_line(entry: str) -> str:
    for ln in entry.splitlines():
        ln2 = RE_BULLET.sub("", ln).strip()
        if ln2 and ln2.lower() != "null":
            return ln2
    return ""


def _finish_token(entry: str) -> str:
    m = RE_FINISH_YEAR.search(entry)
    if m:
        return re.sub(r"\s+", "", m.group(2).strip())
    if RE_SITUACION_COMPLETO.search(entry):
        return "COMPLETO"
    if RE_COMPLETION_CUES.search(entry):
        return "FINALIZADO"
    return ""


def _compute_form_counts(full_text: str) -> Tuple[Dict[str, int], Dict[str, str]]:
    block = _extract_form_block(full_text)
    entries = _split_entries(block)

    counts = {
        "doctorado": 0,
        "maestria": 0,
        "especializacion": 0,
        "grado": 0,
        "profesorado": 0,
        "posdoc": 0,
    }
    evidence_first: Dict[str, str] = {k: "" for k in counts.keys()}

    seen = set()

    for e in entries:
        t = _classify(e)
        if t not in counts:
            continue

        # Evitar falsos posdoc por contexto RRHH
        if t == "posdoc" and RE_BECARIO_CONTEXT.search(e):
            continue

        if not _entry_is_completed(e):
            continue

        title = _norm_key(_title_line(e))
        fin = _norm_key(_finish_token(e))

        # dedup por tipo+título+año
        key = (t, title, fin)
        if key in seen:
            continue
        seen.add(key)

        counts[t] += 1
        if not evidence_first[t]:
            # evidencia humana: 2-3 líneas principales
            ev_lines = [RE_BULLET.sub("", ln).strip() for ln in e.splitlines() if ln.strip()]
            evidence_first[t] = " | ".join(ev_lines[:3])[:260]

    return counts, evidence_first


def score_text(
    text: str,
    criteria: Dict[str, Any],
    evidence_max_chars: int = 260
) -> Tuple[List[ItemResult], Dict[str, float], float, str, Dict[str, Any]]:
    sections = criteria.get("sections", {})
    categorias = criteria.get("categorias", {})

    # ✅ PRE-CÁLCULO: conteos reales de formación (solo afecta visualización/ocurrencias)
    form_counts, form_evidence = _compute_form_counts(text)

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

            count = 0
            evidence = ""

            # ✅ OVERRIDE SOLO PARA FORMACIÓN ACADÉMICA (mostrar ocurrencias reales)
            if section_name.strip().lower().startswith("formación académica") or section_name.strip().lower().startswith("formacion academica"):
                item_l = item_name.lower()

                if "doctorad" in item_l:
                    count = int(form_counts.get("doctorado", 0))
                    evidence = form_evidence.get("doctorado", "")
                elif "maestr" in item_l or "magister" in item_l or "magíster" in item_l:
                    count = int(form_counts.get("maestria", 0))
                    evidence = form_evidence.get("maestria", "")
                elif "especializ" in item_l or "especialista" in item_l:
                    count = int(form_counts.get("especializacion", 0))
                    evidence = form_evidence.get("especializacion", "")
                elif "título de grado" in item_l or "titulo de grado" in item_l or item_l.strip() == "grado":
                    count = int(form_counts.get("grado", 0))
                    evidence = form_evidence.get("grado", "")
                elif "profesorado" in item_l or "docencia universitaria" in item_l:
                    count = int(form_counts.get("profesorado", 0))
                    evidence = form_evidence.get("profesorado", "")
                elif re.search(r"\bposdoc\b|\bpostdoc\b|\bposdoctorad\b|\bpostdoctorad\b", item_l):
                    count = int(form_counts.get("posdoc", 0))
                    evidence = form_evidence.get("posdoc", "")
                else:
                    # ítems de cursos/idiomas dentro de la sección siguen por regex
                    rx = _compile(pattern)
                    matches = list(rx.finditer(text))
                    count = len(matches)
                    if matches:
                        evidence = _pick_evidence(text, matches[0], max_chars=evidence_max_chars)
            else:
                # Normal: por regex
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
