"""导出会话快照为静态 demo 站点的罐头数据（docs/demo 用，GitHub Pages）。

用法：
    py tools/export_demo_session.py 20260912-023141-7020 \
        --out web/demo --evaluate --states 1,2,4,5

- --states：demo 状态机各阶段对应的版本号（plan,core,arrange,revise）
- --evaluate：对 arrange 与 revise 两个版本现场执行规则轨 + LLM Judge 评估
  （真实 API 调用），产出与 POST /evaluate 端点一致的 {report, composite} 结构
- 产物：web/demo/demo-data.js（window.MIIDI_DEMO_DATA）+ demo.mid（最终版渲染）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


def _load_env_dotenv() -> None:
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sid", help="sessions/ 下的会话 ID")
    parser.add_argument("--out", type=Path, default=Path("web/demo"))
    parser.add_argument("--evaluate", action="store_true", help="现场评估 arrange/revise 版本")
    parser.add_argument(
        "--states", default="1,2,4,5", help="demo 状态机版本号：plan,core,arrange,revise"
    )
    args = parser.parse_args()

    session_dir = REPO_ROOT / "sessions" / args.sid
    meta = json.loads((session_dir / "meta.json").read_text())
    plan_v, core_v, arrange_v, revise_v = (int(x) for x in args.states.split(","))

    def load_version(n: int) -> dict:
        return json.loads((session_dir / f"v{n}.json").read_text())

    versions = []
    for n in sorted(int(p.stem[1:]) for p in session_dir.glob("v*.json")):
        v = load_version(n)
        versions.append({"version": n, "label": v.get("label", ""), "composition": v["composition"]})

    evals: dict[str, dict] = {}
    if args.evaluate:
        _load_env_dotenv()
        from miidi.eval.composite import compute_composite
        from miidi.eval.judge import evaluate_judge
        from miidi.eval.score import evaluate_rules
        from miidi.llm.client import LLMClient, load_config
        from miidi.schema.model import Composition
        from miidi.skills.loader import load_style_pack

        client = LLMClient(load_config())
        style = meta["style"]
        pack = load_style_pack(style)
        for n in (arrange_v, revise_v):
            comp = Composition.model_validate(load_version(n)["composition"])
            report = evaluate_rules(comp, pack.defaults)
            judge = evaluate_judge(comp, report, client, style, prompt=meta["prompt"])
            evals[str(n)] = {
                "report": report.to_dict(),
                "composite": compute_composite(report, judge).to_dict(),
            }
            print(f"evaluated v{n}: composite={evals[str(n)]['composite']['composite']}")
        client.close()

    data = {
        "session": {
            "sid": f"demo-{args.sid}",
            "prompt": meta["prompt"],
            "style": meta["style"],
            "created": meta.get("created", ""),
            "versions": versions,
        },
        "stateVersions": {"plan": plan_v, "core": core_v, "arrange": arrange_v, "revise": revise_v},
        "evals": evals,
    }

    args.out.mkdir(parents=True, exist_ok=True)
    data_js = "window.MIIDI_DEMO_DATA = " + json.dumps(data, ensure_ascii=False) + ";\n"
    (args.out / "demo-data.js").write_text(data_js)
    print(f"wrote {args.out / 'demo-data.js'} ({len(data_js) // 1024} KB)")

    # 最终版本渲染 MIDI，供 demo 站点静态下载
    from miidi.render.midi import generate_midi
    from miidi.schema.model import Composition

    comp = Composition.model_validate(load_version(revise_v)["composition"])
    midi_path = generate_midi(comp, args.out)
    target = args.out / "demo.mid"
    if midi_path != target:
        midi_path.replace(target)
    print(f"wrote {target}")


if __name__ == "__main__":
    main()
