from __future__ import annotations

import json

from miidi.eval.score import evaluate_rules
from miidi.eval.style import StyleDefaults
from miidi.llm.client import LLMClient
from miidi.pipeline.brief import MusicBrief
from miidi.pipeline.prompts import (
    compose_system, compose_user, plan_system, plan_user, review_system,
    review_user,
)
from miidi.schema.model import Composition, Section, Track
from miidi.schema.normalize import normalize_raw
from miidi.schema.validate import validate_composition
from miidi.skills.loader import StylePack


class StageError(RuntimeError):
    pass


def _to_music_brief(raw: dict, pack: StylePack) -> tuple[MusicBrief, list[str]]:
    notes: list[str] = []
    cursor = 0
    fixed_sections = []
    for s in raw.get("structure", []):
        start = s.get("start_bar")
        if not isinstance(start, int) or start != cursor:
            start = cursor
            notes.append(f"section {s.get('name')!r}: start_bar repaired to {cursor}")
        fixed = dict(s)
        fixed["start_bar"] = start
        fixed_sections.append(fixed)
        cursor = start + int(s.get("bars", 0))
    raw["structure"] = fixed_sections
    lo, hi = pack.defaults.bpm_range
    bpm = raw.get("bpm")
    if isinstance(bpm, int) and not lo <= bpm <= hi:
        clamped = max(int(lo), min(int(hi), bpm))
        notes.append(f"bpm {bpm} outside style range; clamped to {clamped}")
        raw["bpm"] = clamped
    brief = MusicBrief.model_validate(raw)
    errors = MusicBrief.validate_symbols(brief.harmony)
    return brief, errors + notes


def make_brief(client: LLMClient, pack: StylePack, user_prompt: str) -> MusicBrief:
    last_notes: list[str] = []
    for attempt in range(2):
        system = plan_system(pack)
        user = plan_user(user_prompt, pack)
        if last_notes:
            user += ("\nPREVIOUS ATTEMPT REJECTED:\n" + "\n".join(last_notes)
                     + "\nFix these and return the full corrected JSON.")
        raw = client.respond_json(system, user)
        try:
            brief, notes = _to_music_brief(raw, pack)
        except Exception as exc:
            last_notes = [f"schema/validation error: {exc}"]
            continue
        hard_errors = [n for n in notes if n.startswith("chord")]
        if hard_errors:
            last_notes = hard_errors
            continue
        return brief
    raise StageError(f"planner failed after retry: {last_notes}")


def build_context(kind: str, tracks: dict[str, Track]) -> str:
    blocks = []
    for name, t in tracks.items():
        if t.is_drum:
            continue
        if kind == "full":
            rows = [[o, d, p, v] for o, d, p, v in t.notes]
            blocks.append(f"{name} ({t.role}) notes: {rows}")
        else:
            bar = 1920
            hist: dict[int, set[int]] = {}
            for o, d, p, _v in t.notes:
                hist.setdefault(o // bar, set()).add(p % 12)
            pretty = ", ".join(f"bar{b}:{sorted(pcs)}" for b, pcs in sorted(hist.items())[:16])
            blocks.append(f"{name} ({t.role}) per-bar pitch classes: {pretty}")
    return "\n".join(blocks)


def compose_track(client: LLMClient, pack: StylePack, brief: MusicBrief,
                  spec, context_block: str) -> tuple[Track, list[str]]:
    spec_dict = spec.model_dump() if hasattr(spec, "model_dump") else dict(spec)
    feedback: list[str] = []
    for attempt in range(3):
        raw = client.respond_json(
            compose_system(spec_dict, pack),
            compose_user(brief.brief_json(), spec_dict, context_block))
        merged = {**spec_dict, "notes": raw.get("notes", [])}
        result = normalize_raw({
            "meta": json.loads(brief.brief_json()),
            "tracks": [merged],
        })
        if result.composition is None or not result.composition.tracks:
            feedback = result.errors[:10] or ["unparseable notes"]
            continue
        skeleton = result.composition
        viols = validate_composition(skeleton)
        if viols:
            feedback = [f"{v.location}: {v.message}" for v in viols][:10]
            continue
        return skeleton.tracks[0], result.repairs
    raise StageError(f"track {spec_dict.get('name')!r} failed: {feedback}")


def _report_text(comp: Composition, defaults: StyleDefaults) -> str:
    report = evaluate_rules(comp, defaults)
    if report.invalid:
        return "INVALID COMPOSITION:\n" + "\n".join(
            f"{v.location}: {v.message}" for v in report.violations[:12])
    axis_lines = [f"{k}={v.score:.2f}" for k, v in report.axes.items()]
    gate_lines = [f"G_{k}={v:.2f}" for k, v in report.gates.items()]
    viol_lines = [f"- {v.location}: {v.message}" for v in report.violations][:12]
    parts = [f"R_rule={report.R_rule:.1f}",
             "axes: " + ", ".join(axis_lines),
             "gates: " + ", ".join(gate_lines)]
    if viol_lines:
        parts.append("violations:")
        parts.extend(viol_lines)
    else:
        parts.append("violations: none listed")
    return "\n".join(parts)


def self_review(client: LLMClient, comp: Composition, defaults: StyleDefaults,
                max_rounds: int = 2) -> tuple[Composition, list[dict]]:
    current = comp
    trajectory: list[dict] = []
    prev_score = float("-inf")
    for round_index in range(max_rounds):
        report = evaluate_rules(current, defaults)
        trajectory.append({"round": round_index, "R_rule": round(report.R_rule, 2)})
        if report.invalid:
            trajectory[-1]["action"] = "invalid composition; review stopped"
            break
        if report.R_rule - prev_score < 1.0 and round_index > 0:
            break
        prev_score = report.R_rule
        options = [t.name for t in current.tracks if not t.is_drum] or \
                  [t.name for t in current.tracks]
        try:
            reply = client.respond_json(
                review_system(),
                review_user(_report_text(current, defaults), options,
                            json.dumps(current.meta.model_dump())))
        except Exception as exc:
            trajectory[-1]["action"] = f"review aborted: {exc}"
            break
        track_name = reply.get("track")
        notes = reply.get("notes")
        if not track_name or not isinstance(notes, list):
            trajectory[-1]["action"] = "kept"
            break
        target = next((t for t in current.tracks if t.name == track_name), None)
        if target is None:
            trajectory[-1]["action"] = f"unknown track {track_name!r}; kept"
            break
        spec = {"name": target.name, "program": target.program,
                "role": target.role, "is_drum": target.is_drum}
        result = normalize_raw({
            "meta": current.meta.model_dump(),
            "tracks": [{**spec, "notes": notes}],
        })
        if (result.composition is None or not result.composition.tracks
                or validate_composition(result.composition)):
            trajectory[-1]["action"] = "patch rejected; kept"
            break
        patched_track = result.composition.tracks[0]
        new_tracks = [patched_track if t.name == track_name else t
                      for t in current.tracks]
        current = current.model_copy(update={"tracks": new_tracks})
        trajectory[-1]["action"] = f"patched {track_name}"
    return current, trajectory
