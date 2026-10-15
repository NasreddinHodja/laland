#!/usr/bin/env python3
"""laland build: palette.toml -> hex, APCA contrast report, doom themes, showcase.

Color math: OKLCH -> sRGB (Björn Ottosson, bottosson.github.io/posts/oklab).
doom helpers: ported from doom-themes.el:301-343 (sRGB blend).
Derived faces: as doom-themes-base.el:34-60 builds them from the slots.
"""
import json
import math
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VARIANTS = ("dark", "light")
THEME_NAMES = {"dark": "doom-laland", "light": "doom-laland-light"}

# ── OKLab / OKLCH ────────────────────────────────────────────────────────

def oklab_to_linear(L, a, b):
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    return (
        +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )

def oklch_to_lab(L, C, H):
    h = math.radians(H)
    return L, C * math.cos(h), C * math.sin(h)

def in_gamut(rgb, eps=1e-4):
    return all(-eps <= c <= 1 + eps for c in rgb)

def max_chroma(L, H):
    lo, hi = 0.0, 0.4
    for _ in range(30):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if in_gamut(oklab_to_linear(*oklch_to_lab(L, mid, H))) else (lo, mid)
    return lo

def lch_to_linear(L, C, H):
    """Clip into sRGB by lowering chroma (keeps L and H). Returns (rgb, clipped?)."""
    mc = max_chroma(L, H)
    return oklab_to_linear(*oklch_to_lab(L, min(C, mc), H)), C > mc + 1e-4

