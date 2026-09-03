import mido

from miidi.render.midi import generate_midi
from miidi.schema.model import Composition


def sample_comp() -> Composition:
    return Composition(
        meta={"title": "Test Song", "bpm": 100},
        tracks=[
            {
                "name": "Lead",
                "program": 73,
                "role": "melody",
                "notes": [[0, 240, 69, 96], [240, 240, 71, 96]],
            },
            {
                "name": "Drums",
                "role": "drums",
                "is_drum": True,
                "notes": [[0, 120, 36, 100], [240, 120, 38, 100]],
            },
        ],
    )


def collect(path):
    mid = mido.MidiFile(path)
    notes, programs = [], []
    for track in mid.tracks:
        t = 0
        for msg in track:
            t += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                notes.append((msg.channel, msg.note, t))
            elif msg.type == "program_change":
                programs.append((msg.channel, msg.program))
    return notes, programs


def test_roundtrip(tmp_path):
    path = generate_midi(sample_comp(), tmp_path)
    notes, programs = collect(path)
    assert (0, 69, 0) in notes and (0, 71, 240) in notes
    assert (9, 36, 0) in notes and (9, 38, 240) in notes
    assert (0, 73) in programs


def test_tempo_written(tmp_path):
    path = generate_midi(sample_comp(), tmp_path)
    mid = mido.MidiFile(path)
    tempos = [m.tempo for tr in mid.tracks for m in tr if m.type == "set_tempo"]
    assert any(abs(t - mido.bpm2tempo(100)) < 2 for t in tempos)


def test_title_sanitized(tmp_path):
    comp = sample_comp().model_copy(deep=True)
    comp.meta.title = "a/b:c?"
    path = generate_midi(comp, tmp_path)
    assert "/" not in path.name and ":" not in path.name
