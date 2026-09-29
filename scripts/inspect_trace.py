from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from langfuse import get_client

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"


def trace_id_for_correlation(correlation_id: str) -> str | None:
    if not LOG_PATH.exists():
        return None
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("correlation_id") == correlation_id and record.get("trace_id"):
            return record["trace_id"]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect Langfuse observations for one local correlation ID")
    parser.add_argument(
        "correlation_id",
        nargs="?",
        help="Request ID from data/logs.jsonl, e.g. req-1234abcd",
    )
    parser.add_argument(
        "--recent-minutes",
        type=int,
        help="List recent root observations from the configured personal project.",
    )
    args = parser.parse_args()
    if args.recent_minutes is None and not args.correlation_id:
        parser.error("provide a correlation_id or --recent-minutes")

    load_dotenv(REPO_ROOT / ".env", override=False)
    client = get_client()
    if args.recent_minutes is not None:
        start = datetime.now(timezone.utc) - timedelta(minutes=max(1, args.recent_minutes))
        result = client.api.observations.get_many(
            from_start_time=start,
            is_root_observation=True,
            limit=1000,
            fields="core,basic,metadata",
        )
        print(f"Recent Langfuse root traces: {len(result.data)}")
        for observation in result.data:
            metadata = observation.metadata if isinstance(observation.metadata, dict) else {}
            correlation_id = metadata.get("correlation_id", "-")
            print(f"{correlation_id} {observation.trace_id or '-'} {observation.name or '-'}")
        return 0

    trace_id = trace_id_for_correlation(args.correlation_id)
    if trace_id is None:
        print(f"No trace_id found in {LOG_PATH} for {args.correlation_id}.")
        return 1
    result = client.api.observations.get_many(
        trace_id=trace_id,
        limit=100,
        fields="core,basic,metadata,model,usage,prompt,metrics",
    )
    if not result.data:
        print(f"No Langfuse observations are visible yet for trace {trace_id}.")
        return 1

    print(f"correlation_id={args.correlation_id}")
    print(f"trace_id={trace_id}")
    for observation in result.data:
        parent = observation.parent_observation_id or "(root)"
        usage = observation.usage_details or {}
        cost = observation.cost_details or {}
        metadata = observation.metadata if isinstance(observation.metadata, dict) else {}
        safe_metadata = {
            key: metadata.get(key)
            for key in ("correlation_id", "prompt_name", "prompt_label", "prompt_version", "prompt_source", "doc_count")
            if key in metadata
        }
        print(
            f"name={observation.name} type={observation.type} parent={parent} "
            f"latency_ms={round(observation.latency * 1000, 1) if observation.latency is not None else '-'} "
            f"model={observation.model or '-'} prompt={observation.prompt_name or '-'} "
            f"prompt_version={observation.prompt_version or '-'} usage={usage or '-'} "
            f"cost={cost or '-'} metadata={safe_metadata or '-'}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
