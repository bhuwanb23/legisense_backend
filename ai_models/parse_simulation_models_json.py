from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple


class ParseError(Exception):
    pass


def _require(obj: Dict[str, Any], key: str, expected_type: Tuple[type, ...]) -> Any:
    if key not in obj:
        raise ParseError(f"Missing required key: {key}")
    val = obj[key]
    if not isinstance(val, expected_type):
        exp = ", ".join(t.__name__ for t in expected_type)
        raise ParseError(f"Key '{key}' must be of type(s): {exp}")
    return val


def parse_models_json(data: str) -> Dict[str, Any]:
    """
    Parse and lightly validate the JSON extracted from simulation.py as per
    prompts/simulation_models_extraction_prompt.txt.

    Returns the loaded dictionary if valid; raises ParseError otherwise.
    """
    try:
        obj = json.loads(data)
    except json.JSONDecodeError as e:
        raise ParseError(f"Invalid JSON: {e}") from e

    # Required root keys
    _require(obj, "file", (str,))
    _require(obj, "extracted_at", (str,))
    models = _require(obj, "models", (list,))
    enums = _require(obj, "enums", (list,))
    relationships = _require(obj, "relationships", (list,))
    _require(obj, "derived", (dict,))

    # Validate models
    for m in models:
        if not isinstance(m, dict):
            raise ParseError("Each model must be an object")
        _require(m, "name", (str,))
        # optional docstring can be str or None
        if "docstring" in m and m["docstring"] is not None and not isinstance(m["docstring"], str):
            raise ParseError("model.docstring must be string or null")
        meta = _require(m, "meta", (dict,))
        # optional ordering
        if "ordering" in meta and meta["ordering"] is not None and not isinstance(meta["ordering"], list):
            raise ParseError("meta.ordering must be list or null")
        str_repr = _require(m, "str_repr", (dict,))
        _require(str_repr, "template", (str,))
        fields = _require(m, "fields", (list,))
        if len(fields) == 0:
            raise ParseError(f"model {m['name']} has no fields")
        for f in fields:
            if not isinstance(f, dict):
                raise ParseError("field must be an object")
            _require(f, "name", (str,))
            _require(f, "kind", (str,))
            # related can be dict or null
            if "related" in f and f["related"] is not None and not isinstance(f["related"], dict):
                raise ParseError("field.related must be object or null")

    # Validate enums
    for e in enums:
        if not isinstance(e, dict):
            raise ParseError("each enum must be an object")
        _require(e, "name", (str,))
        _require(e, "source_model", (str,))
        _require(e, "source_field", (str,))
        members = _require(e, "members", (list,))
        for mem in members:
            if not isinstance(mem, dict):
                raise ParseError("enum.member must be an object")
            _require(mem, "key", (str,))
            _require(mem, "label", (str,))

    # Validate relationships
    for r in relationships:
        if not isinstance(r, dict):
            raise ParseError("each relationship must be an object")
        _require(r, "from_model", (str,))
        _require(r, "from_field", (str,))
        _require(r, "to_model", (str,))
        _require(r, "cardinality", (str,))

    return obj


def get_model(obj: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    for m in obj.get("models", []):
        if m.get("name") == name:
            return m
    return None


def list_foreign_keys(model: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [f for f in model.get("fields", []) if f.get("related") and f["related"].get("type") == "ForeignKey"]
