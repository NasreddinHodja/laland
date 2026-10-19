#!/usr/bin/env python3
"""laland build: palette.toml -> hex, APCA contrast report, every app's theme file in dist/.

Color math: OKLCH -> sRGB (Björn Ottosson, bottosson.github.io/posts/oklab).
doom helpers: ported from doom-themes.el:301-343 (sRGB blend).
Derived faces: as doom-themes-base.el:34-60 builds them from the slots.
"""
import json
import math
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VARIANTS = ("dark",)  # [light] in palette.toml is kept for later; it is not built
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
        "toolbarbutton-icon-fill": e["base7"], "toolbarbutton-icon-fill-attention": e["highlight"],
        "toolbarbutton-background-color-hover": e["base2"], "toolbarbutton-background-color-active": e["base3"],
        "color-accent-primary": e["highlight"], "color-accent-primary-hover": lighten(e["highlight"], 0.15),
        "color-accent-primary-active": darken(e["highlight"], 0.1), "button-text-color-primary": e["bg"],
        "focus-outline-color": e["highlight"],
        "newtab-background-color": e["bg"],
    }

def firefox_css(dark):
    block = lambda e: "\n".join(f"    --{k}: {v} !important;" for k, v in firefox_vars(e).items())
    return f"""/* laland for Firefox. Generated by build.py from palette.toml. Edit the palette, not this file.
   Imported from userChrome.css. */

:root {{
{block(dark)}
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

def firefox_content_css(dark):
    block = lambda e, ind: "\n".join(f"{ind}--{k}: {v} !important;" for k, v in firefox_content_vars(e).items())
    return f"""/* laland for Firefox's own pages (about:, settings, new tab). Generated by build.py from palette.toml.
   Imported from userContent.css. */

