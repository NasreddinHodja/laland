#!/usr/bin/env python3
"""Throwaway: candidate palettes rendered through doom-themes' own slot -> face rules -> showcase/picker.html.

Face rules copied from doom-themes-base.el:34-60 (font-lock-*), blend math from doom-themes.el:301-343.
Slot assignments copied from doom-dracula-theme.el:88-99 and doom-one-theme.el:98-109.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from build import apca, in_gamut, lch_to_linear, linear_to_hex, oklab_to_linear, oklch_to_lab  # noqa: E402

def hx(L, C, H):
    return linear_to_hex(lch_to_linear(L, C, H)[0])

def max_chroma(L, H):
    lo, hi = 0.0, 0.4
    for _ in range(30):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if in_gamut(oklab_to_linear(*oklch_to_lab(L, mid, H))) else (lo, mid)
    return lo

def hxf(L, frac, H):
    return hx(L, max_chroma(L, H) * frac, H)

# doom-blend: alpha*c1 + (1-alpha)*c2 per sRGB channel; lighten = blend with white at (1-alpha)
def blend(c1, c2, a):
    p = lambda h: [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return "#" + "".join(f"{round((a * x + (1 - a) * y) * 255):02x}" for x, y in zip(p(c1), p(c2)))

def lighten(c, a):
    return blend(c, "#ffffff", 1 - a)

# ── laland Midnight vivid, accents at 80% of max saturation ─────────────
BG = (0.170, 0.040, 270)
FRAC = 0.80
ACC_L = dict(pink=.74, red=.73, orange=.76, yellow=.88, green=.84, cyan=.85, blue=.74, violet=.75, teal=.72)
HUES = dict(pink=350, red=22, orange=55, yellow=90, green=150, cyan=205, blue=255, violet=300, teal=190)

def colors(yellow):
    bgL, bgC, bgH = BG
    c = {a: hxf(ACC_L[a], FRAC, HUES[a]) for a in ACC_L}
    c["yellow"] = yellow
    c.update({
        "bg": hx(bgL, bgC, bgH), "bg-alt": hx(bgL - 0.035, bgC, bgH),
        "base3": hx(bgL + 0.10, bgC * 1.4, bgH), "base4": hx(bgL + 0.08, bgC, bgH),
        "base5": hx(0.62, 0.07, bgH),  # comments slot, like doom-dracula's base5 #6272a4
        "hl-line": hx(bgL + 0.04, bgC * 1.1, bgH),
        "fg": hx(0.96, 0.012, bgH),
    })
    return c

# slot -> palette name, exactly as each upstream theme assigns them
MAPPINGS = {
    "doom-dracula slots": dict(builtin="orange", constants="cyan", functions="green", keywords="pink",
                               methods="teal", operators="violet", type="violet", strings="yellow",
                               variables=("lighten", "pink", 0.6), numbers="violet"),
    "doom-one slots": dict(builtin="pink", constants="violet", functions="pink", keywords="blue",
                           methods="cyan", operators="blue", type="yellow", strings="green",
                           variables=("lighten", "pink", 0.4), numbers="orange"),
}

def slots(c, m):
    s = {k: (lighten(c[v[1]], v[2]) if isinstance(v, tuple) else c[v]) for k, v in m.items()}
    s["comments"] = c["base5"]
    s["doc-comments"] = lighten(c["base5"], 0.25)
    return s

def faces(c, s):
    """font-lock faces as doom-themes-base.el builds them."""
    return {
        "kw": s["keywords"], "fn": s["functions"], "fc": blend(s["functions"], c["fg"], 0.7),
        "ty": s["type"], "str": s["strings"], "con": s["constants"], "num": s["numbers"],
        "var": s["variables"], "vu": blend(s["variables"], c["fg"], 0.5), "op": s["operators"],
        "pun": blend(s["operators"], c["fg"], 0.25), "prop": blend(s["keywords"], c["fg"], 0.6),
        "bi": s["builtin"], "com": s["comments"], "doc": s["doc-comments"],
    }

SNIP = '''<span class="com"># picker.py: font-lock faces exactly as doom-themes computes them</span>
<span class="kw">from</span> dataclasses <span class="kw">import</span> dataclass
<span class="kw">import</span> math

<span class="ty">@dataclass</span><span class="pun">(</span><span class="var">frozen</span><span class="op">=</span><span class="con">True</span><span class="pun">)</span>
<span class="kw">class</span> <span class="ty">Swatch</span><span class="pun">:</span>
    <span class="doc">"""One named color in OKLCH."""</span>
    <span class="prop">name</span><span class="pun">:</span> <span class="bi">str</span>
    <span class="prop">lc</span><span class="pun">:</span> <span class="bi">float</span> <span class="op">=</span> <span class="num">60.0</span>

<span class="kw">def</span> <span class="fn">contrast</span><span class="pun">(</span><span class="var">txt</span><span class="pun">:</span> <span class="bi">str</span><span class="pun">,</span> <span class="var">bg</span><span class="pun">:</span> <span class="bi">str</span> <span class="op">=</span> <span class="str">"#090e21"</span><span class="pun">)</span> <span class="op">-&gt;</span> <span class="bi">float</span><span class="pun">:</span>
    <span class="var">t</span><span class="pun">,</span> <span class="var">b</span> <span class="op">=</span> <span class="fc">luminance</span><span class="pun">(</span><span class="vu">txt</span><span class="pun">),</span> <span class="fc">luminance</span><span class="pun">(</span><span class="vu">bg</span><span class="pun">)</span>
<span class="hl">    <span class="kw">if</span> <span class="fc">abs</span><span class="pun">(</span><span class="vu">b</span> <span class="op">-</span> <span class="vu">t</span><span class="pun">)</span> <span class="op">&lt;</span> <span class="num">0.0005</span><span class="pun">:</span><span class="cur"> </span></span>
        <span class="kw">return</span> <span class="num">0.0</span>
    <span class="kw">return</span> <span class="pun">(</span><span class="vu">b</span> <span class="op">**</span> <span class="num">0.56</span> <span class="op">-</span> <span class="vu">t</span> <span class="op">**</span> <span class="num">0.57</span><span class="pun">)</span> <span class="op">*</span> <span class="num">114</span>

<span class="var">PINK</span> <span class="op">=</span> <span class="fc">Swatch</span><span class="pun">(</span><span class="str">"pink"</span><span class="pun">,</span> <span class="var">lc</span><span class="op">=</span><span class="fc">contrast</span><span class="pun">(</span><span class="str">"#f07fb8"</span><span class="pun">))</span>
<span class="fc">print</span><span class="pun">(</span><span class="str">f"</span><span class="pun">{</span><span class="vu">PINK</span><span class="pun">.</span><span class="prop" style="font-weight:400">name</span><span class="pun">}</span><span class="str">: </span><span class="pun">{</span><span class="vu">PINK</span><span class="pun">.</span><span class="prop" style="font-weight:400">lc</span><span class="pun">:.0f}</span><span class="str">"</span><span class="pun">)</span>

<span class="pun">(</span><span class="kw">defun</span> <span class="fn">laland-rebuild</span> <span class="pun">()</span>
  <span class="doc">"Rebuild and reload the theme."</span>
  <span class="pun">(</span><span class="kw">interactive</span><span class="pun">)</span>
  <span class="pun">(</span><span class="fc">shell-command</span> <span class="str">"python3 build.py"</span><span class="pun">)</span>
  <span class="pun">(</span><span class="fc">load-theme</span> <span class="con">'doom-laland</span> <span class="con">t</span><span class="pun">))</span>'''

LEGEND = [("keywords", "kw"), ("functions", "fn"), ("strings", "str"), ("type", "ty"), ("constants", "con"),
          ("numbers", "num"), ("builtin", "bi"), ("variables", "var"), ("operators", "op"), ("comments", "com")]

YELLOWS = [("Gold", 0.84, 0.80, 80), ("Butter", 0.90, 0.60, 95), ("Warm lemon", 0.90, 0.80, 100),
           ("Pale lemon", 0.93, 0.55, 105), ("Honey", 0.82, 0.85, 70)]

def card(i, title, c, m):
    s = slots(c, m)
    f = faces(c, s)
    style = ";".join(f"--{k}:{v}" for k, v in {**c, **{f'f-{k}': v for k, v in f.items()}}.items())
    legend = "".join(
        f'<span><i style="background:{s[k]}"></i>{k} <em>{m[k] if isinstance(m.get(k), str) else ("lighten " + m[k][1] if k in m else "base5")}</em>'
        f' <small>Lc {abs(apca(s[k], c["bg"])):.0f}</small></span>' for k, _ in LEGEND)
    return f'''<article class="cand" style="{style}">
  <header><b class="num">{i}</b><div><h2>{title}</h2><small>Midnight vivid · accents at {FRAC:.0%} saturation · bg {c["bg"]}</small></div></header>
  <div class="legend">{legend}</div>
  <pre>{SNIP}</pre>
  <div class="ml"><i></i><b>N</b> picker.py <span>12:42</span><em></em><span class="er">✖ 1</span><span class="wa">⚠ 2</span><span class="br">main</span></div>
</article>'''

def main():
    y_default = hxf(0.84, 0.80, 80)
    cards = []
    n = 1
    for title, m in MAPPINGS.items():
        cards.append(card(n, title, colors(y_default), m))
        n += 1
    c = colors(y_default)
    ys = []
    for i, (label, L, fr, H) in enumerate(YELLOWS):
        y = hxf(L, fr, H)
        ys.append(f'<div class="y"><b>Y{i + 1}</b><code style="color:{y}">"python3 build.py" f"pink: "</code>'
                  f'<small>{label} · {y} · Lc {abs(apca(y, c["bg"])):.0f}</small></div>')
    page = (ROOT / "templates" / "picker.html").read_text()
    page = page.replace("<!--@CARDS@-->", "\n".join(cards))
    page = page.replace("<!--@YELLOWS@-->", f'<div class="ys" style="background:{c["bg"]}">' + "".join(ys) + "</div>")
    (ROOT / "showcase" / "picker.html").write_text(page)
    for title, m in MAPPINGS.items():
        s = slots(c, m)
        print(title, {k: (s[k], round(abs(apca(s[k], c["bg"])))) for k, _ in LEGEND})

if __name__ == "__main__":
    main()
