from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError


def _make_default_client():
    from miidi.llm.client import LLMClient, load_config

    return LLMClient(load_config())


def cmd_generate(args) -> int:
    from miidi.pipeline.orchestrator import run_pipeline

    try:
        client = _make_default_client()
    except Exception as exc:
        print(f"client init failed: {exc}", file=sys.stderr)
        return 1
    result = run_pipeline(
        args.prompt,
        args.style,
        client,
        out_dir=Path(args.out) if args.out else None,
        max_review_rounds=0 if args.no_review else args.rounds,
        stages=args.stages.split(",") if args.stages else None,
    )
    for line in result.stage_log:
        print(line)
    if result.comp is None:
        return 1
    from miidi.eval.score import evaluate_rules
    from miidi.skills.loader import load_style_pack

    report = evaluate_rules(result.comp, load_style_pack(args.style).defaults)
    print(f"R_rule={report.R_rule:.2f}")
    print(json.dumps(report.to_dict()["axes"], ensure_ascii=False, indent=1))
    return 0


def cmd_styles(_args) -> int:
    from miidi.skills.loader import available_styles

    print("\n".join(available_styles()))
    return 0


def cmd_evaluate(args) -> int:
    from miidi.eval.score import evaluate_rules
    from miidi.schema.model import Composition

    raw = json.loads(Path(args.json).read_text(encoding="utf-8"))
    try:
        comp = Composition.model_validate(raw)
    except ValidationError as exc:
        print(f"invalid composition: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(evaluate_rules(comp).to_dict(), ensure_ascii=False, indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="miidi")
    sub = parser.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate")
    g.add_argument("--style", required=True)
    g.add_argument("--prompt", required=True)
    g.add_argument("--out", default=None)
    g.add_argument("--rounds", type=int, default=2)
    g.add_argument("--no-review", action="store_true")
    g.add_argument(
        "--stages", default=None, help="Comma-separated stages: plan,core,arrange (default: all)"
    )
    g.set_defaults(func=cmd_generate)

    s = sub.add_parser("styles")
    s.set_defaults(func=cmd_styles)

    e = sub.add_parser("evaluate")
    e.add_argument("--json", required=True)
    e.set_defaults(func=cmd_evaluate)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
