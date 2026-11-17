import json
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from casavaiano.config import EVALS_DIR

DATASET_PATH = EVALS_DIR / "dataset.jsonl"
DEFAULT_TODAY = date(2026, 11, 17)

Behavior = Literal["answer", "clarify", "escalate"]
Split = Literal["dev", "test"]


class EvalCase(BaseModel):
    id: str
    split: Split
    language: str
    message: str
    today: date = DEFAULT_TODAY
    intent: list[str]
    behavior: list[Behavior]
    tools: list[str] = []
    tools_any: list[str] = []
    tool_args: dict[str, dict[str, Any]] = {}
    must_include: list[list[str]] = []
    must_not_include: list[str] = []
    sources: list[tuple[str, str]] = []
    expected: str
    tags: list[str] = []

    @property
    def must_escalate(self) -> bool:
        return self.behavior == ["escalate"]

    @property
    def may_escalate(self) -> bool:
        return "escalate" in self.behavior


def load_cases(
    path: Path = DATASET_PATH, split: str = "all", ids: list[str] | None = None
) -> list[EvalCase]:
    lines = path.read_text(encoding="utf-8").splitlines()
    cases = [EvalCase(**json.loads(line)) for line in lines if line.strip()]
    if split != "all":
        cases = [c for c in cases if c.split == split]
    if ids:
        cases = [c for c in cases if c.id in ids]
    return cases
