#!/usr/bin/env python3
"""MCP server for session management — resume past sessions or branch new ones."""

import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("session")

WORKSPACE = os.path.expanduser("~/workspace")


def _get_terminal_app() -> str:
    """Detect which terminal app is running. Returns 'iterm2' or 'terminal'."""
    if os.environ.get("ITERM_SESSION_ID") or os.environ.get("TERM_PROGRAM") == "iTerm.app":
        return "iterm2"
    return "terminal"


def _find_session_cwd(session_id: str) -> str:
    """Look up the working directory for a session from history files. Falls back to WORKSPACE."""
    history_dir = Path.home() / "pi-data" / "history"
    if not history_dir.exists():
        return WORKSPACE
    today = datetime.now()
    for i in range(14):
        day = today - timedelta(days=i)
        f = history_dir / f"{day.strftime('%Y-%m-%d')}.json"
        if not f.exists():
            continue
        try:
            entries = json.loads(f.read_text())
            for entry in reversed(entries):
                if entry.get("session_id") == session_id and entry.get("cwd"):
                    return entry["cwd"]
        except Exception:
            pass
    return WORKSPACE


def _open_iterm2_tab(command: str, background: bool = False, cwd: str = WORKSPACE) -> str:
    """Open a new iTerm2 tab via AppleScript and run command in it."""
    tab_id = f"claude-{int(time.time())}"
    escaped_command = command.replace('\\', '\\\\').replace('"', '\\"')
    escaped_cwd = cwd.replace('\\', '\\\\').replace('"', '\\"')

    if background:
        script = f'''
set frontApp to name of first application process of application "System Events" whose frontmost is true
tell application "iTerm2"
    tell current window
        create tab with default profile
        tell current session of current tab
            write text "cd \\"{escaped_cwd}\\" && {escaped_command}"
        end tell
    end tell
end tell
delay 0.1
tell application frontApp to activate
'''
    else:
        script = f'''
tell application "iTerm2"
    activate
    tell current window
        create tab with default profile
        tell current session of current tab
            write text "cd \\"{escaped_cwd}\\" && {escaped_command}"
        end tell
    end tell
end tell
'''
    subprocess.run(["osascript", "-e", script], check=True)
    return tab_id


def _open_terminal_tab(command: str, background: bool = False, cwd: str = WORKSPACE) -> str:
    """Open a new Terminal.app tab via AppleScript and run command in it."""
    tab_id = f"claude-{int(time.time())}"
    escaped_command = command.replace('\\', '\\\\').replace('"', '\\"')
    escaped_cwd = cwd.replace('\\', '\\\\').replace('"', '\\"')
    full_command = f"cd \\"{escaped_cwd}\\" && {escaped_command}"

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
        do script "{full_command}" in front window
    else
        do script "{full_command}"
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
        do script "{full_command}" in front window
    else
        do script "{full_command}"
    end if
end tell
'''
    subprocess.run(["osascript", "-e", script], check=True)
    return tab_id


def _open_tab(command: str, background: bool = False, cwd: str = WORKSPACE) -> str:
    """Route to iTerm2 or Terminal.app based on current terminal."""
    if _get_terminal_app() == "iterm2":
        return _open_iterm2_tab(command, background, cwd)
    return _open_terminal_tab(command, background, cwd)


@mcp.tool()
def resume_session(session_id: str, background: bool = False) -> str:
    """Resume a past Claude Code session in a new tab.

    This is the PRIMARY tool for opening past sessions. Use this whenever the user
    asks to "open", "pull up", "branch", "continue", or "resume" a past session.
    The session_id comes from get_summaries output (the uuid field IS the Claude
    Code session ID) or from search_history results.

    Args:
        session_id: Claude Code session UUID (e.g. '54c77e5a-a32a-42c7-9701-58ebe6c500b2')
        background: If True, start in the background without stealing focus. Default False.
    """
    cwd = _find_session_cwd(session_id)
    tab = _open_tab(f"claude --dangerously-skip-permissions --resume {session_id}", background, cwd)
    if background:
        return f"Opened background tab ({tab}) resuming Claude session {session_id} from {cwd} — focus kept on current tab"
    return f"Opened new tab ({tab}) resuming Claude session {session_id} from {cwd}"


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
    tab = _open_tab(f'claude --dangerously-skip-permissions "$(cat {tmp_path})"', background)
    if background:
        return f"Opened background tab ({tab}) with branched session — focus kept on current tab"
    return f"Opened new tab ({tab}) with branched session"


if __name__ == "__main__":
    mcp.run()
