"""Dispatcher: takes a loaded agent config + task message and runs the agent
against the Anthropic API via the Claude Agent SDK.

The agent gets file/bash tools (Read, Write, Edit, Glob, Grep, Bash) inside a
working directory. Each invocation produces:
  • a final transcript string (returned to the workflow as the step's artifact)
  • a per-step JSONL log under <working_dir>/_agent_logs/<agent_name>.jsonl
  • a per-step usage record (input/output tokens) under the same JSONL

Set DRY_RUN=1 in the environment to print the resolved system prompt and task
without calling the API.
"""
from __future__ import annotations
import asyncio, json, os, time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

DEFAULT_MODEL    = "claude-sonnet-4-5"     # safer default than opus on cost
DEFAULT_MAX_TURNS = 40
DEFAULT_TOOLS    = ["Read", "Write", "Edit", "Glob", "Grep", "Bash"]


class DispatcherUnavailable(RuntimeError):
    """Raised when claude-agent-sdk is not installed or no API key is set."""


@dataclass
class DispatchResult:
    agent: str
    status: str                       # "ok" | "error" | "dry_run"
    transcript: str = ""
    error: str = ""
    duration_seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    log_path: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _check_runtime() -> None:
    try:
        import claude_agent_sdk  # noqa: F401
    except ImportError as e:
        raise DispatcherUnavailable(
            "claude-agent-sdk is not installed. Run: pip install claude-agent-sdk"
        ) from e
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise DispatcherUnavailable(
            "ANTHROPIC_API_KEY is not set. Add it to .env or export it before running."
        )


def _format_inputs_block(inputs: dict | None) -> str:
    """Render upstream artefacts as a readable block under the task message."""
    if not inputs:
        return ""
    lines = ["", "## Upstream artefacts", ""]
    for k, v in inputs.items():
        if isinstance(v, str):
            preview = v if len(v) <= 4000 else v[:4000] + f"\n... [truncated, {len(v)} chars total]"
        elif isinstance(v, (dict, list)):
            j = json.dumps(v, default=str, indent=2)
            preview = j if len(j) <= 4000 else j[:4000] + "\n... [truncated]"
        else:
            preview = repr(v)[:1000]
        lines.append(f"### {k}\n```\n{preview}\n```\n")
    return "\n".join(lines)


async def _run_agent_async(
    *,
    agent_name: str,
    system_prompt: str,
    task: str,
    model: str,
    working_dir: Path,
    allowed_tools: list[str],
    max_turns: int,
    log_path: Path,
) -> DispatchResult:
    from claude_agent_sdk import (
        query, ClaudeAgentOptions, AssistantMessage, UserMessage,
        ResultMessage, TextBlock, ToolUseBlock, ToolResultBlock,
    )

    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        model=model,
        cwd=str(working_dir),
        allowed_tools=allowed_tools,
        max_turns=max_turns,
        permission_mode="acceptEdits",
    )

    transcript_parts: list[str] = []
    in_tokens = out_tokens = 0
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()

    with open(log_path, "a") as logf:
        logf.write(json.dumps({
            "ts": time.time(), "type": "step_start",
            "agent": agent_name, "model": model,
            "task_chars": len(task), "system_chars": len(system_prompt),
        }) + "\n")

        try:
            async for msg in query(prompt=task, options=options):
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            transcript_parts.append(block.text)
                            logf.write(json.dumps({
                                "ts": time.time(), "type": "assistant_text",
                                "text": block.text[:8000],
                            }) + "\n")
                        elif isinstance(block, ToolUseBlock):
                            logf.write(json.dumps({
                                "ts": time.time(), "type": "tool_use",
                                "tool": block.name,
                                "input": str(block.input)[:2000],
                            }) + "\n")
                elif isinstance(msg, UserMessage):
                    # Tool results come back as user messages
                    for block in getattr(msg, "content", []):
                        if isinstance(block, ToolResultBlock):
                            content = block.content
                            preview = (content[:2000] if isinstance(content, str)
                                       else str(content)[:2000])
                            logf.write(json.dumps({
                                "ts": time.time(), "type": "tool_result",
                                "tool_use_id": block.tool_use_id,
                                "is_error": getattr(block, "is_error", False),
                                "content": preview,
                            }) + "\n")
                elif isinstance(msg, ResultMessage):
                    usage = getattr(msg, "usage", None) or {}
                    in_tokens = usage.get("input_tokens", 0)
                    out_tokens = usage.get("output_tokens", 0)
                    logf.write(json.dumps({
                        "ts": time.time(), "type": "result",
                        "subtype": getattr(msg, "subtype", ""),
                        "duration_ms": getattr(msg, "duration_ms", None),
                        "num_turns": getattr(msg, "num_turns", None),
                        "input_tokens": in_tokens, "output_tokens": out_tokens,
                        "total_cost_usd": getattr(msg, "total_cost_usd", None),
                    }) + "\n")
        except Exception as e:
            logf.write(json.dumps({
                "ts": time.time(), "type": "error",
                "error": str(e), "error_type": type(e).__name__,
            }) + "\n")
            return DispatchResult(
                agent=agent_name, status="error", error=str(e),
                duration_seconds=time.time() - started,
                log_path=str(log_path),
            )

    return DispatchResult(
        agent=agent_name, status="ok",
        transcript="\n".join(transcript_parts),
        duration_seconds=time.time() - started,
        input_tokens=in_tokens, output_tokens=out_tokens,
        log_path=str(log_path),
    )


