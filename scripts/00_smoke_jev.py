"""Fase 1 - Smoke test do JEV: 1 lead -> imprime answers e usage.

Uso:
    uv run python scripts/00_smoke_jev.py            # chamada real (usa .env)
    uv run python scripts/00_smoke_jev.py --fixture  # le outputs/fixtures/jev_response.json
    uv run python scripts/00_smoke_jev.py --save-fixture  # chama e salva o fixture

Na segunda execucao real, a resposta vem do cache (custo incremental $0).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jevlab.core.config import CSV_PATH, REPO_ROOT, get_settings  # noqa: E402
from jevlab.core.jev_client import JevClient, validate_answers  # noqa: E402
from jevlab.core.questions import get_catalog, get_questions  # noqa: E402
from jevlab.pipeline.load import load_raw_csv  # noqa: E402
from jevlab.pipeline.state_builder import build_state  # noqa: E402

FIXTURE = REPO_ROOT / "outputs" / "fixtures" / "jev_response.json"


def sample_state() -> dict:
    df = load_raw_csv(CSV_PATH)
    settings = get_settings()
    return build_state(df.iloc[0].to_dict(), mask_pii=settings.mask_pii)


def print_result(result: dict, questions: dict) -> None:
    print("=" * 78)
    print(f"model    : {result.get('model')}")
    print(f"provider : {result.get('provider')}")
    print(f"id       : {result.get('id')}")
    print(f"cached   : {result.get('cached')}")
    usage = result.get("usage") or {}
    print(
        "usage    : input_tokens={} output_tokens={} cost=${}".format(
            usage.get("input_tokens"),
            usage.get("output_tokens"),
            usage.get("cost"),
        )
    )
    print("=" * 78)
    for name, answer in result["answers"].items():
        qtype = questions[name]["type"] if name in questions else answer.get("type")
        if answer.get("type") == "noul":
            print(f"  {name:24s} [noul]   {answer['noul']:.4f}")
        elif answer.get("type") == "choice":
            conf = answer.get("confidence")
            conf_txt = f"{conf:.3f}" if conf is not None else "n/a"
            print(f"  {name:24s} [choice] {answer['choice']:15s} conf={conf_txt}")
        elif answer.get("type") == "score":
            conf = answer.get("confidence")
            conf_txt = f"{conf:.3f}" if conf is not None else "n/a"
            print(f"  {name:24s} [score]  {answer['score']:.3f}       conf={conf_txt}")
        else:  # pragma: no cover
            print(f"  {name:24s} [???] {answer}")
    print("=" * 78)


async def run(args: argparse.Namespace) -> int:
    settings = get_settings()
    catalog = get_catalog()
    questions = get_questions()

    if args.fixture:
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        answers = validate_answers(data["answers"], questions)
        result = {
            "id": data.get("id"),
            "model": data.get("model"),
            "provider": data.get("provider"),
            "usage": data.get("usage", {}),
            "answers": answers,
            "cached": False,
        }
        print(f"[fixture] {FIXTURE} (sem rede)")
        print_result(result, questions)
        return 0

    state = sample_state()
    print("STATE enviado:")
    print(json.dumps(state, ensure_ascii=False, indent=2))
    print(f"Perguntas: {len(catalog.questions)} ({', '.join(catalog.question_names())})")

    async with JevClient(settings=settings) as client:
        result = await client.evaluate(state, questions=questions)

    print_result(result, questions)

    if args.save_fixture:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(
            json.dumps(
                {
                    "id": result.get("id"),
                    "model": result.get("model"),
                    "provider": result.get("provider"),
                    "answers": result["answers"],
                    "usage": result.get("usage"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Fixture salvo em {FIXTURE}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test do JEV")
    parser.add_argument("--fixture", action="store_true", help="usa o fixture (offline)")
    parser.add_argument(
        "--save-fixture", action="store_true", help="salva a resposta real como fixture"
    )
    args = parser.parse_args()
    try:
        return asyncio.run(run(args))
    except RuntimeError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
