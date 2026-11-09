"""HTTP client for the HarshCraft Fabric mod bridge."""
from __future__ import annotations
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from .config import BASE_URL


class MCError(RuntimeError):
    pass


class MCClient:
    def __init__(self, base_url: str = BASE_URL, timeout: float = 60.0):
        self.base = base_url.rstrip("/")
        self.timeout = timeout

    def _req(self, path: str, data: dict | None = None, retries: int = 3) -> dict:
        url = self.base + path
        body = None if data is None else json.dumps(data).encode()
        last = None
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    out = json.loads(r.read().decode())
                if "error" in out:
                    raise MCError(out["error"])
                return out
            except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
                last = e
                time.sleep(0.3 * (attempt + 1))
        raise MCError(f"cannot reach Minecraft bridge at {url}: {last}")

    def ping(self) -> dict:
        return self._req("/ping")

    def observation(self) -> dict:
        return self._req("/observation")

    def step(self, **action) -> dict:
        """Run one action for `ticks` client ticks and return the resulting observation."""
        return self._req("/step", action, retries=1)

    def scan(self, names, r: int = 24, v: int = 12, max_results: int = 64) -> list[dict]:
        q = urllib.parse.urlencode({"names": ",".join(names), "r": r, "v": v, "max": max_results})
        return self._req("/scan?" + q)["blocks"]
