#!/usr/bin/env bash
# Copy dist/ into place and reload. Doesn't edit any config: see README for the one-time wiring.
set -euo pipefail
cd "$(dirname "$0")"

put() { mkdir -p "$2" && cp -f "$1" "$2/" && echo "$1 -> $2"; }

put dist/emacs/doom-laland-theme.el "${EMACS_THEMES:-$HOME/.config/emacs/themes}"
put dist/nvim/laland.lua "$HOME/.config/nvim/colors"
put dist/kitty/laland-dark.conf "$HOME/.config/kitty"
pkill -USR1 -x kitty || true   # kitty reloads its config on SIGUSR1

if command -v bat >/dev/null; then
    put dist/bat/laland.tmTheme "$(bat --config-dir)/themes"
    bat cache --build >/dev/null
fi

put dist/kde/LalandDark.colors "$HOME/.local/share/color-schemes"
if command -v plasma-apply-colorscheme >/dev/null && [ "$(kreadconfig6 --group General --key ColorScheme)" = LalandDark ]; then
    # re-applying the active scheme is a no-op, so bounce through Breeze to pick up the new file
    plasma-apply-colorscheme BreezeDark >/dev/null
    plasma-apply-colorscheme LalandDark
fi

if [ -d /usr/share/plasma/desktoptheme/klassy-dark ]; then
    scripts/install-plasma-style.sh
fi
