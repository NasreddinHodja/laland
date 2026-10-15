#!/usr/bin/env python3
"""Render showcase/tuner.html: per-color sliders seeded from palette.toml (dark), doom slot math in JS."""
import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def main():
    pal = tomllib.loads((ROOT / "palette.toml").read_text())["dark"]
    accents = {k: v for k, v in pal["colors"].items() if isinstance(v, dict)}
    ground = {k: v for k, v in pal["colors"].items() if isinstance(v, list)}
    seed = {"accents": accents, "ground": ground, "slots": pal["slots"]}
    page = (ROOT / "templates" / "tuner.html").read_text()
    page = page.replace("/*@SEED@*/null", json.dumps(seed))
    page = page.replace("<!--@SAMPLE@-->", (ROOT / "templates" / "comfort-sample.html").read_text())
    (ROOT / "showcase" / "tuner.html").write_text(page)

if __name__ == "__main__":
    main()
