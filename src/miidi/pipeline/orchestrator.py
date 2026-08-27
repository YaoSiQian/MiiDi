from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from miidi.pipeline.brief import InstrumentSpec, MusicBrief
from miidi.pipeline.prompts import (
    classify_revision_system, classify_revision_user, compose_system,
    compose_user,
)
from miidi.pipeline.stages import (
    StageError, build_context, compose_track, make_brief, self_review,
)
from miidi.render.midi import generate_midi
from miidi.schema.model import Composition
from miidi.schema.validate import validate_composition
from miidi.session.store import SessionStore
from miidi.skills.loader import StylePack, load_style_pack

_ROLE_ORDER = ["melody", "bass", "harmony", "counter", "color", "drums"]
_CORE_ROLES = {"melody", "bass", "drums"}
_ARRANGE_ROLES = {"harmony", "counter", "color"}
_ALL_STAGES = {"plan", "core", "arrange"}


@dataclass
class PipelineResult:
    comp: Composition | None
    brief: MusicBrief | None
    midi_path: Path | None
    trajectory: list[dict] = field(default_factory=list)
    stage_log: list[str] = field(default_factory=list)
    sid: str | None = None


def _context_for(role: str, prior: dict) -> str:
    if not prior:
        return ""
    if role in ("bass", "harmony"):
        mel = {n: t for n, t in prior.items() if t.role == "melody"}
        if mel:
            return build_context("full", mel)
        return build_context("full", prior)
    if role in ("counter", "color"):
        return build_context("pc_summary", prior)
    return ""


def _aborted_reason(trajectory: list[dict]) -> str | None:
    for entry in reversed(trajectory):
        action = entry.get("action")
        if isinstance(action, str) and action.startswith("review aborted:"):
            return action.split(":", 1)[1].strip()
    return None


def _compose_tracks(client, pack, brief, comp, specs, roles, log):
    """Compose tracks whose role is in `roles`. Returns updated comp + prior dict."""
    ordered = sorted(
        [s for s in specs.values() if s.role in roles],
        key=lambda s: (_ROLE_ORDER.index(s.role) if s.role in _ROLE_ORDER else 3),
    )
    prior: dict[str, object] = {}
    for spec in ordered:
        ctx = _context_for(spec.role, prior)
        track, repairs = compose_track(client, pack, brief, spec, ctx)
        prior[track.name] = track
        comp = comp.model_copy(update={
            "tracks": [track if t.name == track.name else t for t in comp.tracks]})
        log.append(f"composed {track.name}" + (f" ({len(repairs)} repairs)" if repairs else ""))
    return comp, prior


def run_pipeline(user_prompt: str, style: str, client,
                 out_dir: Path | None = None, max_review_rounds: int = 2,
                 store: SessionStore | None = None,
                 stages: list[str] | None = None) -> PipelineResult:
    """Run the generation pipeline.

    stages controls which phases execute:
      None or ["plan","core","arrange"] → full pipeline (backward-compatible)
      ["plan"]         → brief + structure + key only
      ["plan","core"]  → brief + melody/bass/drums
      ["plan","core","arrange"] → full
    """
    if stages is None:
        stages = ["plan", "core", "arrange"]
    invalid = set(stages) - _ALL_STAGES
    if invalid:
        raise ValueError(f"invalid stages: {invalid}")

    log: list[str] = []
    pack: StylePack = load_style_pack(style)
    sid = store.create(user_prompt, style) if store is not None else None

    # ── Stage: plan ──────────────────────────────────────────────
    try:
        brief = make_brief(client, pack, user_prompt)
    except Exception as exc:
        log.append(f"brief failed: {exc}")
        return PipelineResult(comp=None, brief=None, midi_path=None,
                              stage_log=log, sid=sid)
    log.append("plan: brief ok")
    comp = brief.to_skeleton()

    if stages == ["plan"]:
        if store is not None:
            store.save_version(sid, "planned", comp, {"brief": brief.model_dump()})
            log.append(f"session {sid}: saved planned")
        return PipelineResult(comp=comp, brief=brief, midi_path=None,
                              stage_log=log, sid=sid)

    # ── Stage: core (melody + bass + drums) ──────────────────────
    specs = {s.name: s for s in brief.instruments}
    try:
        comp, core_prior = _compose_tracks(
            client, pack, brief, comp, specs, _CORE_ROLES, log)
    except Exception as exc:
        log.append(f"core failed: {exc}")
        return PipelineResult(comp=None, brief=brief, midi_path=None,
                              stage_log=log, sid=sid)
    log.append("core: done")

    if store is not None:
        store.save_version(sid, "core", comp, None)
        log.append(f"session {sid}: saved core")

    if stages == ["plan", "core"]:
        midi_path = None
        if out_dir is not None:
            midi_path = generate_midi(comp, Path(out_dir))
            log.append(f"midi written: {midi_path}")
        return PipelineResult(comp=comp, brief=brief, midi_path=midi_path,
                              stage_log=log, sid=sid)

    # ── Stage: arrange (harmony + counter + color) ───────────────
    try:
        comp, _ = _compose_tracks(
            client, pack, brief, comp, specs, _ARRANGE_ROLES, log)
    except Exception as exc:
        log.append(f"arrange failed: {exc}")
        return PipelineResult(comp=None, brief=brief, midi_path=None,
                              stage_log=log, sid=sid)
    log.append("arrange: done")
    assembled = comp

    if store is not None:
        store.save_version(sid, "assembled", assembled, None)
        log.append(f"session {sid}: saved assembled")

    # ── Self-review ──────────────────────────────────────────────
    try:
        reviewed, trajectory = self_review(client, assembled, pack.defaults,
                                           max_rounds=max_review_rounds)
    except Exception as exc:
        log.append(f"self-review failed: {exc}")
        reviewed, trajectory = assembled, []
    else:
        aborted = _aborted_reason(trajectory)
        if aborted is not None:
            log.append(f"self-review failed: {aborted}")
            trajectory = []
        else:
            log.append(f"self-review done ({len(trajectory)} rounds)")

    violations = validate_composition(reviewed)
    if violations:
        log.append("validation failed")
        log.extend(f"{v.location}: {v.message}" for v in violations[:10])
        return PipelineResult(comp=reviewed, brief=brief, midi_path=None,
                              trajectory=trajectory, stage_log=log, sid=sid)

    if store is not None:
        store.save_version(sid, "reviewed", reviewed,
                           {"trajectory": trajectory})
        log.append("saved reviewed version")

    midi_path = None
    if out_dir is not None:
        midi_path = generate_midi(reviewed, Path(out_dir))
        log.append(f"midi written: {midi_path}")
    return PipelineResult(comp=reviewed, brief=brief, midi_path=midi_path,
                          trajectory=trajectory, stage_log=log, sid=sid)