def run_step(
    agent_config: dict,
    task: str,
    working_dir: Path,
    inputs: dict | None = None,
    *,
    dry_run: bool = False,
    log_dir: Path | None = None,
) -> DispatchResult:
    """
    Synchronous entrypoint used by WorkflowEngine.execute().

    working_dir  — task sandbox: where agents read/write files for the task.
                   Can be any path on disk.
    log_dir      — where API interaction logs (_agent_logs/*.jsonl) are written.
                   Defaults to SYSTEM_DIR/_agent_logs so logs never mix with
                   task output regardless of where working_dir points.
    """
    from runtime.telemetry import AGENT_LOGS_DIR
    agent_name = agent_config.get("name", "unknown")
    system_prompt = Path(agent_config["_prompt_path"]).read_text()
    model = agent_config.get("model", DEFAULT_MODEL)
    _tools_cfg = agent_config.get("tools")
    allowed_tools = _tools_cfg if _tools_cfg is not None else DEFAULT_TOOLS
    max_turns = int(agent_config.get("max_turns", DEFAULT_MAX_TURNS))

    full_task = task + _format_inputs_block(inputs)

    _log_dir = Path(log_dir) if log_dir else AGENT_LOGS_DIR
    log_path = _log_dir / f"{agent_name}.jsonl"

    if dry_run or os.environ.get("DRY_RUN") == "1":
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(json.dumps({
            "ts": time.time(), "type": "dry_run",
            "agent": agent_name, "model": model,
            "system_prompt_preview": system_prompt[:500],
            "task_preview": full_task[:1000],
            "allowed_tools": allowed_tools,
        }) + "\n")
        print(f"[dry-run] {agent_name}  model={model}  tools={allowed_tools}")
        print(f"           system: {len(system_prompt)} chars  task: {len(full_task)} chars")
        return DispatchResult(
            agent=agent_name, status="dry_run",
            transcript=f"[DRY RUN — would have called {model} for {agent_name}]",
            log_path=str(log_path),
            metadata={"system_chars": len(system_prompt), "task_chars": len(full_task)},
        )

    _check_runtime()
    return asyncio.run(_run_agent_async(
        agent_name=agent_name,
        system_prompt=system_prompt,
        task=full_task,
        model=model,
        working_dir=Path(working_dir),
        allowed_tools=allowed_tools,
        max_turns=max_turns,
        log_path=log_path,
    ))
