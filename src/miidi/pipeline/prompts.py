from __future__ import annotations

from miidi.skills.loader import StylePack

_JSON_ONLY = (
    "Output ONLY a single JSON object matching the schema. "
    "No markdown fences, no commentary, no trailing text."
)

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


def compose_user(
    brief_json: str, track_spec: dict, context_block: str, piece_end_tick: int | None = None
) -> str:
    boundary = ""
    if piece_end_tick is not None:
        boundary = (
            f"\nPIECE BOUNDARY: all notes must end at or before tick {piece_end_tick}. "
            f"Any note with onset + duration > {piece_end_tick} will be rejected.\n"
        )
    return (
        f"MUSICAL PLAN\n{brief_json}\n\n"
        f"YOUR TRACK\n{track_spec['name']} (role {track_spec.get('role')})\n\n"
        f"CONTEXT FROM OTHER TRACKS\n{context_block or '(you start first — nothing yet)'}\n"
        f"{boundary}\n"
        "Write the whole track over the full structure length.\n"
        'Output ONLY {"notes": [[onset,dur,pitch,velocity], ...]}'
    )


def review_system() -> str:
    return (
        "You are a meticulous composition fixer. You receive an evaluation report "
        "listing concrete violations and the current plan. Choose ONE track worth "
        "rewriting to fix the worst issues, and output its complete replacement notes.\n"
        f"GRID RULES\n{_GRID_RULES}\n\n"
        "Respond ONLY with a single JSON object: either "
        '{"track": "<name>", "notes": [[onset,dur,pitch,velocity], ...]} '
        'or {"track": null} when nothing is worth changing.'
    )


def review_user(report_text: str, track_options: list[str], brief_json: str) -> str:
    opts = ", ".join(track_options)
    return (
        f"EVALUATION REPORT\n{report_text}\n\n"
        f"CANDIDATE TRACKS: {opts}\n\nMUSICAL PLAN\n{brief_json}\n\n"
        "Fix the highest-impact violations. Output ONLY the JSON decision: "
        '{"track": "<name>", "notes": [...]} or {"track": null}.'
    )


def classify_revision_system() -> str:
    return (
        "You route a user's revision request for a generated song to the right layer.\n"
        'Respond ONLY JSON: {"layer": "track|harmony|structure|regenerate", '
        '"track": "<name>" or null}\n'
        "- 'track': feedback targets ONE instrument's performance (density, register, "
        "pattern, feel). Set track to that instrument's name.\n"
        "- 'harmony': feedback targets chord choices/progression.\n"
        "- 'structure': feedback targets form/section layout.\n"
        "- 'regenerate': anything else or ambiguous."
    )


def classify_revision_user(feedback: str, track_names: list[str]) -> str:
    return f"TRACKS: {', '.join(track_names)}\nFEEDBACK: {feedback}"


def arrange_coordinate_system(pack: StylePack) -> str:
    return (
        "You are an arrangement coordinator for a multi-track composition. "
        "Your job: identify coordination problems between tracks and output "
        "adjustment commands. You do NOT rewrite notes — you make structural "
        "decisions about the arrangement.\n\n"
        f"STYLE — {pack.name.title()}\n{_style_identity(pack)}\n\n"
        "ANALYSIS FRAMEWORK — for each section, assess:\n\n"
        "1. FREQUENCY BALANCE: Which MIDI register does each track occupy?\n"
        "   - Bass: C2-C4 (MIDI 24-48)\n"
        "   - Mid: C4-C6 (MIDI 48-72)\n"
        "   - High: C6-C8 (MIDI 72-96)\n"
        "   Are two non-bass tracks competing in the same register?\n\n"
        "2. SECTIONAL DENSITY: Count notes per bar per section.\n"
        "   - Sparse: <4 notes/bar (may need filling)\n"
        "   - Normal: 4-12 notes/bar\n"
        "   - Dense: >12 notes/bar (may need thinning)\n"
        "   Is the density appropriate for the section type?\n\n"
        "3. ROLE CLARITY: In each section, is ONE track clearly the melodic "
        "focus? Or are multiple tracks competing for attention?\n\n"
        "4. REDUNDANCY: Are two tracks playing similar rhythms or pitches "
        "in the same section?\n\n"
        "AVAILABLE ADJUSTMENT TOOLS:\n"
        "- section_mute: Silence a track in a specific bar range\n"
        "- octave_shift: Move a track up/down 12 semitones\n"
        "- density_reduce: Thin out notes in a section (factor=0.5 = keep half)\n\n"
        f"{_JSON_ONLY}"
    )


def arrange_coordinate_user(comp_dict: dict) -> str:
    """Build user prompt from a composition dict."""
    import json

    from miidi.schema.model import PPQ

    time_sig = comp_dict.get("meta", {}).get("time_signature", [4, 4])
    num, den = time_sig[0], time_sig[1]
    bar_ticks = int(PPQ * 4 * num / den)
    tracks_info = []
    for t in comp_dict.get("tracks", []):
        notes = t.get("notes", [])
        bar_counts: dict[int, int] = {}
        for n in notes:
            bar = n[0] // bar_ticks
            bar_counts[bar] = bar_counts.get(bar, 0) + 1
        pitches = [n[2] for n in notes] if notes else []
        pitch_range = f"{min(pitches)}-{max(pitches)}" if pitches else "N/A"
        tracks_info.append(
            {
                "name": t.get("name", "?"),
                "role": t.get("role", "?"),
                "note_count": len(notes),
                "pitch_range": pitch_range,
                "bars_sample": {f"bar{k}": v for k, v in sorted(bar_counts.items())[:16]},
            }
        )

    sections = []
    cursor = 0
    for s in comp_dict.get("structure", []):
        bars = s.get("bars", 4)
        sections.append({"name": s.get("name"), "start_bar": cursor, "end_bar": cursor + bars})
        cursor += bars

    return (
        f"MUSICAL PLAN\n{json.dumps(comp_dict.get('meta', {}), indent=2)}\n\n"
        f"STRUCTURE\n{json.dumps(sections, indent=2)}\n\n"
        f"TRACKS\n{json.dumps(tracks_info, indent=2)}\n\n"
        "Analyze each section for frequency balance, density, role clarity, "
        "and redundancy. Output adjustment commands.\n\n"
        "OUTPUT SCHEMA:\n"
        '{"analysis": {"<section>": {"frequency_balance": "...", '
        '"density": "sparse|normal|dense", "role_clarity": "...", '
        '"redundancy": "..."}}, "adjustments": [{"action": "section_mute|'
        'octave_shift|density_reduce", "track": "<name>", ...}]}\n\n'
        f"{_JSON_ONLY}"
    )