def revise(store: SessionStore, client, sid: str, feedback: str,
           out_dir: Path | None = None) -> PipelineResult:
    meta = store.session_meta(sid)
    latest = store.load_composition(sid, store.latest(sid))
    pack = load_style_pack(meta["style"])
    track_names = [t.name for t in latest.tracks]
    routing = client.respond_json(classify_revision_system(),
                                  classify_revision_user(feedback, track_names))
    layer = routing.get("layer", "regenerate")
    target = routing.get("track")

    if layer == "track" and target in track_names:
        spec = next(s for s in _specs_from(latest) if s.name == target)
        context = f"{build_context('pc_summary', {t.name: t for t in latest.tracks})}\nUSER FEEDBACK: {feedback}"
        track, _repairs = compose_track(client, pack, _brief_from_comp(latest), spec, context)
        updated = latest.model_copy(update={
            "tracks": [track if t.name == target else t for t in latest.tracks]})
        version = store.save_version(sid, "revised", updated, {"feedback": feedback})
        midi_path = generate_midi(updated, out_dir) if out_dir else None
        return PipelineResult(comp=updated, brief=_brief_from_comp(latest),
                              midi_path=midi_path,
                              stage_log=[f"revised track {target} as v{version}"],
                              sid=sid)

    merged_prompt = meta["prompt"] + "\nRevision request: " + feedback
    result = run_pipeline(merged_prompt, meta["style"], client, out_dir=out_dir)
    gated = "validation failed" in result.stage_log
    if result.comp is not None and not gated:
        version = store.save_version(sid, "revised-regenerated", result.comp,
                                     {"feedback": feedback,
                                      "trajectory": result.trajectory})
        result.stage_log.append(f"saved revised-regenerated v{version} under {sid}")
    elif gated:
        result.stage_log.append("regeneration rejected by whole-piece validation; "
                                "nothing persisted")
    result.sid = sid
    return result


def _specs_from(comp: Composition) -> list[InstrumentSpec]:
    role_hints = {"melody": "carry the tune", "bass": "support roots",
                  "drums": "groove"}
    return [InstrumentSpec(name=t.name, program=t.program, role=t.role,
                           description=role_hints.get(t.role, ""))
            for t in comp.tracks]


def _brief_from_comp(comp: Composition) -> MusicBrief:
    return MusicBrief(
        title=comp.meta.title, bpm=comp.meta.bpm,
        time_signature=comp.meta.time_signature,
        tonic_pc=comp.meta.key.tonic_pc, mode=comp.meta.key.mode,
        structure=comp.structure, harmony=comp.harmony,
        instruments=[InstrumentSpec(name=t.name, program=t.program,
                                    role=t.role, description="")
                     for t in comp.tracks],
    )
