from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Result:
    ok: bool
    msg: str = ""

    def __bool__(self):
        return self.ok


def have(m, item: str) -> int:
    """Inventory count for an item name, '#tag', or the generic 'log'."""
    if item == "log":
        return m.w.count("#logs")
    return m.w.count(item)
