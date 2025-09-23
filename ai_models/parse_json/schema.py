from typing import Any, Dict, List


SCHEMA: Dict[str, Any] = {
    "tldr_bullets": list,
    "clauses": list,
    "risk_flags": list,
    "comparative_context": list,
    "suggested_questions": list,
}

VALID_RISK = {"low", "medium", "high"}
VALID_CLAUSE_CATEGORIES = {
    "Payment Terms",
    "Termination / Exit",
    "Liability & Damages",
    "Confidentiality",
    "Dispute Resolution",
    "Renewal / Extension",
}