@-moz-document url-prefix("about:"), url-prefix("chrome:") {{
  :root {{
    color-scheme: dark !important;
{block(dark, "    ")}
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

def sidebery_css(dark):
    block = lambda e: "\n".join(f"    --{k}: {v};" for k, v in sidebery_vars(e).items())
    return f"""/* laland for Sidebery. Generated by build.py from palette.toml.
   Paste into Sidebery settings > Styles editor > custom CSS. Set Sidebery's color scheme to "System". */

#root.root {{
{block(dark)}
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

# ── neovim ───────────────────────────────────────────────────────────────
# Native colorscheme (no plugin). Treesitter captures get the same roles as the Emacs theme, using
# the doom-derived colors from faces() (function calls 70% functions, punctuation 25% operators...).

def nvim_colors(vname, e, f):
    name = "laland" if vname == "dark" else "laland-light"
    bright = (lambda c: lighten(c, 0.15)) if vname == "dark" else (lambda c: darken(c, 0.15))
    black, white = (e["base3"], e["base7"]) if vname == "dark" else (e["base8"], e["base5"])
    ansi = [black, e["red"], e["green"], e["yellow"], e["blue"], e["magenta"], e["cyan"], white]
    ansi += [e["base5"]] + [bright(c) for c in ansi[1:7]] + [e["fg"] if vname == "dark" else e["base4"]]
    g = {
        # editor
        "Normal": dict(fg=f["fg"], bg=e["bg"]), "NormalFloat": dict(fg=f["fg"], bg=e["bg-alt"]),
        "FloatBorder": dict(fg=e["highlight"], bg=e["bg-alt"]), "ColorColumn": dict(bg=e["bg-alt"]),
        "CursorLine": dict(bg=e["bg-alt"]), "CursorColumn": dict(bg=e["bg-alt"]), "Cursor": dict(fg=e["bg"], bg=e["highlight"]),
        "LineNr": dict(fg=f["linenr"]), "CursorLineNr": dict(fg=e["highlight"], bold=True),
        "SignColumn": dict(bg=e["bg"]), "FoldColumn": dict(fg=f["linenr"]), "Folded": dict(fg=f["comment"], bg=e["bg-alt"]),
        "Visual": dict(bg=e["region"]), "Search": dict(fg=e["bg"], bg=e["yellow"]), "IncSearch": dict(fg=e["bg"], bg=e["highlight"]),
        "CurSearch": dict(fg=e["bg"], bg=e["highlight"]), "MatchParen": dict(fg=e["highlight"], bold=True, underline=True),
        "Pmenu": dict(fg=f["fg"], bg=e["bg-alt"]), "PmenuSel": dict(fg=e["bg"], bg=e["highlight"]),
        "PmenuSbar": dict(bg=e["bg-alt"]), "PmenuThumb": dict(bg=e["base4"]),
        "StatusLine": dict(fg=f["fg"], bg=e["modeline-bg"]), "StatusLineNC": dict(fg=e["base5"], bg=e["modeline-bg-inactive"]),
        "WinSeparator": dict(fg=e["base3"]), "VertSplit": dict(fg=e["base3"]), "TabLine": dict(fg=e["base5"], bg=e["bg-alt"]),
        "TabLineSel": dict(fg=f["fg"], bg=e["bg"]), "TabLineFill": dict(bg=e["bg-alt"]), "Title": dict(fg=e["highlight"], bold=True),
        "NonText": dict(fg=e["base4"]), "Whitespace": dict(fg=e["base3"]), "EndOfBuffer": dict(fg=e["bg"]),
        "Directory": dict(fg=e["blue"]), "Question": dict(fg=e["green"]), "MoreMsg": dict(fg=e["green"]),
        "ErrorMsg": dict(fg=e["error"]), "WarningMsg": dict(fg=e["warning"]), "ModeMsg": dict(fg=f["fg"], bold=True),
        "SpellBad": dict(sp=e["error"], undercurl=True), "SpellCap": dict(sp=e["warning"], undercurl=True),
        "DiffAdd": dict(bg=f["added-bg"]), "DiffDelete": dict(fg=e["vc-deleted"], bg=f["deleted-bg"]),
        "DiffChange": dict(bg=blend(e["vc-modified"], e["bg"], 0.15)), "DiffText": dict(bg=blend(e["vc-modified"], e["bg"], 0.3)),
        "DiagnosticError": dict(fg=e["error"]), "DiagnosticWarn": dict(fg=e["warning"]),
        "DiagnosticInfo": dict(fg=e["cyan"]), "DiagnosticHint": dict(fg=f["comment"]),
        "DiagnosticUnderlineError": dict(sp=e["error"], undercurl=True), "DiagnosticUnderlineWarn": dict(sp=e["warning"], undercurl=True),
        "DiagnosticUnderlineInfo": dict(sp=e["cyan"], undercurl=True), "DiagnosticUnderlineHint": dict(sp=f["comment"], undercurl=True),
        # syntax, legacy groups
        "Comment": dict(fg=f["comment"], italic=True), "Constant": dict(fg=f["constant"]), "String": dict(fg=f["string"]),
        "Character": dict(fg=f["string"]), "Number": dict(fg=f["number"]), "Boolean": dict(fg=f["constant"]),
        "Float": dict(fg=f["number"]), "Identifier": dict(fg=f["param"]), "Function": dict(fg=f["function"]),
        "Statement": dict(fg=f["keyword"]), "Keyword": dict(fg=f["keyword"]), "Conditional": dict(fg=f["keyword"]),
        "Repeat": dict(fg=f["keyword"]), "Label": dict(fg=f["keyword"]), "Exception": dict(fg=f["keyword"]),
        "Operator": dict(fg=f["operator"]), "PreProc": dict(fg=f["keyword"]), "Include": dict(fg=f["keyword"]),
        "Type": dict(fg=f["type"]), "StorageClass": dict(fg=f["keyword"]), "Structure": dict(fg=f["type"]),
        "Special": dict(fg=f["builtin"]), "SpecialChar": dict(fg=f["escape"]), "Delimiter": dict(fg=f["punct"]),
        "Tag": dict(fg=f["keyword"]), "Todo": dict(fg=e["bg"], bg=e["warning"], bold=True), "Error": dict(fg=e["error"]),
        "Underlined": dict(underline=True),
        # treesitter
        "@comment": dict(link="Comment"), "@keyword": dict(fg=f["keyword"]), "@keyword.function": dict(fg=f["keyword"]),
        "@keyword.return": dict(fg=f["keyword"]), "@keyword.operator": dict(fg=f["keyword"]),
        "@function": dict(fg=f["function"]), "@function.call": dict(fg=f["fcall"], italic=True),
        "@function.method": dict(fg=f["function"]), "@function.method.call": dict(fg=f["fcall"], italic=True),
        "@function.builtin": dict(fg=f["builtin"]), "@constructor": dict(fg=f["type"]),
        "@type": dict(fg=f["type"]), "@type.builtin": dict(fg=f["builtin"]), "@module": dict(fg=f["type"]),
        "@string": dict(fg=f["string"]), "@string.escape": dict(fg=f["escape"], bold=True), "@string.regexp": dict(fg=f["escape"]),
        "@number": dict(fg=f["number"]), "@number.float": dict(fg=f["number"]), "@boolean": dict(fg=f["constant"]),
        "@constant": dict(fg=f["constant"]), "@constant.builtin": dict(fg=f["constant"]),
        "@variable": dict(fg=f["fg"]), "@variable.builtin": dict(fg=f["builtin"]), "@variable.parameter": dict(fg=f["param"]),
        "@variable.member": dict(fg=f["property"]), "@property": dict(fg=f["property"]),
        "@operator": dict(fg=f["operator"]), "@punctuation": dict(fg=f["punct"]), "@punctuation.bracket": dict(fg=f["punct"]),
        "@punctuation.delimiter": dict(fg=f["punct"]), "@tag": dict(fg=f["keyword"]), "@tag.attribute": dict(fg=f["type"]),
        "@tag.delimiter": dict(fg=f["punct"]), "@attribute": dict(fg=f["builtin"]),
        "@markup.heading": dict(fg=e["highlight"], bold=True), "@markup.link": dict(fg=e["highlight"], underline=True),
        "@markup.raw": dict(fg=f["string"]), "@markup.strong": dict(bold=True), "@markup.italic": dict(italic=True),
        "@diff.plus": dict(fg=e["vc-added"]), "@diff.minus": dict(fg=e["vc-deleted"]), "@diff.delta": dict(fg=e["vc-modified"]),
    }
    def attrs(d):
        return ", ".join(f'{k} = "{v}"' if isinstance(v, str) else f"{k} = {str(v).lower()}" for k, v in d.items())
    lines = [f"-- {name} for Neovim. Generated by build.py from palette.toml. Edit the palette, not this file.",
             "vim.cmd('highlight clear')", "if vim.fn.exists('syntax_on') then vim.cmd('syntax reset') end",
             f"vim.o.background = '{'dark' if vname == 'dark' else 'light'}'", f"vim.g.colors_name = '{name}'",
             "local hl = function(group, opts) vim.api.nvim_set_hl(0, group, opts) end"]
    lines += [f'hl("{k}", {{ {attrs(v)} }})' for k, v in g.items()]
    lines += [f'vim.g.terminal_color_{i} = "{c}"' for i, c in enumerate(ansi)]
    return name, "\n".join(lines) + "\n"

# ── bat (TextMate theme) ─────────────────────────────────────────────────

def bat_theme(vname, e, f):
    name = "laland" if vname == "dark" else "laland-light"
    scopes = [
        ("Comment", "comment, punctuation.definition.comment", f["comment"], "italic"),
        ("String", "string, punctuation.definition.string", f["string"], ""),
        ("Escape", "constant.character.escape, string.regexp", f["escape"], "bold"),
        ("Number", "constant.numeric", f["number"], ""),
        ("Constant", "constant.language, constant.other, support.constant", f["constant"], ""),
        ("Keyword", "keyword, storage, storage.modifier, keyword.control", f["keyword"], ""),
        ("Operator", "keyword.operator", f["operator"], ""),
        ("Storage type", "storage.type", f["keyword"], ""),
        ("Function", "entity.name.function, meta.function-call entity.name.function", f["function"], ""),
        ("Function call", "variable.function, support.function", f["fcall"], "italic"),
        ("Builtin", "support.function.builtin, variable.language, support.type.builtin", f["builtin"], ""),
        ("Type", "entity.name.type, entity.name.class, support.type, support.class, entity.other.inherited-class", f["type"], ""),
        ("Parameter", "variable.parameter", f["param"], ""),
        ("Property", "variable.other.member, variable.other.property, meta.object-literal.key, support.type.property-name", f["property"], ""),
        ("Punctuation", "punctuation, meta.brace", f["punct"], ""),
        ("Tag", "entity.name.tag", f["keyword"], ""),
        ("Attribute", "entity.other.attribute-name", f["type"], ""),
        ("Heading", "markup.heading, entity.name.section", e["highlight"], "bold"),
        ("Link", "markup.underline.link, string.other.link", e["highlight"], "underline"),
        ("Inserted", "markup.inserted", e["vc-added"], ""),
        ("Deleted", "markup.deleted", e["vc-deleted"], ""),
        ("Changed", "markup.changed", e["vc-modified"], ""),
        ("Invalid", "invalid", e["error"], ""),
    ]
    def item(n, scope, fg, style):
        s = f"<key>fontStyle</key><string>{style}</string>" if style else ""
        return (f"<dict><key>name</key><string>{n}</string><key>scope</key><string>{scope}</string>"
                f"<key>settings</key><dict><key>foreground</key><string>{fg}</string>{s}</dict></dict>")
    general = dict(background=e["bg"], foreground=f["fg"], caret=e["highlight"], selection=e["region"],
                   lineHighlight=e["bg-alt"], gutterForeground=f["linenr"], invisibles=e["base4"])
    gen = "".join(f"<key>{k}</key><string>{v}</string>" for k, v in general.items())
    body = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!-- laland for bat. Generated by build.py from palette.toml. -->\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            f'<plist version="1.0"><dict><key>name</key><string>{name}</string><key>settings</key><array>'
            f'<dict><key>settings</key><dict>{gen}</dict></dict>'
            + "".join(item(*s) for s in scopes) + "</array></dict></plist>\n")
    return name, body

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
    (dist / "nvim").mkdir(exist_ok=True)
    (dist / "bat").mkdir(exist_ok=True)
    for v in VARIANTS:
        name, lua = nvim_colors(v, res[v][2], res[v][3])
        (dist / "nvim" / f"{name}.lua").write_text(lua)
        name, tm = bat_theme(v, res[v][2], res[v][3])
        (dist / "bat" / f"{name}.tmTheme").write_text(tm)
    (dist / "kde").mkdir(exist_ok=True)
    for v in VARIANTS:
        name = "LalandDark" if v == "dark" else "LalandLight"
        (dist / "kde" / f"{name}.colors").write_text(kde_colors(v, res[v][2]))
    (dist / "kitty").mkdir(exist_ok=True)
    for v in VARIANTS:
        (dist / "kitty" / f"laland-{v}.conf").write_text(kitty_conf(v, res[v][2]))
    (dist / "firefox").mkdir(exist_ok=True)
    (dist / "firefox" / "laland-colors.css").write_text(firefox_css(res["dark"][2]))
    (dist / "firefox" / "laland-content.css").write_text(firefox_content_css(res["dark"][2]))
    (dist / "firefox" / "laland-sidebery.css").write_text(sidebery_css(res["dark"][2]))

    if fails:
        print("\nContrast gate FAILED:\n  " + "\n  ".join(fails))
        sys.exit(1)
    print("\nContrast gate passed.")

if __name__ == "__main__":
    main()
