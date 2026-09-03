from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from miidi.eval.score import RuleReport
from miidi.llm.client import LLMClient
from miidi.schema.model import Composition
from miidi.skills.loader import StylePack, load_style_pack

_KEY_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_BPM_PATTERN = re.compile(r"(\d{2,3})\s*(?:bpm|BPM)", re.IGNORECASE)
_BPM_EQUALS = re.compile(r"bpm\s*[=:]\s*(\d{2,3})", re.IGNORECASE)
_KEY_PATTERN = re.compile(
    r"\b([A-G][#b]?)\s*"
    r"(major|minor|maj|min|m|M|dor|lyd|mix|phr|loc)\b",
    re.IGNORECASE,
)
_DURATION_BARS = re.compile(r"(\d+)\s*(?:bar|measure|小节)", re.IGNORECASE)
_DURATION_BEATS = re.compile(r"(\d+)\s*(?:beat|拍)", re.IGNORECASE)
_INSTRUMENT_KEYWORDS: dict[str, int] = {
    "piano": 0,
    "acoustic grand": 0,
    "guitar": 25,
    "electric guitar": 27,
    "acoustic guitar": 24,
    "bass": 32,
    "electric bass": 33,
    "synth bass": 38,
    "drums": 0,
    "drum": 0,
    "violin": 40,
    "viola": 41,
    "cello": 42,
    "trumpet": 56,
    "trombone": 57,
    "saxophone": 65,
    "sax": 65,
    "flute": 73,
    "clarinet": 71,
    "oboe": 68,
    "strings": 48,
    "string": 48,
    "pad": 88,
    "organ": 19,
    "harpsichord": 6,
}


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


def _extract_style_checklist(pack: StylePack) -> str:
    lines = []
    lines.append(f"STYLE: {pack.name}")
    lines.append("")
    lines.append("IDENTITY (from SKILL.md):")
    for line in pack.skill_md.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            lines.append(f"  {line}")
    lines.append("")
    lines.append("INSTRUMENTATION (from instruments.md):")
    for line in pack.instruments_md.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            lines.append(f"  {line}")
    lines.append("")
    lines.append("STYLE CHECKLIST (check each item yes/partial/no):")
    lines.append("1. Does the instrumentation match the style's standard ensemble?")
    lines.append("2. Are the instruments in their correct registers for the style?")
    lines.append("3. Does the rhythm/groove match the style's feel (swing, backbeat, etc.)?")
    lines.append("4. Is the harmonic vocabulary appropriate (chord types, progressions)?")
    lines.append("5. Does the density/complexity match the style's expectations?")
    lines.append("6. Are style-specific prohibitions respected (e.g., no drums in classical)?")
    lines.append("7. Does the overall texture/layering match the style?")
    lines.append("8. Is the tempo within the style's typical range?")
    return "\n".join(lines)


def _j1_system(pack: StylePack) -> str:
    checklist = _extract_style_checklist(pack)
    return (
        f"You are a music style expert evaluating {pack.name} music.\n\n"
        f"{checklist}\n\n"
        "For each checklist item, respond with yes/partial/no and cite specific evidence "
        "(track name + bar number). Score 0-100 based on how many items pass.\n\n"
        'Output JSON: {"score": 0-100, "per_item": [{"item": "checklist item N", '
        '"verdict": "yes|partial|no", "evidence": "track X bar Y: ..."}], '
        '"evidence": [{"track": "...", "bar": N, "text": "..."}]}'
    )


def _j1_user(comp_dict: dict) -> str:
    return f"COMPOSITION:\n{json.dumps(comp_dict, indent=2)}\n\nEvaluate style adherence."


