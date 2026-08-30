from __future__ import annotations
from dataclasses import dataclass, field
from miidi.eval.score import RuleReport
from miidi.llm.client import LLMClient
from miidi.schema.model import Composition
from miidi.skills.loader import StylePack, load_style_pack

@dataclass(frozen=True)
class JudgeReport:
    J1: float  # Style adherence (0-100)
    J2: float  # Prompt following (0-100)
    J3: float  # Musicality (0-100)
    per_item: dict[str, list[dict]] = field(default_factory=dict)
    evidence: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "J1": round(self.J1, 2),
            "J2": round(self.J2, 2),
            "J3": round(self.J3, 2),
            "per_item": self.per_item,
            "evidence": self.evidence,
        }

def _j1_system(pack: StylePack) -> str:
    return (
        f"You are a music style expert evaluating {pack.name} music.\n"
        f"STYLE FEATURES TO CHECK:\n{pack.skill_md[:2000]}\n\n"
        "Output JSON: {\"score\": 0-100, \"per_item\": [{\"item\": \"...\", "
        "\"verdict\": \"yes|partial|no\", \"evidence\": \"...\"}], "
        "\"evidence\": [{\"track\": \"...\", \"bar\": N, \"text\": \"...\"}]}"
    )

def _j1_user(comp_dict: dict) -> str:
    import json
    return f"COMPOSITION:\n{json.dumps(comp_dict, indent=2)}\n\nEvaluate style adherence."

def _j2_system() -> str:
    return (
        "You evaluate prompt following for music generation.\n"
        "Check: explicit requirements (BPM, instruments, key, duration) against actual.\n"
        "Output JSON: {\"score\": 0-100, \"per_item\": [{\"item\": \"...\", "
        "\"verdict\": \"satisfied|violated|unaddressed\", \"evidence\": \"...\"}], "
        "\"evidence\": [{\"track\": \"...\", \"bar\": N, \"text\": \"...\"}]}"
    )

def _j2_user(comp_dict: dict, prompt: str) -> str:
    import json
    return f"PROMPT: {prompt}\n\nCOMPOSITION:\n{json.dumps(comp_dict, indent=2)}\n\nEvaluate prompt following."

def _j3_system() -> str:
    return (
        "You evaluate overall musicality of a MIDI composition.\n"
        "Rubric: 1=unplayable, 2=errors dense, 3=competent but flat, "
        "4=coherent with dynamics, 5=clear structure with memorable moments.\n"
        "Output JSON: {\"score\": 0-100, \"per_item\": [{\"item\": \"rubric\", "
        "\"verdict\": \"1-5\", \"evidence\": \"...\"}], "
        "\"evidence\": [{\"track\": \"...\", \"bar\": N, \"text\": \"...\"}]}"
    )

def _j3_user(comp_dict: dict, rule_summary: str) -> str:
    import json
    return f"RULE TRACK RESULTS:\n{rule_summary}\n\nCOMPOSITION:\n{json.dumps(comp_dict, indent=2)}\n\nEvaluate musicality."

def _normalize_score(raw: dict) -> float:
    score = raw.get("score", 50.0)
    if isinstance(score, (int, float)):
        return max(0.0, min(100.0, float(score)))
    return 50.0

def evaluate_judge(comp: Composition, rule_report: RuleReport, client: LLMClient,
                   style: str, prompt: str | None = None) -> JudgeReport:
    pack = load_style_pack(style)
    comp_dict = comp.model_dump()
    rule_summary = f"R_rule={rule_report.R_rule:.1f}" if hasattr(rule_report, 'R_rule') else "N/A"
    j2_prompt = prompt or "Evaluate prompt following for this composition."

    # J1: Style adherence
    raw_j1 = client.respond_json(_j1_system(pack), _j1_user(comp_dict))
    j1_score = _normalize_score(raw_j1)

    # J2: Prompt following
    raw_j2 = client.respond_json(_j2_system(), _j2_user(comp_dict, j2_prompt))
    j2_score = _normalize_score(raw_j2)

    # J3: Musicality
    raw_j3 = client.respond_json(_j3_system(), _j3_user(comp_dict, rule_summary))
    j3_score = _normalize_score(raw_j3)

    all_evidence = []
    all_per_item = {}
    for name, raw in [("J1", raw_j1), ("J2", raw_j2), ("J3", raw_j3)]:
        all_per_item[name] = raw.get("per_item", [])
        all_evidence.extend(raw.get("evidence", []))

    return JudgeReport(J1=j1_score, J2=j2_score, J3=j3_score,
                       per_item=all_per_item, evidence=all_evidence)