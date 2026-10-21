"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from clinical_doc_assist.agent import ClinicalDocumentationAgent
from clinical_doc_assist.config import Settings, SettingsError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clinical-doc-assist",
        description="Draft clinical documentation with a DeepSeek-powered agent.",
    )
    parser.add_argument(
        "prompt",
        nargs="*",
        help="Prompt to send once. Omit it to start an interactive session.",
    )
    return parser


def _interactive(agent: ClinicalDocumentationAgent) -> int:
    print("Clinical Doc Assist. Type /exit to quit or /reset to clear the conversation.")
    while True:
        try:
            prompt = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not prompt:
            continue
        if prompt == "/exit":
            return 0
        if prompt == "/reset":
            agent.reset()
            print("Conversation reset.")
            continue

        try:
            reply = agent.run(prompt)
        except Exception as exc:
            print(f"Agent error: {exc}", file=sys.stderr)
            continue
        print(f"\nAssistant:\n{reply.text}")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        agent = ClinicalDocumentationAgent.from_settings(Settings.from_env())
    except SettingsError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    prompt = " ".join(args.prompt).strip()
    if not prompt:
        return _interactive(agent)

    try:
        reply = agent.run(prompt)
    except Exception as exc:
        print(f"Agent error: {exc}", file=sys.stderr)
        return 1
    print(reply.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

