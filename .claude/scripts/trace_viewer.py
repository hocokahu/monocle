#!/usr/bin/env python3
"""
Interactive terminal trace viewer for .monocle/ local trace files.

Reads monocle trace JSON, builds a span tree, and renders an interactive
curses-based waterfall with arrow-key navigation and detail panels.

Usage:
    python trace_viewer.py                        # Pick from latest traces
    python trace_viewer.py --last 5m              # Traces from last 5 minutes
    python trace_viewer.py --trace-id abc123      # Specific trace
    python trace_viewer.py --dir .monocle         # Custom directory
    python trace_viewer.py --print                # Non-interactive (no TTY)

Keys:
    ↑/↓ or j/k    Navigate spans
    ←/→ or h/l    Collapse/expand children
    Enter          Toggle detail panel
    t              Cycle through traces (when multiple loaded)
    q / Esc        Quit
"""

import argparse
import curses
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ── Trace file loading ──────────────────────────────────────────────

def parse_ts(ts: str) -> datetime:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return datetime.min


def get_trace_files(
    monocle_dir: Path,
    last_minutes: Optional[int] = None,
    trace_id: Optional[str] = None,
    limit: int = 20,
) -> List[Path]:
    if not monocle_dir.exists():
        return []
    files = list(monocle_dir.glob("monocle_trace_*.json"))
    if trace_id:
        files = [f for f in files if trace_id in f.name]
    if last_minutes:
        cutoff = datetime.now() - timedelta(minutes=last_minutes)
        files = [f for f in files if datetime.fromtimestamp(f.stat().st_mtime) > cutoff]
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return files[:limit]


def load_trace(file_path: Path) -> List[Dict]:
    content = file_path.read_text().strip()
    if content.startswith("["):
        return json.loads(content)
    return [json.loads(content)]


# ── Span model ──────────────────────────────────────────────────────

class Span:
    def __init__(self, raw: Dict):
        ctx = raw.get("context", {})
        attrs = raw.get("attributes", {})
        self.name: str = raw.get("name", "unknown")
        self.span_id: str = ctx.get("span_id", "")
        self.trace_id: str = ctx.get("trace_id", "")
        self.parent_id: Optional[str] = raw.get("parent_id")
        self.span_type: str = attrs.get("span.type", "")
        self.status: str = raw.get("status", {}).get("status_code", "")

        start = parse_ts(raw.get("start_time", ""))
        end = parse_ts(raw.get("end_time", ""))
        if start != datetime.min and end != datetime.min:
            self.duration_ms = (end - start).total_seconds() * 1000
            self.start_time = start
        else:
            self.duration_ms = 0
            self.start_time = datetime.min

        self.attributes: Dict[str, Any] = {
            k: v for k, v in attrs.items() if not k.startswith("entity.")
        }
        # Entity info
        for k, v in attrs.items():
            if k.startswith("entity.") and ".name" in k:
                self.attributes["entity.name"] = v
            if k.startswith("entity.") and ".type" in k and "entity.type" not in self.attributes:
                self.attributes["entity.type"] = v

        self.events: List[Dict] = []
        self.tokens: Dict[str, int] = {}
        for ev in raw.get("events", []):
            ev_name = ev.get("name", "")
            ev_attrs = ev.get("attributes", {})
            if ev_name == "metadata":
                for k, v in ev_attrs.items():
                    if "token" in k:
                        self.tokens[k] = v
            else:
                val = ev_attrs.get("input") or ev_attrs.get("response") or ev_attrs.get("output") or ""
                if val:
                    self.events.append({"name": ev_name, "value": str(val)})

        self.children: List["Span"] = []
        self.depth: int = 0
        self.collapsed: bool = False

    def flat_visible(self) -> List["Span"]:
        result = [self]
        if not self.collapsed:
            for c in self.children:
                result.extend(c.flat_visible())
        return result


