"""ghostloop-uses-joe.py: sample ghostloop runtime that routes its
LLMPolicy through joe-http instead of talking to ollama directly.

The win: joe-gemma is your personalised orchestrator, so the robot's
planning brain inherits all your distilled lessons + style preferences.
Auth-gated, so ghostloop can run on a different machine and still
reach joe over Tailscale / LAN.

Setup:
    1. Start joe-http on the machine running joe:
           joe-http --host 0.0.0.0
       (or 127.0.0.1 if ghostloop is on the same box)

    2. Grab the bearer token:
           cat ~/.joe-agent/http-token

    3. Run this:
           OPENAI_BASE_URL=http://<joe-host>:8765/v1 \\
           OPENAI_API_KEY=<token> \\
           OPENAI_MODEL=joe-gemma \\
               python3 ghostloop-uses-joe.py
"""

from __future__ import annotations

import os

from ghostloop import MockBackend, PolicyPipeline, PrimitiveRegistry, Runtime
from ghostloop.policies import (
    GeofenceGate,
    LLMPolicyConfig,
    llm_policy_loop,
)
from ghostloop.primitives import move_to, pick, place, scan


def main() -> None:
    registry = PrimitiveRegistry([move_to(), scan(), pick(), place()])
    runtime = Runtime(
        backend=MockBackend(),
        registry=registry,
        policy_pipeline=PolicyPipeline(gates=[
            GeofenceGate(min_corner=(-1, -1, 0), max_corner=(1, 1, 1)),
        ]),
    )

    base_url = os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:8765/v1")
    api_key = os.environ["OPENAI_API_KEY"]
    model = os.environ.get("OPENAI_MODEL", "joe-gemma")

    summary = llm_policy_loop(
        registry=registry,
        runtime=runtime,
        goal="Pick widget-7 from (0.4, 0.2, 0.1) and place it at (-0.4, 0.2, 0.1).",
        config=LLMPolicyConfig(
            base_url=base_url,
            api_key=api_key,
            model=model,
        ),
        max_steps=16,
    )

    runtime.trace.write_jsonl("episode.jsonl")
    print(f"steps: {summary.step_count}  success: {summary.goal_reached}")
    print("trace written to episode.jsonl")


if __name__ == "__main__":
    main()
