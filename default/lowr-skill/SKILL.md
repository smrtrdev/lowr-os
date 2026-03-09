---
name: lowr
description: >
  REQUIRED for end-user customization of Linux desktop, window manager, or system config.
  Use when editing ~/.config/hypr/, ~/.config/waybar/, ~/.config/walker/,
  ~/.config/alacritty/, ~/.config/kitty/, ~/.config/ghostty/, ~/.config/mako/,
  or ~/.config/lowr/. Triggers: Hyprland, window rules, animations, keybindings,
  monitors, gaps, borders, blur, opacity, waybar, walker, terminal config, themes,
  wallpaper, night light, idle, lock screen, screenshots, layer rules, workspace
  settings, display config, and user-facing lowr commands. Excludes Lowr
  source development in ~/.local/share/lowr/ and lowr-dev-* workflows.
---

# Lowr Skill

Manage [Lowr](https://lowr.org/) Linux systems - a beautiful, modern, opinionated Arch Linux distribution with Hyprland.

This skill is for end-user customization on installed systems.
It is not for contributing to Lowr source code.

## When This Skill MUST Be Used

**ALWAYS invoke this skill for end-user requests involving ANY of these:**

- Editing ANY file in `~/.config/hypr/` (window rules, animations, keybindings, monitors, etc.)
- Editing ANY file in `~/.config/waybar/`, `~/.config/walker/`, `~/.config/mako/`
- Editing terminal configs (alacritty, kitty, ghostty)
- Editing ANY file in `~/.config/lowr/`
- Window behavior, animations, opacity, blur, gaps, borders
- Layer rules, workspace settings, display/monitor configuration
- Themes, wallpapers, fonts, appearance changes
- User-facing `lowr-*` commands (`lowr-theme-*`, `lowr-refresh-*`, `lowr-restart-*`, etc.)
- Screenshots, screen recording, night light, idle behavior, lock screen

**If you're about to edit a config file in ~/.config/ on this system, STOP and use this skill first.**

**Do NOT use this skill for Lowr development tasks** (editing files in `~/.local/share/lowr/`, creating migrations, or running `lowr-dev-*` workflows).

## Critical Safety Rules

**For end-user customization tasks, NEVER modify anything in `~/.local/share/lowr/`** - but READING is safe and encouraged.

This directory contains Lowr's source files managed by git. Any changes will be:
- Lost on next `lowr-update`
- Cause conflicts with upstream
- Break the system's update mechanism

```
~/.local/share/lowr/     # READ-ONLY - NEVER EDIT (reading is OK)
├── bin/                    # Source scripts (symlinked to PATH)
├── config/                 # Default config templates
├── themes/                 # Stock themes
├── default/                # System defaults
├── migrations/             # Update migrations
└── install/                # Installation scripts
```

**Reading `~/.local/share/lowr/` is SAFE and useful** - do it freely to:
- Understand how lowr commands work: `cat $(which lowr-theme-set)`
- See default configs before customizing: `cat ~/.local/share/lowr/config/waybar/config.jsonc`
- Check stock theme files to copy for customization
- Reference default hyprland settings: `cat ~/.local/share/lowr/default/hypr/*`

**Always use these safe locations instead:**
- `~/.config/` - User configuration (safe to edit)
- `~/.config/lowr/themes/<custom-name>/` - Custom themes (must be real directories)
- `~/.config/lowr/hooks/` - Custom automation hooks

If the request is to develop Lowr itself, this skill is out of scope. Follow repository development instructions instead of this skill.

## System Architecture

Lowr is built on:

| Component | Purpose | Config Location |
|-----------|---------|-----------------|
| **Arch Linux** | Base OS | `/etc/`, `~/.config/` |
| **Hyprland** | Wayland compositor/WM | `~/.config/hypr/` |
| **Waybar** | Status bar | `~/.config/waybar/` |
| **Walker** | App launcher | `~/.config/walker/` |
| **Alacritty/Kitty/Ghostty** | Terminals | `~/.config/<terminal>/` |
| **Mako** | Notifications | `~/.config/mako/` |
| **SwayOSD** | On-screen display | `~/.config/swayosd/` |

## Command Discovery

Lowr provides ~145 commands following `lowr-<category>-<action>` pattern.

```bash
# List all lowr commands
compgen -c | grep -E '^lowr-' | sort -u

# Find commands by category
compgen -c | grep -E '^lowr-theme'
compgen -c | grep -E '^lowr-restart'

# Read a command's source to understand it
cat $(which lowr-theme-set)
```

### Command Categories

| Prefix | Purpose | Example |
|--------|---------|---------|
| `lowr-refresh-*` | Reset config to defaults (backs up first) | `lowr-refresh-waybar` |
| `lowr-restart-*` | Restart a service/app | `lowr-restart-waybar` |
| `lowr-toggle-*` | Toggle feature on/off | `lowr-toggle-nightlight` |
| `lowr-theme-*` | Theme management | `lowr-theme-set <name>` |
| `lowr-install-*` | Install optional software | `lowr-install-docker-dbs` |
| `lowr-launch-*` | Launch apps | `lowr-launch-browser` |
| `lowr-cmd-*` | System commands | `lowr-cmd-screenshot` |
| `lowr-pkg-*` | Package management | `lowr-pkg-install <pkg>` |
| `lowr-setup-*` | Initial setup tasks | `lowr-setup-fingerprint` |
| `lowr-update-*` | System updates | `lowr-update` |

## Configuration Locations

### Hyprland (Window Manager)

```
~/.config/hypr/
├── hyprland.conf      # Main config (sources others)
├── bindings.conf      # Keybindings
├── monitors.conf      # Display configuration
├── input.conf         # Keyboard/mouse settings
├── looknfeel.conf     # Appearance (gaps, borders, animations)
├── envs.conf          # Environment variables
├── autostart.conf     # Startup applications
├── hypridle.conf      # Idle behavior (screen off, lock, suspend)
├── hyprlock.conf      # Lock screen appearance
└── hyprsunset.conf    # Night light / blue light filter
```

**Key behaviors:**
- Hyprland auto-reloads on config save (no restart needed for most changes)
- Use `hyprctl reload` to force reload
- Use `lowr-refresh-niri` to reset to defaults

### Waybar (Status Bar)

```
~/.config/waybar/
├── config.jsonc       # Bar layout and modules (JSONC format)
└── style.css          # Styling
```

**Waybar does NOT auto-reload.** You MUST run `lowr-restart-waybar` after any config changes.

**Commands:** `lowr-restart-waybar`, `lowr-refresh-waybar`, `lowr-toggle-waybar`

### Terminals

```
~/.config/alacritty/alacritty.toml
~/.config/kitty/kitty.conf
~/.config/ghostty/config
```

**Command:** `lowr-restart-terminal`

### Other Configs

| App | Location |
|-----|----------|
| btop | `~/.config/btop/btop.conf` |
| fastfetch | `~/.config/fastfetch/config.jsonc` |
| lazygit | `~/.config/lazygit/config.yml` |
| starship | `~/.config/starship.toml` |
| git | `~/.config/git/config` |
| walker | `~/.config/walker/config.toml` |

## Safe Customization Patterns

### Pattern 1: Edit User Config Directly

For simple changes, edit files in `~/.config/`:

```bash
# 1. Read current config
cat ~/.config/hypr/bindings.conf

# 2. Backup before changes
cp ~/.config/hypr/bindings.conf ~/.config/hypr/bindings.conf.bak.$(date +%s)

# 3. Make changes with Edit tool

# 4. Apply changes
# - Hyprland: auto-reloads on save (no restart needed)
# - Waybar: MUST restart with lowr-restart-waybar
# - Walker: MUST restart with lowr-restart-walker
# - Terminals: MUST restart with lowr-restart-terminal
```

### Pattern 2: Make a new theme

1. Create a directory under ~/.config/lowr/themes.
2. See how an existing theme is done via ~/.local/share/lowr/themes/catppuccin.
3. Download a matching background (or several) from the internet and put them in ~/.config/lowr/themes/[name-of-new-theme]
4. When done with the theme, run lowr-theme-set "Name of new theme"

### Pattern 3: Use Hooks for Automation

Create scripts in `~/.config/lowr/hooks/` to run automatically on events:

```bash
# Available hooks (see samples in ~/.config/lowr/hooks/):
~/.config/lowr/hooks/
├── theme-set        # Runs after theme change (receives theme name as $1)
├── font-set         # Runs after font change
└── post-update      # Runs after lowr-update
```

Example hook (`~/.config/lowr/hooks/theme-set`):
```bash
#!/bin/bash
THEME_NAME=$1
echo "Theme changed to: $THEME_NAME"
# Add custom actions here
```

### Pattern 4: Reset to Defaults -- ALWAYS SEEK USER CONFIRMATION BEFORE RUNNING

When customizations go wrong:

```bash
# Reset specific config (creates backup automatically)
lowr-refresh-waybar
lowr-refresh-niri

# The refresh command:
# 1. Backs up current config with timestamp
# 2. Copies default from ~/.local/share/lowr/config/
# 3. Restarts the component
```

## Common Tasks

### Themes

```bash
lowr-theme-list              # Show available themes
lowr-theme-current           # Show current theme
lowr-theme-set <name>        # Apply theme (use "Tokyo Night" not "tokyo-night")
lowr-theme-next              # Cycle to next theme
lowr-theme-bg-next           # Cycle wallpaper
lowr-theme-install <url>     # Install from git repo
```

### Keybindings

Edit `~/.config/hypr/bindings.conf`. Format:
```
bind = SUPER, Return, exec, xdg-terminal-exec
bind = SUPER, Q, killactive
bind = SUPER SHIFT, E, exit
```

View current bindings: `lowr-menu-keybindings --print`

**IMPORTANT: When re-binding an existing key:**

1. First check existing bindings: `lowr-menu-keybindings --print`
2. If the key is already bound, you MUST add an `unbind` directive BEFORE your new `bind`
3. Inform the user what the key was previously bound to

Example - rebinding SUPER+F (which is bound to fullscreen by default):
```
# Unbind existing SUPER+F (was: fullscreen)
unbind = SUPER, F
# New binding for file manager
bind = SUPER, F, exec, nautilus
```

Always tell the user: "Note: SUPER+F was previously bound to fullscreen. I've added an unbind directive to override it."

### Display/Monitors

Edit `~/.config/hypr/monitors.conf`. Format:
```
monitor = eDP-1, 1920x1080@60, 0x0, 1
monitor = HDMI-A-1, 2560x1440@144, 1920x0, 1
```

List monitors: `hyprctl monitors`

### Window Rules

**CRITICAL: Hyprland window rules syntax changes frequently between versions.**

Before writing ANY window rules, you MUST fetch the current documentation from the official Hyprland wiki:
- https://github.com/hyprwm/hyprland-wiki/blob/main/content/Configuring/Window-Rules.md

DO NOT rely on cached or memorized window rule syntax. The format has changed multiple times and using outdated syntax will cause errors or unexpected behavior.

Window rules go in `~/.config/hypr/hyprland.conf` or a sourced file. Always verify the current syntax from the wiki first.

### Fonts

```bash
lowr-font-list               # Available fonts
lowr-font-current            # Current font
lowr-font-set <name>         # Change font
```

### System

```bash
lowr-update                  # Full system update
lowr-version                 # Show Lowr version
lowr-debug --no-sudo --print # Debug info (ALWAYS use these flags)
lowr-lock-screen             # Lock screen
lowr-system-shutdown         # Shutdown
lowr-system-reboot           # Reboot
```

**IMPORTANT:** Always run `lowr-debug` with `--no-sudo --print` flags to avoid interactive sudo prompts that will hang the terminal.

## Troubleshooting

```bash
# Get debug information (ALWAYS use these flags to avoid interactive prompts)
lowr-debug --no-sudo --print

# Upload logs for support
lowr-upload-log

# Reset specific config to defaults
lowr-refresh-<app>

# Refresh specific config file
# config-file path is relative to ~/.config/
# eg. lowr-refresh-config hypr/hyprlock.conf will refresh ~/.config/hypr/hyprlock.conf
lowr-refresh-config <config-file>

# Full reinstall of configs (nuclear option)
lowr-reinstall
```

## Decision Framework

When user requests system changes:

1. **Is it a stock lowr command?** Use it directly
2. **Is it a config edit?** Edit in `~/.config/`, never `~/.local/share/lowr/`
3. **Is it a theme customization?** Create a NEW custom theme directory
4. **Is it automation?** Use hooks in `~/.config/lowr/hooks/`
5. **Is it a package install?** Use `lowr-pkg-add` (or `lowr-pkg-aur-add` for AUR-only packages)
6. **Unsure if command exists?** Search with `compgen -c | grep lowr`

## Out of Scope

This skill intentionally does not cover Lowr source development. Do not use this skill for:
- Editing files in `~/.local/share/lowr/` (`bin/`, `config/`, `default/`, `themes/`, `migrations/`, etc.)
- Creating or editing migrations
- Running `lowr-dev-*` commands

## Example Requests

- "Change my theme to catppuccin" -> `lowr-theme-set catppuccin`
- "Add a keybinding for Super+E to open file manager" -> Check existing bindings first, add `unbind` if needed, then add `bind` in `~/.config/hypr/bindings.conf`
- "Configure my external monitor" -> Edit `~/.config/hypr/monitors.conf`
- "Make the window gaps smaller" -> Edit `~/.config/hypr/looknfeel.conf`
- "Set up night light to turn on at sunset" -> `lowr-toggle-nightlight` or edit `~/.config/hypr/hyprsunset.conf`
- "Customize the catppuccin theme colors" -> Create `~/.config/lowr/themes/catppuccin-custom/` by copying from stock, then edit
- "Run a script every time I change themes" -> Create `~/.config/lowr/hooks/theme-set`
- "Reset waybar to defaults" -> `lowr-refresh-waybar`
