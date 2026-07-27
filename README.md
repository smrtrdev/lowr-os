# Lowr

Lowr is a very opinionated Linux distribution, specifically adjusted for me. It uses [Niri](https://github.com/YaLTeR/niri) as its Wayland compositor.

## Main components

Lowr is built around a small set of opinionated desktop components:

- [Niri](https://github.com/YaLTeR/niri) is the Wayland compositor and the center of the desktop experience. Lowr uses it for window management, workspace layout, startup applications, input settings, and window rules.
- [Waybar](https://github.com/Alexays/Waybar) is the top bar. In this repo it integrates Niri workspaces, clock, updates, tray, Bluetooth, network, audio, CPU, and battery, plus custom indicators for screen recording, idle locking, notification silencing, and dictation.
- [Mako](https://github.com/emersion/mako) handles notifications. Lowr configures it with a clean top-right layout, do-not-disturb mode, critical notification handling, and clickable actions for common tasks such as Wi-Fi setup, updates, and keybinding help.
- [Walker](https://github.com/abenz1267/walker) is the application launcher. It is configured for launching apps, files, symbol search, calculator input, web search, and clipboard access.
- `hypridle` and `hyprlock` handle idle behavior, screensaver flow, and screen locking.
- `hyprsunset` provides night light behavior, and `swayosd` provides on-screen feedback for things like volume and brightness changes.
- [Limine](https://limine-bootloader.org/) is the boot manager. In this repo it is themed and configured around UKIs, fallback boot entries, and Snapper snapshot integration.
- `LUKS` full-disk encryption is part of the system setup. The installer enables the `encrypt` initramfs hook, and Lowr includes tooling to manage the drive encryption password.

## Credits

Lowr is forked from [Omarchy](https://omarchy.org), a beautiful, modern & opinionated Linux distribution by DHH.

## License

Lowr is released under the [MIT License](https://opensource.org/licenses/MIT).
