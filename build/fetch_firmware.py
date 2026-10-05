"""Baixa os 4 firmwares do Release v0.5.0 do pokeldn para firmware/, conferindo o SHA-256."""
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from distrib.board import FIRMWARE  # noqa: E402

TAG = "v0.5.0"
API = f"https://api.github.com/repos/Decryptu/pokeldn/releases/tags/{TAG}"
OUT = Path(__file__).resolve().parent.parent / "firmware"
HEADERS = {"User-Agent": "Distribuidor-build"}


def main() -> None:
    # No CI, sem token a API cai no limite por IP compartilhado (403 rate limit exceeded).
    token = os.environ.get("GITHUB_TOKEN")
    api_headers = {**HEADERS, **({"Authorization": f"Bearer {token}"} if token else {})}
    with urllib.request.urlopen(urllib.request.Request(API, headers=api_headers), timeout=30) as resp:
        assets = {a["name"]: a for a in json.loads(resp.read())["assets"]}
    OUT.mkdir(exist_ok=True)
    for name in FIRMWARE.values():
        asset = assets[name]
        with urllib.request.urlopen(urllib.request.Request(asset["browser_download_url"], headers=HEADERS),
                                    timeout=120) as resp:
            data = resp.read()
        digest = (asset.get("digest") or "").removeprefix("sha256:")
        if digest and hashlib.sha256(data).hexdigest() != digest:
            raise SystemExit(f"{name}: SHA-256 não confere")
        (OUT / name).write_bytes(data)
        print(f"{name}: {len(data)} bytes")


if __name__ == "__main__":
    main()
