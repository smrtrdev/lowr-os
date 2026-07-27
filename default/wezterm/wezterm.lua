-- Pull in the wezterm API
local wezterm = require 'wezterm'

local act = wezterm.action
-- This will hold the configuration.
local config = wezterm.config_builder()

-- This is where you actually apply your config choices

config.initial_cols = 120
config.initial_rows = 28

config.default_prog = { 'nu' }
config.color_scheme = 'Tokyo Night'

config.font = wezterm.font 'JetBrains Mono'
config.font_size = 10.0

config.use_fancy_tab_bar = false
config.window_close_confirmation = "NeverPrompt"

config.mouse_bindings = {
  {
    event = { Up = { streak = 1, button = 'Left' } },
    mods = 'NONE',
    action = act.CompleteSelection 'Clipboard',
  },
}

-- get default key tables
local key_tables = wezterm.gui.default_key_tables()

-- override only "y" in copy_mode
table.insert(key_tables.copy_mode, {
  key = "y",
  mods = "NONE",
  action = act.Multiple { act.CopyTo 'Clipboard', act.CopyMode 'Close' },
})
table.insert(key_tables.copy_mode, {
  key = "Enter",
  mods = "NONE",
  action = act.Multiple { act.CopyTo 'Clipboard', act.CopyMode 'Close' },
})

config.key_tables = key_tables

config.key_tables.alt_p_prefix = {
  { key = 'e',          action = act.SplitHorizontal {} },
  { key = 'i',          action = act.SplitVertical {} },
  { key = 'x',          action = act.CloseCurrentPane { confirm = false } },
  { key = 'LeftArrow',  action = act.ActivatePaneDirection 'Left' },
  { key = 'RightArrow', action = act.ActivatePaneDirection 'Right' },
  { key = 'UpArrow',    action = act.ActivatePaneDirection 'Up' },
  { key = 'DownArrow',  action = act.ActivatePaneDirection 'Down' },
  { key = 't',          action = act.ActivatePaneDirection 'Left' },
  { key = 'r',          action = act.ActivatePaneDirection 'Right' },
  { key = 'm',          action = act.ActivatePaneDirection 'Up' },
  { key = 'n',          action = act.ActivatePaneDirection 'Down' },
  {
    key = 'p',
    mods = 'ALT',
    action = act.PopKeyTable,
  },
  { key = 'Escape', action = act.PopKeyTable },
  { key = 'Enter',  action = act.PopKeyTable },
}

config.keys = {
  { key = 'Space', mods = 'CTRL', action = act.ActivateCopyMode },
  { key = ',',     mods = 'ALT',  action = act.SplitVertical { domain = "CurrentPaneDomain" } },
  { key = '.',     mods = 'ALT',  action = act.SplitHorizontal { domain = "CurrentPaneDomain" } },
  { key = 'j',     mods = 'ALT',  action = act.CloseCurrentPane { confirm = false } },
  { key = 't',     mods = 'ALT',  action = act.ActivatePaneDirection 'Left' },
  { key = 'r',     mods = 'ALT',  action = act.ActivatePaneDirection 'Right' },
  { key = 'm',     mods = 'ALT',  action = act.ActivatePaneDirection 'Up' },
  { key = 'n',     mods = 'ALT',  action = act.ActivatePaneDirection 'Down' },
  { key = 'p',     mods = 'ALT',  action = act.ActivateKeyTable { name = 'alt_p_prefix', one_shot = false } },
}



local tabline = wezterm.plugin.require("https://github.com/michaelbrusegard/tabline.wez")
local tabline_opts = {
  options = {
    icons_enabled = true,
    theme = config.colors,
    tabs_enabled = true,
    theme_overrides = {},
    section_separators = {
      left = wezterm.nerdfonts.pl_left_hard_divider,
      right = wezterm.nerdfonts.pl_right_hard_divider,
    },
    component_separators = {
      left = wezterm.nerdfonts.pl_left_soft_divider,
      right = wezterm.nerdfonts.pl_right_soft_divider,
    },
    tab_separators = {
      left = wezterm.nerdfonts.pl_left_hard_divider,
      right = wezterm.nerdfonts.pl_right_hard_divider,
    },
  },
  sections = {
    tabline_a = { 'mode' },
    tabline_b = { 'workspace' },
    tabline_c = { ' ' },
    tab_active = {
      'index',
      { 'parent', padding = 0 },
      '/',
      { 'cwd',    padding = { left = 0, right = 1 } },
      { 'zoomed', padding = 0 },
    },
    tab_inactive = { 'index', { 'process', padding = { left = 0, right = 1 } } },
    tabline_x = { 'ram', 'cpu' },
    tabline_y = {},
    tabline_z = { 'domain' },
  },
  extensions = {},
}

local theme_file = wezterm.home_dir .. '/.config/lowr/current/theme/wezterm.theme.lua'
local ok, apply_theme = pcall(dofile, theme_file)
if ok and type(apply_theme) == 'function' then
  config = apply_theme(config, tabline_opts)
end

tabline.setup(tabline_opts)

-- and finally, return the configuration to wezterm
return config
