#!/usr/bin/env python3
"""Final-pass audit: WCAG 2 ratio, APCA, chroma, and color-blind distinguishability of the faces.

CVD simulation: Viénot 1999 (protan, deutan) and Brettel 1997 (tritan) on linear RGB,
precomputed matrices from github.com/DaltonLens/libDaltonLens (libDaltonLens.c).
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build  # noqa: E402

def dec(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def lin(h):
    return [dec(c) for c in build.hex_to_rgb255(h)]

def to_hex(rgb):
    return build.linear_to_hex(rgb)

def mat(m, v):
    return [sum(m[i][j] * v[j] for j in range(3)) for i in range(3)]

PROTAN = [[0.11238, 0.88762, 0.0], [0.11238, 0.88762, 0.0], [0.00401, -0.00401, 1.0]]
DEUTAN = [[0.29275, 0.70725, 0.0], [0.29275, 0.70725, 0.0], [-0.02234, 0.02234, 1.0]]
TRI1 = [[1.01277, 0.13548, -0.14826], [-0.01243, 0.86812, 0.14431], [0.07589, 0.80500, 0.11911]]
TRI2 = [[0.93678, 0.18979, -0.12657], [0.06154, 0.81526, 0.12320], [-0.37562, 1.12767, 0.24796]]
TRI_N = [0.03901, -0.02788, -0.01113]

def sim(h, kind):
    v = lin(h)
    if kind == "protan":
        return to_hex(mat(PROTAN, v))
    if kind == "deutan":
        return to_hex(mat(DEUTAN, v))
    d = sum(a * b for a, b in zip(v, TRI_N))
    return to_hex(mat(TRI1 if d >= 0 else TRI2, v))

def oklab(h):
    r, g, b = lin(h)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = (math.copysign(abs(x) ** (1 / 3), x) for x in (l, m, s))
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)

def de(a, b):
    return math.dist(oklab(a), oklab(b))

def chroma(h):
    _, a, b = oklab(h)
    return math.hypot(a, b)

def wcag(a, b):
    lum = lambda h: sum(w * c for w, c in zip((0.2126, 0.7152, 0.0722), lin(h)))
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)

# pairs that carry meaning when told apart
PAIRS = [("added", "deleted"), ("success", "error"), ("warning", "error"), ("string", "type"),
         ("keyword", "function"), ("string", "number"), ("function", "constant"), ("keyword", "constant"),
         ("number", "type"), ("string", "keyword")]
ROLES = ["fg", "keyword", "function", "fcall", "string", "type", "number", "constant", "param",
         "property", "punct", "comment", "doc", "linenr", "error", "warning", "success"]

def audit(label, f):
    bg = f["bg"]
    print(f"\n== {label} == bg {bg}")
    print(f"  {'role':<9} {'hex':<8} {'WCAG':>6} {'APCA':>6} {'chroma':>7}")
    for r in ROLES:
        print(f"  {r:<9} {f[r]:<8} {wcag(f[r], bg):6.2f} {abs(build.apca(f[r], bg)):6.1f} {chroma(f[r]):7.3f}")
    print(f"  ΔE_ok between meaning-carrying pairs (normal / protan / deutan / tritan); <0.06 flagged")
    for a, b in PAIRS:
        vals = [de(f[a], f[b])] + [de(sim(f[a], k), sim(f[b], k)) for k in ("protan", "deutan", "tritan")]
        flag = " <-- confusable" if min(vals) < 0.06 else ""
        print(f"  {a + '/' + b:<18} " + " ".join(f"{v:.3f}" for v in vals) + flag)

def main():
    import tomllib
    pal = tomllib.loads((ROOT / "palette.toml").read_text())
    for v in ("dark", "light"):
        _, _, env = build.resolve(pal[v])
        audit(v, build.faces(env))

if __name__ == "__main__":
    main()
