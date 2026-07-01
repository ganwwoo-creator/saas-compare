#!/usr/bin/env python3
"""Unmanned refresh: re-scrape tiers, then rebuild the site. One command; runs the
same way locally and in CI (uses whichever Python invokes it, so the venv locally and
the runner's env in GitHub Actions). collect.py is a standalone diagnostic and is NOT
in this hot path — the site consumes tiers.json + curated.json only.
"""
import datetime
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
env = {**os.environ, "SCRAPED_AT": datetime.date.today().isoformat()}

for step in ("parse_tiers.py", "build_site.py"):
    print(f"==> {step}")
    subprocess.run([sys.executable, str(ROOT / "scripts" / step)], env=env, check=True)

print("refresh complete")