def _parse_prompt_constraints(prompt: str) -> dict[str, str | None]:
    result: dict[str, str | None] = {
        "bpm": None,
        "key": None,
        "duration_bars": None,
        "instruments": None,
    }
    m = _BPM_EQUALS.search(prompt) or _BPM_PATTERN.search(prompt)
    if m:
        result["bpm"] = m.group(1)
    m = _KEY_PATTERN.search(prompt)
    if m:
        tonic = m.group(1).upper()
        if len(tonic) == 2:
            tonic = tonic[0] + "#" if tonic[1] == "#" else tonic[0] + "b"
        mode_raw = (m.group(2) or "major").lower()
        mode_map = {
            "major": "major",
            "maj": "major",
            "m": "minor",
            "minor": "minor",
            "min": "minor",
            "dor": "dorian",
            "lyd": "lydian",
            "mix": "mixolydian",
            "phr": "phrygian",
            "loc": "locrian",
        }
        mode = mode_map.get(mode_raw, "major")
        result["key"] = f"{tonic} {mode}"
    m = _DURATION_BARS.search(prompt)
    if m:
        result["duration_bars"] = m.group(1)
    else:
        m = _DURATION_BEATS.search(prompt)
        if m:
            result["duration_bars"] = m.group(1) + " beats"
    found_instruments = []
    prompt_lower = prompt.lower()
    for kw, program in _INSTRUMENT_KEYWORDS.items():
        if kw in prompt_lower:
            found_instruments.append(f"{kw}(program={program})")
    if found_instruments:
        result["instruments"] = ", ".join(found_instruments)
    return result


def _extract_explicit_constraints(comp: Composition, prompt: str) -> list[dict]:
    parsed = _parse_prompt_constraints(prompt)
    meta = comp.meta
    key_name = _KEY_NAMES[meta.key.tonic_pc]
    key_str = f"{key_name} {meta.key.mode}"
    total_bars = comp.total_bars()
    duration_bars = int(total_bars) if total_bars else 0
    programs_used = [t.program for t in comp.tracks if not t.is_drum]
    programs_str = ", ".join(str(p) for p in programs_used) if programs_used else "none"
    constraints = []
    if parsed["bpm"]:
        constraints.append(
            {
                "item": "BPM",
                "expected": parsed["bpm"],
                "actual": str(meta.bpm),
                "check": f"Prompt specifies {parsed['bpm']} BPM; composition has {meta.bpm}",
            }
        )
    else:
        constraints.append(
            {
                "item": "BPM",
                "expected": "not specified",
                "actual": str(meta.bpm),
                "check": "Prompt does not specify BPM; mark as unaddressed",
            }
        )
    if parsed["key"]:
        constraints.append(
            {
                "item": "Key/Tonality",
                "expected": parsed["key"],
                "actual": key_str,
                "check": f"Prompt specifies {parsed['key']}; composition is {key_str}",
            }
        )
    else:
        constraints.append(
            {
                "item": "Key/Tonality",
                "expected": "not specified",
                "actual": key_str,
                "check": "Prompt does not specify key; mark as unaddressed",
            }
        )
    if parsed["duration_bars"]:
        constraints.append(
            {
                "item": "Duration",
                "expected": parsed["duration_bars"],
                "actual": f"{duration_bars} bars",
                "check": f"Prompt specifies {parsed['duration_bars']}; composition is {duration_bars} bars",
            }
        )
    else:
        constraints.append(
            {
                "item": "Duration",
                "expected": "not specified",
                "actual": f"{duration_bars} bars",
                "check": "Prompt does not specify duration; mark as unaddressed",
            }
        )
    if parsed["instruments"]:
        constraints.append(
            {
                "item": "Specified instruments",
                "expected": parsed["instruments"],
                "actual": f"programs: {programs_str}",
                "check": f"Prompt specifies {parsed['instruments']}; composition uses programs {programs_str}",
            }
        )
    else:
        constraints.append(
            {
                "item": "Specified instruments",
                "expected": "not specified",
                "actual": f"programs: {programs_str}",
                "check": "Prompt does not specify instruments; mark as unaddressed",
            }
        )
    return constraints


def _j2_system(constraints_json: str) -> str:
    return (
        "You evaluate prompt following for music generation.\n\n"
        "EXPLICIT CONSTRAINTS (parsed from prompt vs composition metadata):\n"
        f"{constraints_json}\n\n"
        "For each constraint:\n"
        "- Compare 'expected' (from prompt) vs 'actual' (from composition)\n"
        "- If prompt specified it and it matches: 'satisfied'\n"
        "- If prompt specified it and it mismatches: 'violated'\n"
        "- If prompt didn't specify it: 'unaddressed'\n\n"
        "For IMAGE/EMOTIONAL requirements (e.g., 'happy', 'relaxing', 'epic'):\n"
        "- Judge if the composition's characteristics match the described mood\n"
        "- Mark as satisfied/violated/unaddressed with evidence\n\n"
        'Output JSON: {"score": 0-100, "per_item": [{"item": "...", '
        '"verdict": "satisfied|violated|unaddressed", "evidence": "..."}], '
        '"evidence": [{"track": "...", "bar": N, "text": "..."}]}'
    )


