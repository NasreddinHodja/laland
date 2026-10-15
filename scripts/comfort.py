#!/usr/bin/env python3
"""Throwaway: round 5 picker — comfort levels of the chosen theme, rendered through build.py's doom faces."""
import copy
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build  # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))
import audit  # noqa: E402

BASE = tomllib.loads((ROOT / "palette.toml").read_text())["dark"]

def tweak(sat=None, acc=None, bg_chroma=None, slots=None):
    """Copy of the current dark palette with changes to accents, ground chroma, and slot assignments."""
    v = copy.deepcopy(BASE)
    c = v["colors"]
    for k, s in (sat or {}).items():
        c[k] = {**c[k], "sat": s}
    for k, (L, s, H) in (acc or {}).items():
        c[k] = {"L": L, "sat": s, "H": H}
    if bg_chroma is not None:
        for k in ("bg", "bg-alt", "base0", "base1", "base2", "base3", "base4"):
            c[k] = [c[k][0], c[k][1] * bg_chroma, c[k][2]]
    v["slots"].update(slots or {})
    return v

# Round 9: grown-up blues for keywords, calmer type colors. A muted mid blue collides with how pink looks
# under protanopia (#ff93dd -> #a4a4dd), so the blues are pale and icy; types sit at a calm brightness.
ICY_PERI = dict(blue=(0.88, 0.70, 272))
ICY_STEEL = dict(blue=(0.88, 0.50, 245))
ICY_CORN = dict(blue=(0.87, 0.80, 262))
SEA = dict(slots=dict(type="teal"), acc=dict(teal=(0.75, 0.50, 185)))
# icy keywords collide with the pale lavender constants, so constants go back to a saturated violet
VIOLET = dict(violet=(0.76, 1.00, 307))

def combo(blue, types):
    return tweak(acc={**blue, **types["acc"], **VIOLET}, slots=types.get("slots"))

LEVELS = [
    ("Current", tweak()),
    ("Icy periwinkle keywords · sea-green types", combo(ICY_PERI, SEA)),
    ("Icy steel keywords · sea-green types", combo(ICY_STEEL, SEA)),
    ("Icy cornflower keywords · sea-green types", combo(ICY_CORN, SEA)),
]

ROLES = ["keyword", "function", "string", "type", "number", "constant", "param", "comment", "fg"]

SNIP = (ROOT / "templates" / "comfort-sample.html").read_text()

def card(i, title, v):
    colors, specs, env = build.resolve(v)
    f = build.faces(env)
    style = ";".join(f"--{k}:{x}" for k, x in f.items())
    lc = {r: abs(build.apca(f[r], f["bg"])) for r in ROLES}
    stats = " · ".join(f'<span><i style="background:{f[r]}"></i>{r} {lc[r]:.0f}</span>' for r in ROLES)
    worst = []
    for a, b in audit.PAIRS:
        vals = [audit.de(audit.sim(f[a], k), audit.sim(f[b], k)) for k in ("protan", "deutan", "tritan")]
        if min(vals) < 0.06:
            worst.append(f"{a}/{b} {min(vals):.3f}")
    stats += " · <b>color-blind check: " + ("all pairs clear" if not worst else "close: " + ", ".join(worst)) + "</b>"
    print(i, title, {r: (f[r], round(lc[r])) for r in ("keyword", "type", "string", "constant")}, worst)
    return f'''<article class="cand" style="{style}">
  <header><b class="num">{i}</b><div><h2>{title}</h2><small>bg {f["bg"]} · fg {f["fg"]}</small></div></header>
  <div class="stats">{stats}</div>
  <pre>{SNIP}</pre>
</article>'''

def main():
    cur = tomllib.loads((ROOT / "palette.toml").read_text())["dark"]
    cards = [card(i + 1, t, v or cur) for i, (t, v) in enumerate(LEVELS)]
    page = (ROOT / "templates" / "comfort.html").read_text().replace("<!--@CARDS@-->", "\n".join(cards))
    (ROOT / "showcase" / "comfort.html").write_text(page)

if __name__ == "__main__":
    main()
