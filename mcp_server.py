#!/usr/bin/env python3
"""MCP server for session management — resume past sessions or branch new ones."""

import os
import subprocess
import time
import uuid
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("session")

TMUX = "/opt/homebrew/bin/tmux"
WORKSPACE = os.path.expanduser("~/workspace")


def _open_in_tmux_tab(command: str, background: bool = False) -> str:
    """Create a detached tmux session, send the command, then optionally open a Terminal tab."""
    session = f"claude-{int(time.time())}"

    # Create the session detached and send the command — subprocess args, no quoting issues
    subprocess.run([TMUX, "new-session", "-d", "-s", session, "-c", WORKSPACE], check=True)
    subprocess.run([TMUX, "send-keys", "-t", session, command, "Enter"], check=True)

    # Open a Terminal tab that attaches — simple safe string, no special chars
    attach_cmd = f"{TMUX} attach-session -t {session}"
    if background:
        script = f'''
set frontApp to name of first application process of application "System Events" whose frontmost is true
tell application "Terminal"
    activate
    if (count of windows) > 0 then
        tell application "System Events"
            keystroke "t" using {{command down}}
        end tell
        delay 0.3
        do script "{attach_cmd}" in front window
    else
        do script "{attach_cmd}"
    end if
end tell
delay 0.2
tell application frontApp to activate
'''
    else:
        script = f'''
tell application "Terminal"
    activate
    if (count of windows) > 0 then
        tell application "System Events"
            keystroke "t" using {{command down}}
        end tell
        delay 0.3
        do script "{attach_cmd}" in front window
    else
        do script "{attach_cmd}"
    end if
end tell
'''
    subprocess.run(["osascript", "-e", script], check=True)
    return session


@mcp.tool()
def resume_session(session_id: str, background: bool = False) -> str:
    """Resume a past Claude Code session in a new Terminal tab.

    This is the PRIMARY tool for opening past sessions. Use this whenever the user
    asks to "open", "pull up", "branch", "continue", or "resume" a past session.
    The session_id comes from get_summaries output (the uuid field IS the Claude
    Code session ID) or from search_history results.

    Args:
        session_id: Claude Code session UUID (e.g. '54c77e5a-a32a-42c7-9701-58ebe6c500b2')
        background: If True, start in the background without stealing focus. Default False.
    """
    session = _open_in_tmux_tab(f"claude --dangerously-skip-permissions --resume {session_id}", background)
    if background:
        return f"Opened background Terminal tab (tmux: {session}) resuming Claude session {session_id} — focus kept on current tab"
    return f"Opened new Terminal tab (tmux: {session}) resuming Claude session {session_id}"


@mcp.tool()
def branch_session(context: str, prompt: str, background: bool = False) -> str:
    """Branch a tangent from the CURRENT session into a new Claude Code session.

    Use this ONLY when you want to fork a tangent from the current conversation
    into a fresh session with specific injected context. This creates a NEW session,
    not a continuation of an existing one. For opening past sessions, use
    resume_session instead.

    Args:
        context: Relevant context gathered from the current session (errors, file contents, tool results, etc.)
        prompt: The distilled task or question to address in the new session
        background: If True, start in the background without stealing focus. Default False.
    """
    branch_id = uuid.uuid4().hex[:8]
    tmp_path = Path(f"/tmp/claude-branch-{branch_id}.txt")
    composed = f"Here is context from a branched session:\n\n{context}\n\n---\n\n{prompt}"
    tmp_path.write_text(composed)
    session = _open_in_tmux_tab(f'claude --dangerously-skip-permissions "$(cat {tmp_path})"', background)
    if background:
        return f"Opened background Terminal tab (tmux: {session}) with branched session — focus kept on current tab"
    return f"Opened new Terminal tab (tmux: {session}) with branched session"


if __name__ == "__main__":
    mcp.run()
