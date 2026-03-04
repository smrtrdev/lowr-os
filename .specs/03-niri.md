# Feature: Niri Window Manager

## Summary

Install and configure Niri as the Wayland compositor — a scrollable-tiling window manager where windows arrange in columns on an infinite horizontal strip. Includes lock screen, idle management, wallpaper, keybindings, and desktop portal configuration.

## Why Niri

- Scrollable tiling: opening a new window never resizes existing ones.
- Workspaces are dynamic and vertical (per-monitor).
- Simple KDL-based config with live reload.
- Built-in screenshot support.
- Lightweight, focused on doing one thing well.

## Requirements

### Packages
- `niri` — Scrollable-tiling Wayland compositor
- `xwayland-satellite` — XWayland support for legacy X11 apps
- `xdg-desktop-portal`, `xdg-desktop-portal-gnome` — Desktop portal for screensharing
- `xdg-utils` — xdg-open and related tools
- `qt6-wayland`, `qt5-wayland` — Qt Wayland support
- `polkit-gnome` — Authentication agent
- `wl-clipboard` — Clipboard utilities (wl-copy, wl-paste)
- `cliphist` — Clipboard history manager
- `swaybg` — Wallpaper
- `swaylock` — Lock screen
- `swayidle` — Idle daemon
- `brightnessctl` — Backlight control
- `playerctl` — Media player control
- `wlsunset` — Night light (blue light filter)
- `grim` — Screenshot (used by niri's built-in screenshot action)
- `slurp` — Region selection (for custom screenshot scripts)
- `wiremix` — TUI audio mixer (launched from waybar)
- `bluetui` (AUR) — TUI bluetooth manager (launched from waybar)
- `impala` (AUR) — TUI wifi manager (launched from waybar)

### Configuration

Niri uses KDL format. Config lives at `~/.config/niri/config.kdl`.

**Important: Niri config assembly strategy**
The niri config is a single `config.kdl` file. Feature scripts that need to add autostart entries (e.g., mako, gnome-keyring-daemon) must be declared in this spec's autostart block. The install script assembles the final config from the template in `config/niri/config.kdl` which includes ALL autostart entries. Individual feature scripts do NOT modify the niri config — they only install their own packages and configs.

**Input:**
```kdl
input {
    keyboard {
        xkb {
            layout "us"
        }
    }
    touchpad {
        tap
        natural-scroll
    }
    mouse {
        accel-profile "flat"
    }
}
```

**Cursor:**
```kdl
cursor {
    theme "catppuccin-mocha-dark-cursors"
    size 24
}
```

**Layout:**
```kdl
layout {
    gaps 8
    center-focused-column "on-overflow"

    preset-column-widths {
        proportion 0.33333
        proportion 0.5
        proportion 0.66667
    }

    default-column-width {
        proportion 0.5
    }

    focus-ring {
        width 2
        active-color "#89b4fa"
        inactive-color "#313244"
    }

    border {
        off
    }

    shadow {
        on
    }
}
```

**Screenshot path:**
```kdl
screenshot-path "~/Pictures/Screenshots/%Y-%m-%d_%H-%M-%S.png"
```

The install script must ensure `~/Pictures/Screenshots/` directory exists.

**Animations:**
- Use niri defaults (they're good out of the box), or disable specific ones if too distracting.

**Key Bindings:**

Niri loads **no default bindings** — everything must be declared explicitly.

```kdl
binds {
    // App launchers
    Mod+Return { spawn "ghostty"; }
    Mod+D { spawn "walker"; }
    Mod+E { spawn "nautilus"; }

    // Clipboard history
    Mod+V { spawn-sh "cliphist list | walker --dmenu | cliphist decode | wl-copy"; }

    // Window management
    Mod+Q { close-window; }
    Mod+F { maximize-column; }
    Mod+Shift+F { fullscreen-window; }
    Mod+Shift+Space { toggle-window-floating; }
    Mod+C { center-column; }

    // Focus
    Mod+H { focus-column-left; }
    Mod+L { focus-column-right; }
    Mod+J { focus-window-down; }
    Mod+K { focus-window-up; }

    // Move windows
    Mod+Shift+H { move-column-left; }
    Mod+Shift+L { move-column-right; }
    Mod+Shift+J { move-window-down; }
    Mod+Shift+K { move-window-up; }

    // Resize
    Mod+Minus { set-column-width "-10%"; }
    Mod+Equal { set-column-width "+10%"; }
    Mod+Shift+Minus { set-window-height "-10%"; }
    Mod+Shift+Equal { set-window-height "+10%"; }

    // Preset widths
    Mod+R { switch-preset-column-width; }

    // Workspaces (dynamic, vertical)
    Mod+1 { focus-workspace 1; }
    Mod+2 { focus-workspace 2; }
    Mod+3 { focus-workspace 3; }
    Mod+4 { focus-workspace 4; }
    Mod+5 { focus-workspace 5; }
    Mod+6 { focus-workspace 6; }
    Mod+7 { focus-workspace 7; }
    Mod+8 { focus-workspace 8; }
    Mod+9 { focus-workspace 9; }
    Mod+Shift+1 { move-column-to-workspace 1; }
    Mod+Shift+2 { move-column-to-workspace 2; }
    Mod+Shift+3 { move-column-to-workspace 3; }
    Mod+Shift+4 { move-column-to-workspace 4; }
    Mod+Shift+5 { move-column-to-workspace 5; }
    Mod+Shift+6 { move-column-to-workspace 6; }
    Mod+Shift+7 { move-column-to-workspace 7; }
    Mod+Shift+8 { move-column-to-workspace 8; }
    Mod+Shift+9 { move-column-to-workspace 9; }

    // Scroll through workspaces
    Mod+WheelScrollDown cooldown-ms=150 { focus-workspace-down; }
    Mod+WheelScrollUp cooldown-ms=150 { focus-workspace-up; }

    // Screenshots (niri built-in)
    Print { screenshot; }
    Mod+Print { screenshot-screen; }
    Mod+Shift+Print { screenshot-window; }

    // Notifications
    Mod+N { spawn "makoctl" "dismiss" "--all"; }

    // Lock
    Mod+Escape { spawn "swaylock"; }

    // Night light toggle
    Mod+Shift+N { spawn-sh "pkill wlsunset || wlsunset -l 48.2 -L 16.4"; }

    // Media keys
    XF86AudioRaiseVolume { spawn "wpctl" "set-volume" "@DEFAULT_AUDIO_SINK@" "0.05+"; }
    XF86AudioLowerVolume { spawn "wpctl" "set-volume" "@DEFAULT_AUDIO_SINK@" "0.05-"; }
    XF86AudioMute { spawn "wpctl" "set-mute" "@DEFAULT_AUDIO_SINK@" "toggle"; }
    XF86AudioMicMute { spawn "wpctl" "set-mute" "@DEFAULT_AUDIO_SOURCE@" "toggle"; }
    XF86MonBrightnessUp { spawn "brightnessctl" "set" "+5%"; }
    XF86MonBrightnessDown { spawn "brightnessctl" "set" "5%-"; }
    XF86AudioPlay { spawn "playerctl" "play-pause"; }
    XF86AudioNext { spawn "playerctl" "next"; }
    XF86AudioPrev { spawn "playerctl" "previous"; }

    // Quit niri
    Mod+Shift+E { quit; }
}
```

**Autostart (spawn-at-startup):**

This is the canonical list of all autostart entries. Other feature specs reference this list but do not modify the niri config directly.

```kdl
spawn-at-startup "waybar"
spawn-at-startup "swaybg" "-i" "$SMRTR_WALLPAPER" "-m" "fill"
spawn-at-startup "swayidle" "-w" "timeout" "300" "swaylock -f" "timeout" "600" "niri msg action power-off-monitors" "resume" "niri msg action power-on-monitors"
spawn-at-startup "mako"
spawn-at-startup "wl-paste" "--watch" "cliphist" "store"
spawn-at-startup "/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1"
spawn-at-startup "xwayland-satellite"
spawn-at-startup "gnome-keyring-daemon" "--start" "--components=secrets,ssh"
spawn-at-startup "wlsunset" "-l" "48.2" "-L" "16.4"
```

Note: `$SMRTR_WALLPAPER` is a placeholder — the install script substitutes it with the actual path (e.g., `~/.config/smrtr/wallpapers/default.jpg`). The `wlsunset` latitude/longitude defaults should be replaced by the user or auto-detected from timezone.

**Window Rules:**
```kdl
window-rule {
    match app-id="org.gnome.Nautilus"
    default-column-width { proportion 0.5; }
}

window-rule {
    match app-id="zen-browser"
    default-column-width { proportion 0.66667; }
}

// Float dialogs, polkit, small windows
window-rule {
    match is-floating=true
    shadow { on; }
    geometry-corner-radius 8 8 8 8
}
```

**Monitor Config:**
```kdl
// Auto-detect (default behavior, no config needed)
// User can add specific output config:
// output "eDP-1" {
//     scale 1.0
//     mode "1920x1080@60"
// }
```

**Environment Variables (compositor-specific only):**
```kdl
environment {
    DISPLAY ":0"
}
```

General env vars (`EDITOR`, `BROWSER`, `QT_QPA_PLATFORMTHEME`, `XDG_*`, etc.) are set in `~/.config/environment.d/smrtr.conf` (see spec 02 environment variable strategy). They are NOT duplicated here.

### Desktop Portal Configuration

**`~/.config/xdg-desktop-portal/portals.conf`:**
```ini
[preferred]
default=gnome
org.freedesktop.impl.portal.Screenshot=gnome
org.freedesktop.impl.portal.ScreenCast=gnome
```

This ensures screen sharing works in browsers (video calls, etc.).

### Lock Screen (swaylock)

**~/.config/swaylock/config:**
```
daemonize
color=1e1e2e
inside-color=31324400
ring-color=89b4fa
key-hl-color=a6e3a1
text-color=cdd6f4
line-color=00000000
separator-color=00000000
layout-text-color=cdd6f4
```

### Lid Close / Power Behavior

Configure `logind.conf` for laptop lid behavior:

**`/etc/systemd/logind.conf.d/smrtr.conf`:**
```ini
[Login]
HandleLidSwitch=suspend
HandleLidSwitchExternalPower=ignore
HandlePowerKey=poweroff
IdleAction=suspend
IdleActionSec=30min
```

### Wallpaper
- Include a default dark wallpaper in `config/wallpapers/default.jpg`
- Copied to `~/.config/smrtr/wallpapers/default.jpg` during install
- Set via swaybg in spawn-at-startup

## Acceptance Criteria

- After running the script and starting Niri (`niri-session` from TTY or display manager), the user gets a working scrollable-tiling desktop.
- All keybindings work as specified.
- New windows open to the right without resizing existing windows.
- Column width cycling works with `Mod+R`.
- Lock screen activates on `Mod+Escape` and after idle timeout.
- Screenshots save to `~/Pictures/Screenshots/` and clipboard.
- Volume/brightness keys work.
- XWayland apps work via xwayland-satellite.
- Clipboard history accessible via `Mod+V`.
- `Mod+N` dismisses notifications.
- `Mod+E` opens file manager.
- Screen sharing works in browsers (portal configured).
- Laptop lid close suspends the system.
- Cursor theme is consistent across Wayland and XWayland apps.
- Night light (wlsunset) runs at startup and can be toggled with `Mod+Shift+N`.

## Dependencies

- `01-base-packages` (GPU drivers, wayland libs)

## References

- https://github.com/niri-wm/niri
- https://wiki.archlinux.org/title/Niri
- https://github.com/niri-wm/niri/wiki/Overview
