#!/usr/bin/env python3
"""MCP server for session management — resume past sessions or branch new ones."""

import subprocess
import uuid
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("session")


def _open_terminal_tab(command: str) -> None:
    """Open a new Terminal.app tab and run the given command."""
    escaped = command.replace("\\", "\\\\").replace('"', '\\"')
    subprocess.run([
        "osascript", "-e",
        f'tell application "Terminal" to do script "{escaped}"',
    ], check=True)


@mcp.tool()
def resume_session(session_id: str) -> str:
    """Resume a past Claude Code session in a new Terminal tab.

    This is the PRIMARY tool for opening past sessions. Use this whenever the user
    asks to "open", "pull up", "branch", "continue", or "resume" a past session.
    The session_id comes from get_summaries output (the uuid field IS the Claude
    Code session ID) or from search_history results.

    Args:
        session_id: Claude Code session UUID (e.g. '54c77e5a-a32a-42c7-9701-58ebe6c500b2')
    """
    _open_terminal_tab(f"claude --resume {session_id}")
    return f"Opened new Terminal tab resuming session {session_id}"


@mcp.tool()
def branch_session(context: str, prompt: str) -> str:
    """Branch a tangent from the CURRENT session into a new Claude Code session.

    Use this ONLY when you want to fork a tangent from the current conversation
    into a fresh session with specific injected context. This creates a NEW session,
    not a continuation of an existing one. For opening past sessions, use
    resume_session instead.

    Args:
        context: Relevant context gathered from the current session (errors, file contents, tool results, etc.)
        prompt: The distilled task or question to address in the new session
    """
    branch_id = uuid.uuid4().hex[:8]
    tmp_path = Path(f"/tmp/claude-branch-{branch_id}.txt")
    composed = f"Here is context from a branched session:\n\n{context}\n\n---\n\n{prompt}"
    tmp_path.write_text(composed)
    _open_terminal_tab(f'claude "$(cat {tmp_path})"')
    return f"Opened new Terminal tab with branched session (context file: {tmp_path})"


if __name__ == "__main__":
    mcp.run()
