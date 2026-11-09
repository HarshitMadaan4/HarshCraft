"""Optional LLM command parser (Anthropic API). Used only when the rule parser does not understand a command.
Set ANTHROPIC_API_KEY (and optionally HARSHCRAFT_LLM_MODEL). Output is validated against a fixed schema."""
from __future__ import annotations
import json
import os
import urllib.request

from .planner import Task

ALLOWED = {"get", "goto", "kill", "hunt", "build", "eat", "explore", "shelter", "survive", "set_home", "go_home",
           "stop", "status", "pillar", "bridge", "cook_all", "food"}
SYSTEM = (
    "You convert a Minecraft player's spoken command into JSON tasks for a bot. Reply with ONLY JSON: "
    '{"reply": "<short confirmation>", "tasks": [{"kind": ..., "item": ..., "n": ..., "args": {...}}]}. '
    "Allowed kinds: get (item = minecraft item id without prefix, e.g. stone_pickaxe, log, iron_ingot, diamond; n = amount), "
    "goto (args x,y,z; y may be null), kill (item = mob id or *hostile), hunt (item = cow/pig/sheep/chicken, n), "
    "build (item = house|wall|tower|platform, args dims list or null, material or null), eat, explore, shelter, "
    "survive (args seconds), set_home, go_home, stop, status, pillar (n), bridge (n), cook_all, food (n). "
    "If the command is not a bot task, return an empty tasks list and explain in reply.")


def make_llm_parser():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    model = os.environ.get("HARSHCRAFT_LLM_MODEL", "claude-sonnet-5-5")

    def parse(text: str, state: str):
        body = json.dumps({"model": model, "max_tokens": 400, "system": SYSTEM,
                           "messages": [{"role": "user", "content": f"Bot state: {state}\nCommand: {text}"}]}).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
            "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            out = json.loads(r.read().decode())
        txt = "".join(b.get("text", "") for b in out["content"])
        txt = txt[txt.index("{"): txt.rindex("}") + 1]
        data = json.loads(txt)
        tasks = []
        for t in data.get("tasks", []):
            if t.get("kind") in ALLOWED:
                tasks.append(Task(t["kind"], str(t.get("item") or ""), int(t.get("n") or 1), dict(t.get("args") or {})))
        return tasks, str(data.get("reply", ""))
    return parse
