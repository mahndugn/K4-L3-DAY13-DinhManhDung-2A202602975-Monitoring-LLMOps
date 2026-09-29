from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
from langfuse import get_client

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT_NAME = "day13-chat"
PROMPT_V1 = "Feature={{feature}}\nDocs={{docs}}\nQuestion={{message}}"
PROMPT_V2 = (
    "Feature={{feature}}\nDocs={{docs}}\nQuestion={{message}}\n"
    "Answer concisely using the available context. If it is insufficient, say so."
)


def _versions(client) -> list[int]:
    response = client.api.prompts.list(name=PROMPT_NAME, limit=100)
    rows = [row for row in response.data if row.name == PROMPT_NAME]
    return sorted({version for row in rows for version in row.versions})


def _show(client) -> int:
    versions = _versions(client)
    if not versions:
        print(f"Prompt '{PROMPT_NAME}' is not present in the configured Langfuse project.")
        return 1
    for version in versions:
        prompt = client.get_prompt(PROMPT_NAME, version=version, type="text")
        labels = sorted(getattr(prompt, "labels", []) or [])
        print(f"{PROMPT_NAME} v{version}: labels={','.join(labels) or '(none)'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage Day 13 Langfuse prompt versions")
    parser.add_argument(
        "action",
        choices=("inspect", "initialize", "promote-v2", "rollback-v1"),
        help="Inspect versions, create the initial v1/v2 pair, promote v2, or rollback to v1.",
    )
    args = parser.parse_args()
    load_dotenv(REPO_ROOT / ".env", override=False)
    client = get_client()

    if args.action == "inspect":
        return _show(client)

    if args.action == "initialize":
        existing = _versions(client)
        if existing:
            print(
                f"Refusing to create duplicate versions; existing versions: {existing}. "
                "Inspect the project and add labels to the intended versions first."
            )
            return 2
        v1 = client.create_prompt(
            name=PROMPT_NAME,
            type="text",
            prompt=PROMPT_V1,
            labels=["baseline", "production"],
            commit_message="Day 13 baseline prompt v1",
        )
        v2 = client.create_prompt(
            name=PROMPT_NAME,
            type="text",
            prompt=PROMPT_V2,
            labels=["candidate"],
            commit_message="Day 13 candidate prompt v2",
        )
        print(f"Created baseline v{v1.version} and candidate v{v2.version}; production stays on v1.")
        return _show(client)

    versions = _versions(client)
    if not {1, 2}.issubset(versions):
        print(f"Expected versions 1 and 2; found {versions}. No label was changed.")
        return 2

    if args.action == "promote-v2":
        client.update_prompt(name=PROMPT_NAME, version=2, new_labels=["candidate", "production"])
        print("Moved production to v2; candidate remains on v2.")
    elif args.action == "rollback-v1":
        client.update_prompt(name=PROMPT_NAME, version=1, new_labels=["baseline", "production"])
        print("Rolled production back to v1; candidate remains on v2.")
    return _show(client)


if __name__ == "__main__":
    sys.exit(main())