def encode(c):
    c = min(1.0, max(0.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055

def linear_to_hex(rgb):
    return "#" + "".join(f"{round(encode(c) * 255):02x}" for c in rgb)

def hex_to_rgb255(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))

# ── doom helpers (sRGB, as doom-themes.el) ───────────────────────────────

def blend(c1, c2, a):
    return "#" + "".join(f"{round(a * x + (1 - a) * y):02x}"
                         for x, y in zip(hex_to_rgb255(c1), hex_to_rgb255(c2)))

def darken(c, a):
    return blend(c, "#000000", 1 - a)

def lighten(c, a):
    return blend(c, "#ffffff", 1 - a)

# ── APCA-W3 0.0.98G (github.com/Myndex/apca-w3, SA98G constants) ─────────

def apca_y(h):
    r, g, b = (c / 255 for c in hex_to_rgb255(h))
    return 0.2126729 * r ** 2.4 + 0.7151522 * g ** 2.4 + 0.0721750 * b ** 2.4

def apca(txt, bg):
    t, b = apca_y(txt), apca_y(bg)
    clamp = lambda y: y if y > 0.022 else y + (0.022 - y) ** 1.414
    t, b = clamp(t), clamp(b)
    if abs(b - t) < 0.0005:
        return 0.0
    if b > t:
        s = (b ** 0.56 - t ** 0.57) * 1.14
        return 0.0 if s < 0.1 else (s - 0.027) * 100
    s = (b ** 0.65 - t ** 0.62) * 1.14
    return 0.0 if s > -0.1 else (s + 0.027) * 100

# ── resolve ──────────────────────────────────────────────────────────────

def color(spec):
    if isinstance(spec, dict):
        L, H = spec["L"], spec["H"]
        return linear_to_hex(lch_to_linear(L, max_chroma(L, H) * spec["sat"], H)[0]), (L, spec["sat"], H, "sat")
    L, C, H = spec
    return linear_to_hex(lch_to_linear(L, C, H)[0]), (L, C, H, "C")

def slot_value(expr, env):
    parts = expr.split(":")
    if parts[0] == "lighten":
        return lighten(env[parts[1]], float(parts[2]))
    if parts[0] == "darken":
        return darken(env[parts[1]], float(parts[2]))
    if parts[0] == "blend":
        return blend(env[parts[1]], env[parts[2]], float(parts[3]))
    return env[expr]

def slot_elisp(expr):
    parts = expr.split(":")
    if parts[0] in ("lighten", "darken"):
        return f"(doom-{parts[0]} {parts[1]} {parts[2]})"
    if parts[0] == "blend":
        return f"(doom-blend {parts[1]} {parts[2]} {parts[3]})"
    return expr

def resolve(variant):
    colors, specs = {}, {}
    for name, spec in variant["colors"].items():
        colors[name], specs[name] = color(spec)
    env = dict(colors)
    for slot, expr in variant["slots"].items():
        env[slot] = slot_value(expr, env)
    return colors, specs, env

def faces(e):
    """The colors Emacs ends up painting, per doom-themes-base.el + laland overrides."""
    f = {
        # font-lock (doom-themes-base.el:34-60)
        "keyword": e["keywords"], "function": e["functions"], "fcall": blend(e["functions"], e["fg"], 0.7),
        "string": e["strings"], "type": e["type"], "number": e["numbers"], "constant": e["constants"],
        "builtin": e["builtin"], "param": e["variables"], "varuse": blend(e["variables"], e["fg"], 0.5),
        "comment": e["comments"], "doc": e["doc-comments"], "operator": e["operators"],
        "punct": blend(e["operators"], e["fg"], 0.25), "property": blend(e["keywords"], e["fg"], 0.6),
        "escape": e["operators"],
        # UI
        "bg": e["bg"], "bg-alt": e["bg-alt"], "bg-deep": e["base0"], "fg": e["fg"], "fg-dim": e["base7"],
        "hl-line": e["bg-alt"], "surface": e["base3"], "border": e["base3"],
        "linenr": e["base4"], "linenr-cur": e["highlight"], "cursor": e["highlight"], "link": e["highlight"],
        "region": e["region"], "search": blend(e["yellow"], e["bg"], 0.3),
        "error": e["error"], "warning": e["warning"], "success": e["success"], "info": e["cyan"],
        "added": e["vc-added"], "deleted": e["vc-deleted"], "modified": e["vc-modified"],
        "added-bg": blend(e["vc-added"], e["bg"], 0.2), "deleted-bg": blend(e["vc-deleted"], e["base3"], 0.2),
        "modeline": e["modeline-bg"],
        # outline-1..3 (doom-themes-base.el:1255-1257) feed org-level-1..3
        "h1": e["blue"], "h2": e["magenta"], "h3": e["violet"], "h4": e["cyan"],
        "org-todo": e["green"], "org-date": e["yellow"],
        "wk-key": e["green"], "wk-grp": e["violet"], "wk-cmd": e["blue"],
        "magit-heading": e["blue"], "magit-branch": e["cyan"],
        "orderless": blend(e["blue"], e["fg"], 0.6), "orderless-bg": blend(e["blue"], e["bg"], 0.1),
        # names the mockups use for ANSI / ramps
        "pink": e["magenta"], "crust": e["base0"], "mantle": e["bg-alt"], "base": e["bg"],
        "surface0": e["base2"], "surface1": e["base3"], "surface2": e["base4"],
        "overlay0": e["base4"], "overlay1": e["base5"], "overlay2": e["base6"],
        "subtext0": e["base7"], "subtext1": e["base7"], "text": e["fg"],
    }
    return f

# APCA floors. "APCA in a Nutshell": body text 75 (90 preferred), other content 60, large/bold 45,
# placeholder/disabled 30. Syntax floor is 55, a little under 60: pink and violet sit at Lc 58-59
# on the lighter bg chosen in round 6, the most they reach at full saturation.
TARGETS = {
    # fg floor 85, not 90: the text is pulled back from white to cut halation on dark grounds
    # (smashingmagazine.com/2025/04/inclusive-dark-mode-designing-accessible-dark-themes).
    "fg": 85, "fg-dim": 60,
    **{r: 55 for r in "keyword function fcall string type number constant builtin param punct property".split()},
    "comment": 45, "doc": 50, "linenr": 30,
}
FG_ON = ("region", "hl-line", "modeline", "surface")
# magit paints diff lines in vc-added/vc-deleted on their tinted bg (doom-themes-base.el:923,934)
DIFF_ON = (("added", "added-bg"), ("deleted", "deleted-bg"))

def check(vname, f):
    bg, fails = f["bg"], []
    print(f"\n── {vname} ── bg {bg}")
    rows = [(r, f[r], "bg", abs(apca(f[r], bg)), floor) for r, floor in TARGETS.items()]
    rows += [("fg", f["fg"], s, abs(apca(f["fg"], f[s])), 75) for s in FG_ON]
    # bold diff lines; floor 40 under APCA's 45 because red stays dark enough to tell from green for
    # red-green color blindness (scripts/audit.py), and every diff line also carries its +/- marker
    rows += [(r, f[r], s, abs(apca(f[r], f[s])), 40) for r, s in DIFF_ON]
    for role, hx, on, lc, floor in rows:
        ok = lc >= floor
        print(f"  {'ok ' if ok else 'LOW'} {role:<9}{hx}  on {on:<10} Lc {lc:5.1f}  (≥{floor})")
        if not ok:
            fails.append(f"{vname}: {role} {hx} on {on} Lc {lc:.1f} < {floor}")
    return fails

# ── doom theme ───────────────────────────────────────────────────────────

ANSI16 = {  # 16-color fallbacks, as doom-one-theme.el assigns them
    "bg": "black", "bg-alt": "black", "base0": "black", "base1": "brightblack", "base2": "brightblack",
    "base3": "brightblack", "base4": "brightblack", "base5": "brightblack", "base6": "brightblack",
    "base7": "brightblack", "base8": "white", "fg": "brightwhite", "fg-alt": "white",
    "red": "red", "orange": "brightred", "green": "green", "teal": "brightgreen", "yellow": "yellow",
    "blue": "brightblue", "dark-blue": "blue", "magenta": "brightmagenta", "violet": "magenta",
    "cyan": "brightcyan", "dark-cyan": "cyan",
}

def doom_theme(vname, variant, colors, name=None):
    name = name or THEME_NAMES[vname]
    mode = "dark" if vname == "dark" else "light"
    pal = "\n".join(f'   ({k:<10} \'("{v}" "{v}" "{ANSI16.get(k, "brightmagenta")}"))' for k, v in colors.items())
    slots = "\n".join(f"   ({k:<20} {slot_elisp(v)})" for k, v in variant["slots"].items())
    return f''';;; {name}-theme.el --- laland, a pink theme ({vname}) -*- lexical-binding: t; no-byte-compile: t; -*-
;;
;; Generated by build.py from palette.toml. Edit the palette, not this file.
;;
;;; Code:

(require 'doom-themes)

(def-doom-theme {name}
  "laland ({vname}): blue-tinted ground, vivid accents, pink in the magenta slot."
  :family 'doom-laland
  :background-mode '{mode}

  ;; name        default   256       16
  ({pal.lstrip()}

{slots})

  ;;;; Face overrides
  (((line-number &override) :foreground base4)
   ((line-number-current-line &override) :foreground highlight :weight 'bold)
   (mode-line :background modeline-bg :foreground fg)
   (mode-line-inactive :background modeline-bg-inactive :foreground base5)
   (mode-line-emphasis :foreground highlight)
   ;;;; doom-modeline
   (doom-modeline-bar :background highlight)
   (doom-modeline-buffer-file :inherit 'mode-line-buffer-id :weight 'bold)
   (doom-modeline-buffer-path :inherit 'mode-line-emphasis :weight 'bold)
   (doom-modeline-buffer-project-root :foreground green :weight 'bold)
   ;;;; solaire-mode
   (solaire-mode-line-face :inherit 'mode-line :background modeline-bg)
   (solaire-mode-line-inactive-face :inherit 'mode-line-inactive :background modeline-bg-inactive))

  ;;;; Variable overrides
  ())

;;; {name}-theme.el ends here
'''

# ── firefox ──────────────────────────────────────────────────────────────
# Variable names read from Firefox 157's own chrome CSS (browser/omni.ja: browser-colors.css,
# tabbrowser/tab.tokens.css, design-system tokens). Firefox sets them on :root under
# [lwtheme]/:not([lwtheme]) selectors, so ours carry !important to win.

def firefox_vars(e):
    return {
        "toolbox-background-color": e["bg-alt"], "toolbox-text-color": e["fg"],
        "toolbox-background-color-inactive": e["bg-alt"], "toolbox-text-color-inactive": e["base7"],
        "toolbar-background-color": e["bg"], "toolbar-text-color": e["fg"],
        "toolbar-field-background-color": e["bg-alt"], "toolbar-field-text-color": e["fg"],
        "toolbar-field-border-color": e["base3"],
        "toolbar-field-background-color-focus": e["bg-alt"], "toolbar-field-text-color-focus": e["fg"],
        "toolbar-field-border-color-focus": e["highlight"],
        "urlbar-box-background-color": e["bg-alt"],
        "tab-background-color-selected": e["bg"], "tab-text-color-selected": e["fg"],
        "panel-background-color": e["bg"], "panel-text-color": e["fg"], "panel-border-color": e["base3"],
        "urlbarview-background-color-selected": e["region"], "urlbarview-text-color-selected": e["fg"],
        "sidebar-background-color": e["bg-alt"], "sidebar-text-color": e["fg"], "sidebar-border-color": e["base3"],
        "chrome-content-separator-color": e["base3"],
        "toolbarbutton-icon-fill": e["base7"],
        "toolbarbutton-background-color-hover": e["base2"], "toolbarbutton-background-color-active": e["base3"],
        "color-accent-primary": e["highlight"], "color-accent-primary-hover": lighten(e["highlight"], 0.15),
        "color-accent-primary-active": darken(e["highlight"], 0.1), "button-text-color-primary": e["bg"],
        "focus-outline-color": e["highlight"],
        "newtab-background-color": e["bg"],
    }

def firefox_css(dark, light):
    block = lambda e: "\n".join(f"    --{k}: {v} !important;" for k, v in firefox_vars(e).items())
    return f"""/* laland for Firefox. Generated by build.py from palette.toml. Edit the palette, not this file.
   Imported from userChrome.css; dark by default, light when the system asks for light. */

:root {{
{block(dark)}
}}

@media (prefers-color-scheme: light) {{
  :root {{
{block(light)}
  }}
}}
"""

# about: pages, settings and new tab (userContent.css). Names from Firefox 157's toolkit design-system
# tokens (tokens-shared.css, tokens-platform.css) and the newtab builtin add-on's activity-stream.css.

def firefox_content_vars(e):
    return {
        "background-color-canvas": e["bg"], "text-color": e["fg"], "text-color-deemphasized": e["base7"],
        "background-color-box": e["bg-alt"], "border-color": e["base3"], "border-color-interactive": e["base4"],
        "color-accent-primary": e["highlight"], "color-accent-primary-hover": lighten(e["highlight"], 0.15),
        "color-accent-primary-active": darken(e["highlight"], 0.1),
        "link-color": e["highlight"], "link-color-hover": lighten(e["highlight"], 0.15),
        "button-background-color": e["base2"], "button-background-color-hover": e["base3"],
        "button-background-color-active": blend(e["base3"], e["base4"], 0.5), "button-text-color": e["fg"],
        "button-background-color-primary": e["highlight"], "button-text-color-primary": e["bg"],
        "focus-outline-color": e["highlight"],
        "newtab-background-color": e["bg"], "newtab-background-color-secondary": e["bg-alt"],
        "newtab-text-primary-color": e["fg"], "newtab-text-secondary-color": e["base7"],
        "newtab-primary-action-background": e["highlight"],
    }

def firefox_content_css(dark, light):
    block = lambda e, ind: "\n".join(f"{ind}--{k}: {v} !important;" for k, v in firefox_content_vars(e).items())
    return f"""/* laland for Firefox's own pages (about:, settings, new tab). Generated by build.py from palette.toml.
   Imported from userContent.css. */

@-moz-document url-prefix("about:"), url-prefix("chrome:") {{
  :root {{
    color-scheme: dark !important;
{block(dark, "    ")}
  }}
  @media (prefers-color-scheme: light) {{
    :root {{
      color-scheme: light !important;
{block(light, "      ")}
    }}
  }}
}}
"""

# ── sidebery ─────────────────────────────────────────────────────────────
# Variable names read from Sidebery 5.6.1's styles/sidebar.css. Its Styles editor writes overrides as
# `#root.root {--var: value;}`, so this uses the same selector; paste it into Sidebery's custom CSS.

def sidebery_vars(e):
    return {
        "frame-bg": e["bg-alt"], "frame-fg": e["fg"], "toolbar-bg": e["bg"], "toolbar-fg": e["fg"],
        "popup-bg": e["bg"], "popup-fg": e["fg"], "ctx-menu-bg": e["bg"], "ctx-menu-fg": e["fg"],
        "active-el-bg": e["region"], "active-el-fg": e["fg"],
        "tabs-normal-fg": e["base7"], "tabs-activated-bg": "transparent", "tabs-activated-fg": e["fg"],
        "tabs-activated-shadow": f"inset 0 0 0 2px {e['highlight']}",
        "frame-el-overlay-selected-bg": e["region"], "tabs-progress-bg": e["highlight"],
        "badge-bg": e["highlight"], "badge-fg": e["bg"], "s-accent": e["highlight"],
    }

def sidebery_css(dark, light):
    block = lambda e: "\n".join(f"    --{k}: {v};" for k, v in sidebery_vars(e).items())
    return f"""/* laland for Sidebery. Generated by build.py from palette.toml.
   Paste into Sidebery settings > Styles editor > custom CSS. Set Sidebery's color scheme to "System". */

#root.root {{
{block(dark)}
}}

@media (prefers-color-scheme: light) {{
  #root.root {{
{block(light)}
  }}
}}

/* Container mark (.ctx, a 2px bar at right:0 inside the tab body in Sidebery 5.6.1) moved outside:
   the body is 6px narrower, so the title is clipped inside the pink border, and the bar sits in the
   freed space with a 4px gap: [tab----] | */
#root.root .Tab[data-pin=false] .body {{
    width: calc(100% - 12px);
    margin-left: 6px;  /* same 6px on the left, so the tab sits centered */
}}
#root.root .Tab[data-pin=false] .ctx {{
    right: -6px;
    top: 2px;
    height: calc(100% - 4px);  /* full height minus the 2px border, top and bottom */
}}
"""

# ── kitty ────────────────────────────────────────────────────────────────
# Same keys as the dracula.conf it replaces (~/.config/kitty/dracula.conf).

def kitty_conf(vname, e):
    dark = vname == "dark"
    bright = (lambda c: lighten(c, 0.15)) if dark else (lambda c: darken(c, 0.15))
    black, bblack = (e["base3"], e["base5"]) if dark else (e["base8"], e["base5"])
    white, bwhite = (e["base7"], e["fg"]) if dark else (e["base5"], e["base4"])
    ansi = [black, e["red"], e["green"], e["yellow"], e["blue"], e["magenta"], e["cyan"], white]
    ansi_bright = [bblack] + [bright(c) for c in ansi[1:7]] + [bwhite]
    lines = [
        f"# laland ({vname}) for kitty. Generated by build.py from palette.toml.",
        "",
        f"foreground            {e['fg']}",
        f"background            {e['bg']}",
        f"selection_foreground  {e['fg']}",
        f"selection_background  {e['region']}",
        f"url_color             {e['highlight']}",
        "",
    ]
    for i in range(8):
        lines += [f"color{i:<2} {ansi[i]}", f"color{i + 8:<2} {ansi_bright[i]}"]
    lines += [
        "",
        f"cursor                  {e['highlight']}",
        "cursor_text_color       background",
        "",
        f"active_tab_foreground   {e['highlight']}",
        f"active_tab_background   {e['bg']}",
        f"inactive_tab_foreground {e['base5']}",
        f"inactive_tab_background {e['bg']}",
        "",
        f"mark1_foreground {e['bg']}",
        f"mark1_background {e['red']}",
        "",
        f"active_border_color   {e['highlight']}",
        f"inactive_border_color {e['base4']}",
        "",
    ]
    return "\n".join(lines)

# ── KDE / Qt (and GTK 3 via kde-gtk-config) ──────────────────────────────
# Same sections and keys as /usr/share/color-schemes/BreezeDark.colors (Plasma 6.7.5); the
# ColorEffects blocks are copied from Breeze (identical in its dark and light schemes).

KDE_EFFECTS = """[ColorEffects:Disabled]
Color=56,56,56
ColorAmount=0
ColorEffect=0
ContrastAmount=0.65
ContrastEffect=1
IntensityAmount=0.1
IntensityEffect=2

[ColorEffects:Inactive]
ChangeSelectionColor=true
Color=112,111,110
ColorAmount=0.025
ColorEffect=2
ContrastAmount=0.1
ContrastEffect=2
Enable=false
IntensityAmount=0
IntensityEffect=0
"""

def kde_colors(vname, e):
    rgb = lambda h: ",".join(str(c) for c in hex_to_rgb255(h))
    fgs = dict(
        DecorationFocus=e["highlight"], DecorationHover=e["highlight"], ForegroundActive=e["highlight"],
        ForegroundInactive=e["base7"], ForegroundLink=e["highlight"], ForegroundNegative=e["error"],
        ForegroundNeutral=e["warning"], ForegroundNormal=e["fg"], ForegroundPositive=e["success"],
        ForegroundVisited=e["violet"],
    )
    sets = {
        "Button": (e["base2"], e["base3"], {}),
        "Complementary": (e["base0"], e["bg-alt"], {}),
        "Header": (e["bg"], e["bg-alt"], {}),
        "Header][Inactive": (e["bg-alt"], e["bg"], {}),
        # selection text sits on pink: navy text there, not the light fg
        "Selection": (e["highlight"], e["region"], dict(ForegroundNormal=e["bg"], ForegroundActive=e["bg"],
                                                        ForegroundInactive=e["base3"], ForegroundLink=e["bg"])),
        "Tooltip": (e["base2"], e["bg-alt"], {}),
        "View": (e["bg-alt"], e["base1"], {}),
        "Window": (e["bg"], e["bg-alt"], {}),
    }
    out = [f"# laland ({vname}) for KDE Plasma. Generated by build.py from palette.toml.", "", KDE_EFFECTS]
    for name, (normal, alt, over) in sets.items():
        out.append(f"[Colors:{name}]")
        out.append(f"BackgroundAlternate={rgb(alt)}")
        out.append(f"BackgroundNormal={rgb(normal)}")
        out += [f"{k}={rgb(v)}" for k, v in sorted({**fgs, **over}.items())]
        out.append("")
    scheme = "LalandDark" if vname == "dark" else "LalandLight"
    out += ["[General]", f"ColorScheme={scheme}", f"Name=laland {vname}", "shadeSortColumn=true", "",
            "[KDE]", "contrast=4", "",
            "[WM]", f"activeBackground={rgb(e['bg-alt'])}", f"activeBlend={rgb(e['fg'])}",
            f"activeForeground={rgb(e['fg'])}", f"inactiveBackground={rgb(e['base0'])}",
            f"inactiveBlend={rgb(e['base5'])}", f"inactiveForeground={rgb(e['base5'])}", ""]
    return "\n".join(out)

# ── showcase ─────────────────────────────────────────────────────────────

def swatches_html(vname, colors, specs, f):
    bg = f["bg"]
    out = [f'<div class="sw-set" data-variant="{vname} · {THEME_NAMES[vname]}" '
           f'style="--sw-bg:{bg};--sw-fg:{f["fg"]};--sw-dim:{f["comment"]}">']
    names = list(colors)
    for title, group in (("Ground: bg, bg-alt, base0–8, fg, fg-alt", names[:13]), ("Accents", names[13:])):
        out.append(f'<h4>{title}</h4><div class="sw-grid">')
        for n in group:
            L, C, H, kind = specs[n]
            ch = f"sat {C:.0%}" if kind == "sat" else f"C {C:.3f}"
            out.append(
                f'<div class="sw"><span class="chip" style="background:{colors[n]}"></span>'
                f'<b>{n}</b><code>{colors[n]}</code>'
                f'<small>L {L:.2f} · {ch} · H {H:g}</small><small>Lc {abs(apca(colors[n], bg)):.0f} on bg</small></div>')
        out.append("</div>")
    out.append("</div>")
    return "".join(out)

def slot_table_html(variants_env, slots_src):
    rows = []
    for slot, expr in slots_src["dark"].items():
        if slot in ("vertical-bar", "modeline-bg", "modeline-bg-inactive", "grey"):
            continue
        cells = "".join(
            f'<td><span class="dot" style="background:{variants_env[v][slot]}"></span>'
            f'<code>{variants_env[v][slot]}</code></td>' for v in VARIANTS)
        rows.append(f"<tr><th>{slot}</th><td><code>{expr}</code></td>{cells}</tr>")
    return ('<div class="tbl"><table><thead><tr><th>slot</th><th>value (dark)</th><th>dark</th><th>light</th>'
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")

def css_vars(f):
    return "".join(f"--{k}:{v};" for k, v in f.items())

NUMERIC = re.compile(r'^-?[\d.]+(px|ms)?$')

def main():
    pal = tomllib.loads((ROOT / "palette.toml").read_text())
    res, fails = {}, []
    for v in VARIANTS:
        colors, specs, env = resolve(pal[v])
        f = faces(env)
        fails += check(v, f)
        res[v] = (colors, specs, env, f)

    dist = ROOT / "dist"
    (dist / "emacs").mkdir(parents=True, exist_ok=True)
    (dist / "palette.json").write_text(json.dumps(
        {v: {"colors": res[v][0], "slots": {k: res[v][2][k] for k in pal[v]["slots"]}} for v in VARIANTS},
        indent=2) + "\n")
    for v in VARIANTS:
        (dist / "emacs" / f"{THEME_NAMES[v]}-theme.el").write_text(doom_theme(v, pal[v], res[v][0]))
    (dist / "kde").mkdir(exist_ok=True)
    for v in VARIANTS:
        name = "LalandDark" if v == "dark" else "LalandLight"
        (dist / "kde" / f"{name}.colors").write_text(kde_colors(v, res[v][2]))
    (dist / "kitty").mkdir(exist_ok=True)
    for v in VARIANTS:
        (dist / "kitty" / f"laland-{v}.conf").write_text(kitty_conf(v, res[v][2]))
    (dist / "firefox").mkdir(exist_ok=True)
    (dist / "firefox" / "laland-colors.css").write_text(firefox_css(res["dark"][2], res["light"][2]))
    (dist / "firefox" / "laland-content.css").write_text(firefox_content_css(res["dark"][2], res["light"][2]))
    (dist / "firefox" / "laland-sidebery.css").write_text(sidebery_css(res["dark"][2], res["light"][2]))

    page = (ROOT / "templates" / "showcase.html").read_text()
    # .n spans: numbers keep .n, symbols/booleans/keywords-args become constants (.cn)
    page = re.sub(r'<span class="n">([^<]*)</span>',
                  lambda m: m.group(0) if NUMERIC.match(m.group(1)) else f'<span class="cn">{m.group(1)}</span>', page)
    page = page.replace("/*@VARS_DARK@*/", css_vars(res["dark"][3]))
    page = page.replace("/*@VARS_LIGHT@*/", css_vars(res["light"][3]))
    page = page.replace("<!--@SWATCHES@-->", "".join(swatches_html(v, *res[v][:2], res[v][3]) for v in VARIANTS))
    page = page.replace("<!--@SLOTS@-->", slot_table_html({v: res[v][2] for v in VARIANTS},
                                                          {v: pal[v]["slots"] for v in VARIANTS}))
    (ROOT / "showcase" / "index.html").write_text(page)

    if fails:
        print("\nContrast gate FAILED:\n  " + "\n  ".join(fails))
        sys.exit(1)
    print("\nContrast gate passed.")

if __name__ == "__main__":
    main()
