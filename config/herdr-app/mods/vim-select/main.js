// Vim-like keyboard selection for the focused terminal (a copy mode).
// Opened with `mod.open:vim-select` (lowr binds alt-space and ctrl-space; again: leave).
// The selection is the cursor: in normal mode it is one cell that moves, in visual
// mode its moving end follows the motions, in visual line mode whole rows are selected.
//
//   h j k l / arrows   move            0 ^ $ / home end   line start / end
//   w / b / e          next word / word start / word end  (W B E: blank-separated WORDs)
//   gg / G             top / bottom    ctrl-u ctrl-d ctrl-b ctrl-f / pgup pgdn   page
//   v / V              visual / visual line (again: back to normal)
//   y / enter          copy the selection and leave       yy / Y   copy the line
//   esc                visual: back to normal, normal: leave        q   leave
//   1-9                count prefix (5j)

import { View, div } from "gpui-kit";
import { h_flex } from "gpui-base";
import { run, hc, props, closeOverlay, theme, focused, terminals, panes, checking } from "herdr";

const MOTIONS = {
  h: "left", left: "left",
  l: "right", right: "right",
  j: "down", down: "down",
  k: "up", up: "up",
  "0": "line_start", "^": "line_start", home: "line_start",
  $: "line_end", end: "line_end",
  G: "end",
  "ctrl-u": "page_up", "ctrl-b": "page_up", pageup: "page_up",
  "ctrl-d": "page_down", "ctrl-f": "page_down", pagedown: "page_down",
};

// Motions a count doesn't repeat.
const ONCE = new Set(["line_start", "line_end", "home", "end"]);

const LABELS = { normal: "NORMAL", visual: "VISUAL", line: "VISUAL LINE" };

const WORDS = { w: "w", b: "b", e: "e", W: "w", B: "b", E: "e" };

// History rows read above the cursor, so `b` can cross into earlier lines.
const CONTEXT = 50;

const same = (a, b) => a.row === b.row && a.col === b.col;

const sleep = (cx, ms) => new Promise((done) => cx.timer.after(ms, done));

// Vim's character classes: 0 blank, 1 word characters, 2 other non-blanks (WORD: 1 for all).
const kind = (ch, big) => (!ch || /\s/.test(ch) ? 0 : big || /[\p{L}\p{N}_]/u.test(ch) ? 1 : 2);

// Cells in reading order; each row ends in a blank so words never run across lines.
function cellsOf(lines, firstRow) {
  const cells = [];
  lines.forEach((line, i) => {
    const chars = Array.from(line);
    chars.forEach((ch, col) => cells.push({ row: firstRow + i, col, ch }));
    cells.push({ row: firstRow + i, col: chars.length, ch: "" });
  });
  return cells;
}

// Where w, b or e lands from cell i (i itself when there is nowhere to go).
function wordTarget(cells, i, motion, big) {
  const k = (j) => kind(cells[j]?.ch, big);
  const n = cells.length;
  let j = i;
  if (motion === "w") {
    const start = k(j);
    if (start) while (j < n && k(j) === start) j++;
    while (j < n && !k(j)) j++;
    return j < n ? j : i;
  }
  const step = motion === "e" ? 1 : -1;
  j += step;
  while (j >= 0 && j < n && !k(j)) j += step;
  if (j < 0 || j >= n) return i;
  const word = k(j);
  while (k(j + step) === word) j += step;
  return j;
}

export default class VimSelect extends View {
  init(_props, cx) {
    this.mode = "normal";
    this.count = "";
    this.pending = "";
    this.term = focused()?.terminal ?? null;
    this.handle = cx.focus_handle();
    this.handle.focus();
    cx.timer.after(100, () => this.handle.focus());
    if (checking()) return;
    if (!this.term) return this.quit();
    run("terminal.select", { terminal: this.term });
  }

  async close(_cx) {
    if (this.term) run("terminal.clear_selection", { terminal: this.term });
  }

  selection() {
    const t = terminals().find((t) => t.address === this.term);
    return (t ?? focused())?.selection ?? null;
  }

  pageRows() {
    return panes().find((p) => p.terminal === this.term)?.scroll?.len || 20;
  }

  quit() {
    const id = props()?.overlay;
    if (id) closeOverlay(id);
  }

  select(at) {
    run("terminal.select", { terminal: this.term, at });
  }

  adjust(direction, times = 1) {
    for (let i = 0; i < times; i++) run("terminal.adjust_selection", { terminal: this.term, direction });
  }

  // Normal mode keeps a one-cell cursor: after a motion, collapse onto the moving end.
  collapse() {
    if (this.mode !== "normal") return;
    const sel = this.selection();
    if (sel && !same(sel.start, sel.end)) this.select(sel.end);
  }

  // Visual line: select whole rows from the upper to the lower of anchor and cursor row.
  drawLines() {
    this.select({ row: Math.min(this.anchor, this.row), col: 0 });
    this.adjust("down", Math.abs(this.row - this.anchor));
    this.adjust("line_end");
  }

  // Past the last row, `down` stops at the bottom: follow where the selection really ends.
  syncLines() {
    if (this.mode !== "line" || this.row <= this.anchor) return;
    const sel = this.selection();
    if (sel && sel.end.row < this.row) this.row = sel.end.row;
  }

  move(motion, times) {
    if (this.mode !== "line") {
      this.adjust(motion, times);
      return this.collapse();
    }
    if (motion === "end") {
      // The bottom row isn't known up front: extend from the anchor until the terminal stops.
      this.row = Number.MAX_SAFE_INTEGER;
      this.select({ row: this.anchor, col: 0 });
      this.adjust("end");
      this.adjust("line_end");
      return;
    }
    const page = this.pageRows();
    const by = { up: -1, down: 1, page_up: -page, page_down: page }[motion];
    if (motion === "home") this.row = 0;
    else if (by) this.row = Math.max(0, this.row + by * times);
    else return; // horizontal motions don't change a line selection
    this.drawLines();
  }

