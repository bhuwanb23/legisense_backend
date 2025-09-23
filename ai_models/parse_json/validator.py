from __future__ import annotations

from typing import Dict, Any, List

from .schema import SCHEMA, VALID_RISK, VALID_CLAUSE_CATEGORIES


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    return []


def validate_and_normalize(payload: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {k: [] for k in SCHEMA.keys()}
    if not isinstance(payload, dict):
        return out

    # TL;DR
    tldr = _as_list(payload.get("tldr_bullets"))[:5]
    out["tldr_bullets"] = [str(x).strip() for x in tldr if str(x).strip()]

    # Clauses
    clauses = _as_list(payload.get("clauses"))
    norm_clauses: List[Dict[str, Any]] = []
    for c in clauses:
        if not isinstance(c, dict):
            continue
        category = str(c.get("category", "")).strip()
        if category not in VALID_CLAUSE_CATEGORIES:
            category = "Payment Terms" if category == "" else category
        risk = str(c.get("risk", "low")).lower()
        if risk not in VALID_RISK:
            risk = "low"
        norm_clauses.append({
            "category": category,
            "original_snippet": str(c.get("original_snippet", "")).strip(),
            "explanation": str(c.get("explanation", "")).strip(),
            "risk": risk,
            "icon": c.get("icon") or None,
        })
    out["clauses"] = norm_clauses

    # Risk flags
    flags = _as_list(payload.get("risk_flags"))
    norm_flags: List[Dict[str, Any]] = []
    for f in flags:
        if not isinstance(f, dict):
            continue
        level = str(f.get("level", "low")).lower()
        if level not in VALID_RISK:
            level = "low"
        norm_flags.append({
            "text": str(f.get("text", "")).strip(),
            "level": level,
            "why": str(f.get("why", "")).strip(),
        })
    out["risk_flags"] = norm_flags

    # Comparative context
    comp = _as_list(payload.get("comparative_context"))
    norm_comp: List[Dict[str, Any]] = []
    for cc in comp:
        if not isinstance(cc, dict):
            continue
        norm_comp.append({
            "label": str(cc.get("label", "")).strip(),
            "standard": str(cc.get("standard", "")).strip(),
            "contract": str(cc.get("contract", "")).strip(),
            "assessment": str(cc.get("assessment", "")).strip(),
        })
    out["comparative_context"] = norm_comp

    # Questions
    qs = _as_list(payload.get("suggested_questions"))[:8]
    out["suggested_questions"] = [str(x).strip() for x in qs if str(x).strip()]

    return out