def build_tree(raw_spans: List[Dict]) -> Tuple[List[Span], float]:
    spans = [Span(s) for s in raw_spans]
    by_id = {s.span_id: s for s in spans}
    roots = []
    for s in spans:
        if s.parent_id and s.parent_id in by_id:
            by_id[s.parent_id].children.append(s)
        else:
            roots.append(s)

    total_ms = max((s.duration_ms for s in spans), default=1) or 1
    earliest = min((s.start_time for s in spans if s.start_time != datetime.min), default=datetime.min)

    def set_depth(span, d):
        span.depth = d
        for c in span.children:
            set_depth(c, d + 1)

    for r in roots:
        set_depth(r, 0)

    return roots, total_ms


# ── Color setup ─────────────────────────────────────────────────────

C_HEADER = 1
C_SELECTED = 2
C_WORKFLOW = 3
C_TURN = 4
C_INFERENCE = 5
C_TOOL = 6
C_DIM = 7
C_KEY = 8
C_VAL = 9
C_EVENT = 10
C_BORDER = 11
C_OK = 12
C_ERR = 13
C_AGENT = 14
C_MCP = 15


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(C_HEADER, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(C_SELECTED, curses.COLOR_BLACK, curses.COLOR_CYAN)
    curses.init_pair(C_WORKFLOW, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(C_TURN, curses.COLOR_BLACK, curses.COLOR_GREEN)
    curses.init_pair(C_INFERENCE, curses.COLOR_WHITE, curses.COLOR_MAGENTA)
    curses.init_pair(C_TOOL, curses.COLOR_BLACK, curses.COLOR_YELLOW)
    curses.init_pair(C_DIM, 8, -1)
    curses.init_pair(C_KEY, curses.COLOR_CYAN, -1)
    curses.init_pair(C_VAL, curses.COLOR_WHITE, -1)
    curses.init_pair(C_EVENT, curses.COLOR_YELLOW, -1)
    curses.init_pair(C_BORDER, 8, -1)
    curses.init_pair(C_OK, curses.COLOR_GREEN, -1)
    curses.init_pair(C_ERR, curses.COLOR_RED, -1)
    curses.init_pair(C_AGENT, curses.COLOR_WHITE, curses.COLOR_RED)
    curses.init_pair(C_MCP, curses.COLOR_BLACK, curses.COLOR_WHITE)


def bar_color(span_type: str) -> int:
    if "workflow" in span_type:
        return C_WORKFLOW
    if "turn" in span_type or "agentic.turn" in span_type:
        return C_TURN
    if "inference" in span_type:
        return C_INFERENCE
    if "mcp" in span_type:
        return C_MCP
    if "invocation" in span_type and "tool" not in span_type:
        return C_AGENT
    if "tool" in span_type:
        return C_TOOL
    return C_DIM


def type_badge(span_type: str) -> str:
    if "workflow" in span_type:
        return "WF"
    if "agentic.turn" in span_type:
        return "TN"
    if "inference" in span_type:
        return "LM"
    if "mcp" in span_type:
        return "MC"
    if "skill" in span_type:
        return "SK"
    if "invocation" in span_type and "tool" not in span_type:
        return "AG"
    if "tool" in span_type:
        return "TL"
    return "??"


# ── Drawing helpers ─────────────────────────────────────────────────

def safe(win, y, x, text, attr=0):
    h, w = win.getmaxyx()
    if y < 0 or y >= h or x >= w:
        return
    try:
        win.addstr(y, x, text[: w - x - 1], attr)
    except curses.error:
        pass


def draw_bar(win, y, x, length, color):
    try:
        win.addstr(y, x, "█" * max(1, length), curses.color_pair(color))
    except curses.error:
        pass


# ── Main UI ─────────────────────────────────────────────────────────

class TraceViewer:
    def __init__(self, traces: List[Tuple[str, List[Span], float]]):
        self.traces = traces  # [(filename, roots, total_ms), ...]
        self.trace_idx = 0
        self.selected = 0
        self.detail_open = True
        self.scroll_offset = 0

    @property
    def current(self):
        return self.traces[self.trace_idx]

    @property
    def visible_spans(self) -> List[Span]:
        _, roots, _ = self.current
        result = []
        for r in roots:
            result.extend(r.flat_visible())
        return result

    def run(self, stdscr):
        curses.curs_set(0)
        init_colors()

        while True:
            stdscr.clear()
            h, w = stdscr.getmaxyx()
            fname, roots, total_ms = self.current
            visible = self.visible_spans

            # Clamp selection
            if self.selected >= len(visible):
                self.selected = max(0, len(visible) - 1)

            # ── Header ──
            safe(stdscr, 0, 0, " " * w, curses.color_pair(C_HEADER))
            safe(stdscr, 0, 1, "TRACE VIEWER", curses.color_pair(C_HEADER) | curses.A_BOLD)
            if visible:
                tid = visible[0].trace_id[:20] + "..."
                safe(stdscr, 0, 15, tid, curses.color_pair(C_HEADER))
            trace_nav = f" [{self.trace_idx+1}/{len(self.traces)}] "
            status_str = f"OK" if all(s.status != "ERROR" for s in visible) else "ERR"
            sc = C_OK if status_str == "OK" else C_ERR
            right = f"{status_str} | {total_ms:.0f}ms | {len(visible)} spans{trace_nav}"
            safe(stdscr, 0, max(0, w - len(right) - 1), right, curses.color_pair(C_HEADER))

            # ── Span list (waterfall) ──
            name_col = min(32, w // 3)
            bar_area = max(15, w - name_col - 15)
            y = 2

            # Column headers
            safe(stdscr, y, 1, "SPAN", curses.color_pair(C_DIM) | curses.A_BOLD)
            safe(stdscr, y, name_col, "TIMELINE", curses.color_pair(C_DIM) | curses.A_BOLD)
            safe(stdscr, y, name_col + bar_area + 1, "DURATION", curses.color_pair(C_DIM) | curses.A_BOLD)
            y += 1
            safe(stdscr, y, 0, "─" * w, curses.color_pair(C_BORDER))
            y += 1

            # Calculate how many span rows fit
            detail_height = 15 if self.detail_open else 0
            max_span_rows = h - y - detail_height - 2  # 2 for footer

            # Scroll if needed
            if self.selected < self.scroll_offset:
                self.scroll_offset = self.selected
            if self.selected >= self.scroll_offset + max_span_rows:
                self.scroll_offset = self.selected - max_span_rows + 1

            for idx in range(self.scroll_offset, min(len(visible), self.scroll_offset + max_span_rows)):
                span = visible[idx]
                indent = "  " * span.depth
                collapse_marker = ""
                if span.children:
                    collapse_marker = "▸ " if span.collapsed else "▾ "
                else:
                    collapse_marker = "  "
                badge = type_badge(span.span_type)
                label = f"{indent}{collapse_marker}[{badge}] {span.name}"
                label = label[:name_col - 1]

                is_sel = idx == self.selected
                if is_sel:
                    safe(stdscr, y, 0, " " * w, curses.color_pair(C_SELECTED))
                    attr = curses.color_pair(C_SELECTED) | curses.A_BOLD
                else:
                    attr = curses.A_NORMAL

                safe(stdscr, y, 1, label, attr)

                # Bar
                frac = span.duration_ms / total_ms if total_ms > 0 else 0
                bar_len = max(1, int(bar_area * frac))
                bc = bar_color(span.span_type)
                draw_bar(stdscr, y, name_col, bar_len, bc)

                # Duration
                dur = f"{span.duration_ms:.0f}ms" if span.duration_ms >= 1 else "<1ms"
                dur_attr = attr if is_sel else curses.A_NORMAL
                safe(stdscr, y, name_col + bar_area + 1, dur, dur_attr)

                y += 1

            # ── Detail panel ──
            if self.detail_open and visible:
                span = visible[self.selected]
                dy = h - detail_height - 1
                safe(stdscr, dy, 0, "─" * w, curses.color_pair(C_BORDER))
                dy += 1

                # Title row
                safe(stdscr, dy, 1, f"● {span.name}", curses.A_BOLD)
                safe(stdscr, dy, 3 + len(span.name), f"  {span.span_type}", curses.color_pair(C_DIM))
                dy += 1
                safe(stdscr, dy, 1, f"span_id: {span.span_id}", curses.color_pair(C_DIM))
                dy += 1
                if span.parent_id:
                    safe(stdscr, dy, 1, f"parent:  {span.parent_id}", curses.color_pair(C_DIM))
                    dy += 1
                dy += 1

                # Attributes (compact, 2 columns)
                attr_items = [(k, str(v)) for k, v in span.attributes.items()
                              if k not in ("span.type", "span.subtype")]
                col_w = w // 2 - 2
                for i in range(0, min(len(attr_items), 8), 2):
                    k1, v1 = attr_items[i]
                    safe(stdscr, dy, 2, f"{k1}:", curses.color_pair(C_KEY))
                    safe(stdscr, dy, 4 + len(k1), v1[:col_w - len(k1) - 5], curses.color_pair(C_VAL))
                    if i + 1 < len(attr_items):
                        k2, v2 = attr_items[i + 1]
                        safe(stdscr, dy, col_w + 2, f"{k2}:", curses.color_pair(C_KEY))
                        safe(stdscr, dy, col_w + 4 + len(k2), v2[:col_w - len(k2) - 5], curses.color_pair(C_VAL))
                    dy += 1

                # Events
                if span.events and dy < h - 2:
                    dy += 1
                    for ev in span.events[:3]:
                        val = ev["value"]
                        if len(val) > w - 8 - len(ev["name"]):
                            val = val[:w - 12 - len(ev["name"])] + "..."
                        safe(stdscr, dy, 2, ev["name"], curses.color_pair(C_EVENT))
                        safe(stdscr, dy, 4 + len(ev["name"]), val, curses.color_pair(C_VAL))
                        dy += 1

                # Tokens
                if span.tokens and dy < h - 1:
                    tok_str = "  ".join(f"{k}={v:,}" for k, v in span.tokens.items())
                    safe(stdscr, dy, 2, "tokens:", curses.color_pair(C_KEY))
                    safe(stdscr, dy, 10, tok_str, curses.color_pair(C_VAL))

            # ── Footer ──
            fy = h - 1
            safe(stdscr, fy, 0, " " * w, curses.color_pair(C_HEADER))
            keys = "↑↓ Navigate  ←→ Collapse  Enter Detail  t Trace  q Quit"
            safe(stdscr, fy, 1, keys, curses.color_pair(C_HEADER))
            safe(stdscr, fy, max(0, w - len(fname) - 2), fname[:w - 2], curses.color_pair(C_HEADER))

            stdscr.refresh()

            # ── Input ──
            key = stdscr.getch()
            if key == ord("q") or key == ord("Q") or key == 27:
                break
            elif key == curses.KEY_UP or key == ord("k"):
                self.selected = max(0, self.selected - 1)
            elif key == curses.KEY_DOWN or key == ord("j"):
                self.selected = min(len(visible) - 1, self.selected + 1)
            elif key == curses.KEY_LEFT or key == ord("h"):
                s = visible[self.selected]
                if s.children:
                    s.collapsed = True
            elif key == curses.KEY_RIGHT or key == ord("l"):
                s = visible[self.selected]
                if s.children:
                    s.collapsed = False
            elif key == ord("\n") or key == ord(" "):
                self.detail_open = not self.detail_open
            elif key == ord("t") or key == ord("T"):
                self.trace_idx = (self.trace_idx + 1) % len(self.traces)
                self.selected = 0
                self.scroll_offset = 0


# ── Non-interactive (print) mode ────────────────────────────────────

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
RED = "\033[31m"
GRAY = "\033[90m"
WHITE = "\033[97m"
ULINE = "\033[4m"

BAR_COLORS = {
    "workflow": "\033[44;97m",
    "turn": "\033[42;30m",
    "inference": "\033[45;97m",
    "tool": "\033[43;30m",
    "agent": "\033[41;97m",
    "mcp": "\033[47;30m",
}


def get_bar_color(span_type: str) -> str:
    for k, v in BAR_COLORS.items():
        if k in span_type:
            return v
    return GRAY


def print_trace(fname: str, roots: List[Span], total_ms: float):
    tid = roots[0].trace_id if roots else "unknown"

    # Collect all visible spans
    all_spans = []
    for r in roots:
        all_spans.extend(r.flat_visible())

    print()
    print(f"{BOLD}{CYAN}{'━' * 72}{RESET}")
    print(f"  {BOLD}Trace{RESET}     {GRAY}{tid}{RESET}")
    print(f"  {BOLD}Duration{RESET}  {total_ms:.0f}ms")
    print(f"  {BOLD}Spans{RESET}     {len(all_spans)}")
    print(f"  {BOLD}File{RESET}      {GRAY}{fname}{RESET}")
    print()

    # Waterfall
    bar_w = 30
    print(f"  {GRAY}{'SPAN':<30}{'TIMELINE':<{bar_w+2}} DURATION{RESET}")
    print(f"  {GRAY}{'─' * 68}{RESET}")

    for span in all_spans:
        indent = "  " * span.depth
        badge = type_badge(span.span_type)
        label = f"{indent}[{badge}] {span.name}"[:30]
        frac = span.duration_ms / total_ms if total_ms > 0 else 0
        filled = max(1, int(bar_w * frac))
        empty = bar_w - filled
        bc = get_bar_color(span.span_type)
        bar = f"{bc}{' ' * filled}{RESET}{GRAY}{'░' * empty}{RESET}"
        dur = f"{span.duration_ms:.0f}ms" if span.duration_ms >= 1 else "<1ms"
        print(f"  {WHITE}{label:<30}{RESET} {bar} {BOLD}{dur}{RESET}")

    print()

    # Span details
    for i, span in enumerate(all_spans):
        print(f"  {BOLD}{CYAN}── Span {i+1}/{len(all_spans)}: {span.name}{RESET} {GRAY}{span.span_type}{RESET}")
        print(f"    {GRAY}id: {span.span_id}{RESET}")
        dur = f"{span.duration_ms:.0f}ms" if span.duration_ms >= 1 else "<1ms"
        print(f"    {GRAY}duration: {dur}{RESET}")

        for k, v in span.attributes.items():
            if k in ("span.type", "span.subtype"):
                continue
            print(f"    {CYAN}{k}{RESET}: {v}")

        for ev in span.events:
            val = ev["value"][:80] + "..." if len(ev["value"]) > 80 else ev["value"]
            print(f"    {YELLOW}{ev['name']}{RESET}  {val}")

        if span.tokens:
            tok_str = "  ".join(f"{k}={v:,}" for k, v in span.tokens.items())
            print(f"    {CYAN}tokens{RESET}: {tok_str}")
        print()

    print(f"{BOLD}{CYAN}{'━' * 72}{RESET}")


# ── CLI ─────────────────────────────────────────────────────────────

def parse_time(s: str) -> Optional[int]:
    if not s:
        return None
    try:
        if s.endswith("m"):
            return int(s[:-1])
        if s.endswith("h"):
            return int(s[:-1]) * 60
        return int(s)
    except ValueError:
        return None


def main():
    parser = argparse.ArgumentParser(description="Interactive monocle trace viewer")
    parser.add_argument("--dir", "-d", default=".monocle", help="Monocle trace directory")
    parser.add_argument("--last", "-l", help="Traces from last N minutes (e.g. 5m, 1h)")
    parser.add_argument("--trace-id", "-t", help="Filter by trace ID (partial match)")
    parser.add_argument("--limit", "-n", type=int, default=20, help="Max trace files")
    parser.add_argument("--print", "-p", action="store_true", help="Non-interactive print mode")
    args = parser.parse_args()

    monocle_dir = Path(args.dir)
    last_min = parse_time(args.last)
    files = get_trace_files(monocle_dir, last_min, args.trace_id, args.limit)

    if not files:
        print(f"No trace files found in {monocle_dir}/", file=sys.stderr)
        sys.exit(1)

    # Load and deduplicate by trace_id
    traces = []
    seen = set()
    for f in files:
        try:
            raw = load_trace(f)
        except Exception as e:
            print(f"Error loading {f}: {e}", file=sys.stderr)
            continue
        roots, total_ms = build_tree(raw)
        if not roots:
            continue
        tid = roots[0].trace_id
        if tid in seen:
            continue
        seen.add(tid)
        traces.append((f.name, roots, total_ms))

    if not traces:
        print("No valid traces found.", file=sys.stderr)
        sys.exit(1)

    if args.print or not sys.stdout.isatty():
        for fname, roots, total_ms in traces:
            print_trace(fname, roots, total_ms)
    else:
        viewer = TraceViewer(traces)
        curses.wrapper(viewer.run)


if __name__ == "__main__":
    main()
