import re
import json
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple

@dataclass
class ItemResult:
    section: str
    item: str
    count: int
    unit_points: float
    raw_points: float
    capped_points: float
    max_points: float
    evidence: str

def _compile(pattern: str) -> re.Pattern:
    # Permite inline flags (?is) en el pattern
    return re.compile(pattern, flags=0)

def load_criteria(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def score_text(text: str, criteria: Dict[str, Any], max_evidence_chars: int = 240) -> Tuple[List[ItemResult], Dict[str, float], float, str]:
    sections = criteria.get("sections", {})
    categories = criteria.get("categories", {})

    results: List[ItemResult] = []
    section_totals: Dict[str, float] = {}
    total = 0.0

    for section_name, sec in sections.items():
        sec_max = float(sec.get("max_points", 1e9))
        sec_sum = 0.0

        for item_name, item in sec.get("items", {}).items():
            pattern = item.get("pattern", "")
            unit_points = float(item.get("unit_points", 0))
            item_max = float(item.get("max_points", 0))

            if not pattern:
                continue

            rx = _compile(pattern)
            matches = list(rx.finditer(text))
            count = len(matches)

            raw_points = count * unit_points
            capped_item_points = min(raw_points, item_max) if item_max > 0 else raw_points

            evidence = ""
            if matches:
                m0 = matches[0]
                snippet = text[max(0, m0.start()-80): m0.end()+80]
                snippet = re.sub(r"\s+", " ", snippet).strip()
                evidence = snippet[:max_evidence_chars]

            results.append(
                ItemResult(
                    section=section_name,
                    item=item_name,
                    count=count,
                    unit_points=unit_points,
                    raw_points=raw_points,
                    capped_points=capped_item_points,
                    max_points=item_max,
                    evidence=evidence
                )
            )

            sec_sum += capped_item_points

        sec_sum = min(sec_sum, sec_max)
        section_totals[section_name] = sec_sum
        total += sec_sum

    # Categoría: umbrales descendentes
    # categories ejemplo: {"I":1500,"II":1200,...}
    cat = "VI"
    if categories:
        ordered = sorted(categories.items(), key=lambda x: float(x[1]), reverse=True)
        for k, thr in ordered:
            if total >= float(thr):
                cat = k
                break

    return results, section_totals, total, cat
