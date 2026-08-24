from __future__ import annotations

from miidi.skills.loader import StylePack

_JSON_ONLY = ("Output ONLY a single JSON object matching the schema. "
              "No markdown fences, no commentary, no trailing text.")

_BRIEF_SCHEMA = """{
  "title": "string",
  "bpm": integer,
  "time_signature": [numerator, denominator],
  "tonic_pc": 0-11,
  "mode": "major" or "minor",
  "structure": [{"name": "intro|verse|chorus|bridge|outro|...", "start_bar": 0, "bars": 4}],
  "harmony": [{"bar": 0, "dur_bars": 1.0, "symbol": "C"}],
  "instruments": [{"name": "Lead", "program": 73,
                   "role": "melody|harmony|bass|counter|color|drums",
                   "description": "one line of musical intent"}]
}"""

_GRID_RULES = (
    "Time is integer ticks on the ppq=480 grid (quarter=480, eighth=240, sixteenth=120, "
    "eighth-triplet=160). Notes are [onset_tick, duration_tick, midi_pitch, velocity]. "
    "Rests are gaps between notes. Chords inside one track are several entries sharing "
    "the same onset. Velocity is 1-127 and must vary musically."
)


def _style_identity(pack: StylePack) -> str:
    lines = pack.skill_md.splitlines()
    keep = []
    grab = False
    for line in lines:
        if line.startswith("## Identity"):
            grab = True
            continue
        if grab and line.startswith("## "):
            break
        if grab:
            keep.append(line)
    return "\n".join(keep).strip()


def plan_system(pack: StylePack) -> str:
    return (
        "You are an expert music planner. Given a natural-language request you design "
        "a piece: tempo, key, section structure, chord timeline, and instrument roster.\n\n"
        f"STYLE — {pack.name.title()}\n{_style_identity(pack)}\n\n"
        f"BRIEF SCHEMA\n{_BRIEF_SCHEMA}\n\n"
        "Rules:\n"
        "- structure sections must tile the song contiguously starting at bar 0 (start_bar of "
        "each equals previous start_bar + bars).\n"
        "- harmony symbols must be plain chord symbols (C, Am, Fmaj7, Bm7b5...). No slash "
        "chords, no 9/11/13 extensions.\n"
        "- instruments: 3 to 6 entries covering at least one 'melody', one 'bass', one "
        "'harmony'; drums entry uses role 'drums'.\n"
        f"- bpm inside the style's typical range given in the request.\n"
        f"{_JSON_ONLY}"
    )


def plan_user(user_prompt: str, pack: StylePack) -> str:
    d = pack.defaults
    lo, hi = int(d.bpm_range[0]), int(d.bpm_range[1])
    vocab = pack.harmony_md[:1600]
    return (
        f"REQUEST:\n{user_prompt}\n\n"
        f"Typical BPM range for {pack.name}: {lo}-{hi}. Choose within it.\n\n"
        f"HARMONY VOCABULARY (use these symbols):\n{vocab}\n\n{_JSON_ONLY}"
    )


def _role_guidance(track_spec: dict, pack: StylePack) -> str:
    role = track_spec.get("role", "harmony")
    if role == "drums":
        return pack.rhythm_md[:1400]
    if role == "melody":
        return f"{pack.instruments_md[:900]}\nWrite a singable, memorable line."
    if role == "bass":
        return f"{pack.instruments_md[:900]}\nSupport the harmony root motion."
    return f"{pack.harmony_md[:900]}\nRealize the declared chords for this register."


def compose_system(track_spec: dict, pack: StylePack) -> str:
    name = track_spec.get("name", "track")
    program = track_spec.get("program", 0)
    role = track_spec.get("role", "harmony")
    desc = track_spec.get("description", "")
    return (
        f"You are a professional arranger writing ONE track: '{name}' "
        f"(GM program {program}, role '{role}'). Intent: {desc}\n\n"
        f"GRID RULES\n{_GRID_RULES}\n\n"
        f"STYLE GUIDANCE\n{_role_guidance(track_spec, pack)}\n\n"
        'Respond ONLY: {"notes": [[onset,dur,pitch,velocity], ...]}'
    )


def compose_user(brief_json: str, track_spec: dict, context_block: str) -> str:
    return (
        f"MUSICAL PLAN\n{brief_json}\n\n"
        f"YOUR TRACK\n{track_spec['name']} (role {track_spec.get('role')})\n\n"
        f"CONTEXT FROM OTHER TRACKS\n{context_block or '(you start first — nothing yet)'}\n\n"
        "Write the whole track over the full structure length.\n"
        'Output ONLY {"notes": [[onset,dur,pitch,velocity], ...]}'
    )


def review_system() -> str:
    return (
        "You are a meticulous composition fixer. You receive an evaluation report "
        "listing concrete violations and the current plan. Choose ONE track worth "
        "rewriting to fix the worst issues, and output its complete replacement notes.\n"
        f"GRID RULES\n{_GRID_RULES}\n\n"
        'Respond ONLY with a single JSON object: either '
        '{"track": "<name>", "notes": [[onset,dur,pitch,velocity], ...]} '
        'or {"track": null} when nothing is worth changing.'
    )


def review_user(report_text: str, track_options: list[str],
                brief_json: str) -> str:
    opts = ", ".join(track_options)
    return (
        f"EVALUATION REPORT\n{report_text}\n\n"
        f"CANDIDATE TRACKS: {opts}\n\nMUSICAL PLAN\n{brief_json}\n\n"
        'Fix the highest-impact violations. Output ONLY the JSON decision: '
        '{"track": "<name>", "notes": [...]} or {"track": null}.'
    )
