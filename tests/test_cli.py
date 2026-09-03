import json

from miidi.cli import main


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)

    def respond_json(self, system, user, temperature=0.0):
        return self.replies.pop(0)


BRIEF = {
    "title": "CLI",
    "bpm": 100,
    "time_signature": [4, 4],
    "tonic_pc": 0,
    "mode": "major",
    "structure": [{"name": "verse", "start_bar": 0, "bars": 2}],
    "harmony": [{"bar": 0, "dur_bars": 2.0, "symbol": "C"}],
    "instruments": [{"name": "L", "program": 73, "role": "melody", "description": ""}],
}


def test_generate_with_fake_client(monkeypatch, tmp_path, capsys):
    from miidi import cli

    fake = FakeClient(
        [
            BRIEF,
            {
                "notes": [
                    [0, 480, 72, 90],
                    [480, 480, 74, 92],
                    [960, 480, 76, 94],
                    [1440, 480, 72, 90],
                ]
            },
            {"track": None},
        ]
    )
    monkeypatch.setattr(cli, "_make_default_client", lambda: fake)
    code = main(["generate", "--style", "pop", "--prompt", "tiny", "--out", str(tmp_path)])
    assert code == 0
    out = capsys.readouterr().out
    assert "R_rule" in out


def test_styles_command(capsys):
    assert main(["styles"]) == 0
    assert "pop" in capsys.readouterr().out


def test_evaluate_command(tmp_path, capsys):
    from miidi.schema.model import Composition, Track

    comp = Composition(tracks=[Track(name="L", role="melody", notes=[(0, 480, 60, 96)])])
    p = tmp_path / "c.json"
    p.write_text(comp.model_dump_json())
    assert main(["evaluate", "--json", str(p)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "R_rule" in payload


def test_generate_failure_exit_code(monkeypatch):
    from miidi import cli

    def boom():
        raise RuntimeError("env broken")

    monkeypatch.setattr(cli, "_make_default_client", boom)
    assert main(["generate", "--style", "pop", "--prompt", "x"]) == 1
