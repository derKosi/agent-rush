#!/usr/bin/env python3
"""Two-minute connectivity check for Vultr Serverless Inference.

    python3 models/smoke_test.py --list                 # what models exist?
    python3 models/smoke_test.py --prompt "say pong"    # one real completion

Exit codes: 0 ok, 2 missing configuration, 3 API error.
Run this first on 03.11. before writing a single line of agent logic.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import client  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="print the model catalog")
    ap.add_argument("--prompt", default=None, help="send a single chat completion")
    ap.add_argument("--model", default=None, help="override AR_MODEL")
    args = ap.parse_args()

    if not os.environ.get("AR_VULTR_KEY"):
        print("AR_VULTR_KEY is not set. cp .env.example .env, fill it, then: "
              "set -a && . ./.env && set +a", file=sys.stderr)
        return 2

    print(f"base: {client._base()}")
    try:
        if args.list or not args.prompt:
            catalog = client.list_models()
            data = catalog.get("data", catalog) if isinstance(catalog, dict) else catalog
            ids = [m.get("id") for m in data if isinstance(m, dict)]
            print(f"models: {len(ids)}")
            for mid in ids:
                print(f"  - {mid}")
            if not args.prompt:
                print("\nnext: export AR_MODEL=<id above>  then --prompt \"ping\"")

        if args.prompt:
            model = args.model or os.environ.get("AR_MODEL")
            if not model:
                print("AR_MODEL is not set -- pick one from --list", file=sys.stderr)
                return 2
            reply = client.chat(
                [{"role": "user", "content": args.prompt}], model=model, max_tokens=64
            )
            print(f"model: {model}")
            print(f"reply: {reply!r}")
    except client.InferenceError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