  // The text from `fromRow` to the bottom, as cells in selection coordinates.
  async readCells(fromRow) {
    const rows = terminals().find((t) => t.address === this.term)?.rows ?? 0;
    const scroll = panes().find((p) => p.terminal === this.term)?.scroll;
    const top = scroll ? scroll.total - rows : 0; // the screen's first row
    const want = Math.max(0, top - fromRow + CONTEXT);
    const read = async (lines) => {
      const r = await hc(["read", this.term, "--json", "--lines", String(lines)]);
      return JSON.parse(r.stdout).text.split("\n");
    };
    // Trailing blank rows are left out, so count history lines against the screen alone.
    const [screen, all] = await Promise.all([read(0), want ? read(want) : null]);
    const lines = all ?? screen;
    return cellsOf(lines, top - (lines.length - screen.length));
  }

  async wordMove(motion, times, big, cx) {
    const sel = this.selection();
    if (!sel) return;
    const from = sel.end;
    const cells = await this.readCells(from.row);
    let i = cells.findIndex((c) => same(c, from));
    if (i < 0) {
      // Past a row's text: its closing blank; below the text: after everything.
      const row = cells.filter((c) => c.row === from.row);
      i = row.length ? cells.indexOf(row[row.length - 1]) : cells.length;
    }
    let j = i;
    for (let n = 0; n < times; n++) j = wordTarget(cells, j, motion, big);
    const to = cells[j];
    if (!to || j === i) return;
    if (this.mode === "normal") this.select(to);
    else if (from.row === to.row) this.adjust(to.col > from.col ? "right" : "left", Math.abs(to.col - from.col));
    else {
      this.adjust(to.row > from.row ? "down" : "up", Math.abs(to.row - from.row));
      this.adjust("line_start");
      this.adjust("right", to.col);
    }
    // Let the selection catch up before the next motion reads it.
    for (let n = 0; n < 20; n++) {
      if (same(this.selection()?.end ?? from, to)) return;
      await sleep(cx, 15);
    }
  }

  // Word motions read the terminal's text, so they run in order, one at a time.
  queueWord(name, times, cx) {
    if (this.mode === "line") return; // a line selection keeps whole rows
    const before = this.chain;
    this.chain = new Promise((done) => cx.spawn(async (cx) => {
      try {
        await before;
        await this.wordMove(WORDS[name], times, name !== name.toLowerCase(), cx);
      } catch (e) {
        console.log("vim-select:", e);
      } finally {
        done();
        cx.notify();
      }
    }));
  }

  yank() {
    run("terminal.copy");
    this.quit();
  }

  yankLine() {
    const sel = this.selection();
    if (!sel) return;
    this.select({ row: this.mode === "line" ? this.row : sel.end.row, col: 0 });
    this.adjust("line_end");
    this.yank();
  }

  setMode(mode) {
    const sel = this.selection();
    if (!sel) return;
    const cursor = this.mode === "line" ? { row: this.row, col: 0 } : sel.end;
    if (mode === this.mode || mode === "normal") {
      this.mode = "normal";
      return this.select(cursor);
    }
    this.mode = mode;
    if (mode === "line") {
      this.anchor = this.row = cursor.row;
      return this.drawLines();
    }
    this.select(cursor);
  }

  key(e, cx) {
    const mods = e.modifiers ?? {};
    const name = mods.control || mods.alt || mods.platform ? e.keystroke : (e.key_char ?? e.key);
    const pending = this.pending;
    this.pending = "";

    if (/^[1-9]$/.test(name) || (name === "0" && this.count)) {
      this.count = (this.count + name).slice(-3);
      return;
    }
    const times = Math.max(1, parseInt(this.count || "1", 10));
    this.count = "";

    if (pending === "g" && name === "g") return this.move("home", 1);
    if (pending === "y" && name === "y") return this.yankLine();
    if (MOTIONS[name]) return this.move(MOTIONS[name], ONCE.has(MOTIONS[name]) ? 1 : times);
    if (WORDS[name]) return this.queueWord(name, times, cx);

    switch (name) {
      case "g": this.pending = "g"; return;
      case "v": return this.setMode("visual");
      case "V": return this.setMode("line");
      case "Y": return this.yankLine();
      case "y":
      case "enter":
        if (this.mode !== "normal") return this.yank();
        if (name === "y") this.pending = "y";
        return;
      case "escape":
        if (this.mode !== "normal") return this.setMode("normal");
        return this.quit();
      case "q":
      case "ctrl-c":
        return this.quit();
    }
  }

  render(cx) {
    this.collapse();
    this.syncLines();
    const t = theme();
    const hint = this.mode === "normal"
      ? "hjkl wbe move · v/V select · yy line · q quit"
      : "hjkl wbe move · y copy · esc back";
    return h_flex()
      .id("vim-select")
      .track_focus(this.handle)
      .on_key_down((e, cx) => {
        this.key(e, cx);
        cx.stop_propagation();
        cx.notify();
      })
      .size_full()
      .px(12)
      .gap(12)
      .items_center()
      .bg(t.popover)
      .text_size(12)
      .child(
        div().px(8).py(2).rounded(4).font_semibold()
          .bg(this.mode === "normal" ? t.raised : t.accent)
          .text_color(this.mode === "normal" ? t.foreground : t.accent_foreground)
          .child(`-- ${LABELS[this.mode]} --`))
      .child(div().text_color(t.muted).child(this.count + this.pending))
      .child(div().flex_1())
      .child(div().text_color(t.dim).truncate().child(hint));
  }
}
