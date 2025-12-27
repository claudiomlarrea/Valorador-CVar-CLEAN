import json
import re
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple


# =========================
# Reglas duras de finalización
# =========================
RE_IN_PROGRESS = re.compile(
    r"\b(Actualidad|En\s+curso|Cursando|Actualmente|Vigente|A\s+la\s+fecha|Hasta\s+la\s+actualidad|En\s+desarrollo)\b",
    re.IGNORECASE,
)

RE_FINISH_FIELD = re.compile(
    r"\b(A[nñ]o|Fecha)\s+de\s+(finalizaci[oó]n|obtenci[oó]n|graduaci[oó]n)\s*:\s*(\d{2}/\d{4}|19\d{2}|20\d{2})\b",
    re.IGNORECASE,
)


def requires_explicit_finish(item_name: str) -> bool:
    """
    Decide si un ítem exige finalización explícita.
    Regla: todo ítem cuyo nombre contenga "finalizado/a" exige campo de finalización.
    """
    n = (item_name or "").lower()
    return ("finalizado" in n) or ("finalizada" in n) or ("finalizado/a" in n)


def match_is_completed(match_text: str) -> bool:
    """
    Regla dura:
    - Si aparece 'Actualidad/En curso...' => NO finalizado
    - Debe aparecer explícitamente 'Año/Fecha de finalización:' (o de obtención/graduación)
    """
    if not match_text:
        return False
    if RE_IN_PROGRESS.search(match_text):
        return False
    return bool(RE_FINISH_FIELD.search(match_text))


# =========================
# Estructuras y carga
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


def _compile(pattern: str) -> re.Pattern:
    # Tu criteria.json ya trae flags inline (?is)(?ims), etc.
    # Por eso compilamos sin flags globales para no interferir.
    return re.compile(pattern)


def _pick_evidence(text: str, m: re.Match, max_chars: int = 260) -> str:
    start = max(0, m.start() - 80)
    end = min(len(text), m.end() + 120)
    snippet = text[start:end]
    snippet = re.sub(r"\s+", " ", snippet).strip()
    return snippet[:max_chars]


def score_text(
    text: str,
    criteria: Dict[str, Any],
    evidence_max_chars: int = 260
) -> Tuple[List[ItemResult], Dict[str, float], float, str, Dict[str, Any]]:
    sections = criteria.get("sections", {})
    categorias = criteria.get("categorias", {})

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

            rx = _compile(pattern)
            matches = list(rx.finditer(text))

            # =========================
            # ✅ FILTRO DURO: finalización explícita
            # =========================
            if requires_explicit_finish(item_name):
                filtered = []
                for m in matches:
                    frag = m.group(0) if m else ""
                    if match_is_completed(frag):
                        filtered.append(m)
                matches = filtered

            count = len(matches)

            raw_points = count * unit_points
            capped_item_points = min(raw_points, item_max) if item_max >= 0 else raw_points

            evidence = ""
            if matches:
                evidence = _pick_evidence(text, matches[0], max_chars=evidence_max_chars)

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

    # Categoría por umbral (de mayor a menor)
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