def _j2_user(comp_dict: dict, prompt: str) -> str:
    return (
        f"USER PROMPT: {prompt}\n\n"
        f"COMPOSITION:\n{json.dumps(comp_dict, indent=2)}\n\n"
        f"Check each constraint and evaluate prompt following."
    )


def _j3_system() -> str:
    return (
        "You evaluate overall musicality of a MIDI composition.\n\n"
        "RUBRIC (score 1-5):\n"
        "1 = Unplayable: chaotic note placement, no discernible melody or harmony, "
        "rhythmically incoherent, sounds like random MIDI events.\n"
        "2 = Errors dense: has some musical structure but contains frequent wrong notes, "
        "rhythmic mistakes, register violations, or obvious violations of music theory.\n"
        "3 = Competent but flat: technically correct but lacks expression, dynamics, "
        "or memorable moments; sounds mechanical or formulaic.\n"
        "4 = Coherent with dynamics: well-formed melody and harmony, appropriate dynamics "
        "and articulation, some development or variation, engaging to listen to.\n"
        "5 = Clear structure with memorable moments: strong thematic development, "
        "effective use of contrast, clear sections, contains hooks or memorable phrases, "
        "demonstrates stylistic understanding.\n\n"
        "For each aspect, cite specific evidence (track name + bar number).\n\n"
        'Output JSON: {"score": 0-100, "per_item": [{"item": "rubric", '
        '"verdict": "1-5", "evidence": "..."}], '
        '"evidence": [{"track": "...", "bar": N, "text": "..."}]}'
    )


def _j3_user(comp_dict: dict, rule_summary: str) -> str:
    return (
        f"RULE TRACK RESULTS:\n{rule_summary}\n\n"
        f"COMPOSITION:\n{json.dumps(comp_dict, indent=2)}\n\n"
        f"Evaluate musicality using the rubric above."
    )


def _build_rule_summary(rule_report: RuleReport) -> str:
    lines = [f"R_rule = {rule_report.R_rule:.1f}/100"]
    if rule_report.axes:
        lines.append("\nAxis scores:")
        for name, ax in rule_report.axes.items():
            lines.append(f"  {name}: {ax.score:.2f}")
    if rule_report.gates:
        lines.append("\nGate multipliers:")
        for name, val in rule_report.gates.items():
            lines.append(f"  G_{name}: {val:.3f}")
    if rule_report.violations:
        lines.append(f"\nViolations ({len(rule_report.violations)}):")
        for v in rule_report.violations[:10]:
            lines.append(f"  - [{v.location}] {v.message}")
    return "\n".join(lines)


def _normalize_score(raw: dict) -> float:
    score = raw.get("score", 50.0)
    if isinstance(score, (int, float)):
        return max(0.0, min(100.0, float(score)))
    return 50.0


def evaluate_judge(
    comp: Composition,
    rule_report: RuleReport,
    client: LLMClient,
    style: str,
    prompt: str | None = None,
) -> JudgeReport:
    pack = load_style_pack(style)
    comp_dict = comp.model_dump()
    rule_summary = _build_rule_summary(rule_report)
    j2_prompt = prompt or "Evaluate prompt following for this composition."

    # J1: Style adherence
    raw_j1 = client.respond_json(_j1_system(pack), _j1_user(comp_dict))
    j1_score = _normalize_score(raw_j1)

    # J2: Prompt following (with extracted constraints)
    constraints = _extract_explicit_constraints(comp, j2_prompt)
    constraints_json = json.dumps(constraints, indent=2)
    raw_j2 = client.respond_json(_j2_system(constraints_json), _j2_user(comp_dict, j2_prompt))
    j2_score = _normalize_score(raw_j2)

    # J3: Musicality (with full rule evidence)
    raw_j3 = client.respond_json(_j3_system(), _j3_user(comp_dict, rule_summary))
    j3_score = _normalize_score(raw_j3)

    all_evidence = []
    all_per_item = {}
    for name, raw in [("J1", raw_j1), ("J2", raw_j2), ("J3", raw_j3)]:
        all_per_item[name] = raw.get("per_item", [])
        all_evidence.extend(raw.get("evidence", []))

    return JudgeReport(
        J1=j1_score, J2=j2_score, J3=j3_score, per_item=all_per_item, evidence=all_evidence
    )
