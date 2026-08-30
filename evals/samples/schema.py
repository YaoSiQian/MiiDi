from __future__ import annotations

from pydantic import BaseModel, Field


class EvalSample(BaseModel):
    id: str
    style: str
    prompt: str
    constraints: dict = Field(default_factory=dict)
    expectations: dict = Field(default_factory=dict)

    @property
    def sample_type(self) -> str:
        if self.id.startswith("adversarial"):
            return "adversarial"
        if self.id.startswith("hard"):
            return "hard"
        if self.id.startswith("constraint"):
            return "constraint"
        return "basic"
