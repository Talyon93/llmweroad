from typing import Any

from pydantic import BaseModel

UNSUPPORTED_KEYS = {"default", "title"}


def strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Pydantic schema adapted for structured outputs: every object closed, all fields required."""
    return _strict(model.model_json_schema())


def _strict(node: Any) -> Any:
    if isinstance(node, list):
        return [_strict(item) for item in node]
    if not isinstance(node, dict):
        return node
    out = {
        k: (v if k in ("properties", "$defs") else _strict(v))
        for k, v in node.items()
        if k not in UNSUPPORTED_KEYS
    }
    for key in ("properties", "$defs"):
        if key in out:
            out[key] = {name: _strict(sub) for name, sub in out[key].items()}
    if out.get("type") == "object":
        out["additionalProperties"] = False
        out["required"] = list(out.get("properties", {}))
    return out
