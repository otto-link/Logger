#!/usr/bin/env python3
"""Portable live log viewer for the Logger C++ library.

Usage:
    python3 tools/log_viewer.py [path/to/app.log]
"""

from __future__ import annotations

import os
import re
import sys
import textwrap
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass, field
from tkinter import filedialog, ttk
from typing import Dict, List, Optional, Tuple

LEVEL_ORDER = {
    "trace": 0,
    "debug": 1,
    "info": 2,
    "warning": 3,
    "warn": 3,
    "error": 4,
    "err": 4,
    "critical": 5,
}

LEVEL_COLORS = {
    "trace": "#6c757d",
    "debug": "#0d6efd",
    "info": "#198754",
    "warning": "#b45309",
    "warn": "#b45309",
    "error": "#dc3545",
    "err": "#dc3545",
    "critical": "#7f1d1d",
}

# Matches:
#   [2026-11-15 00:10:00.123] [12345] [info    ] [Module]   message
#   [2026-11-15 00:10:00.123] [info    ] [Module]   message
LOG_LINE_RE = re.compile(
    r"^\[(?P<ts>[^\]]+)\]\s+"
    r"(?:\[(?P<tid>\d+)\]\s+)?"
    r"\[(?P<level>[a-zA-Z]+)\s*\]\s+"
    r"\[(?P<module>[^\]]+)\]\s"
    r"(?:\[ctx:(?P<ctx>[0-9/]+)\]\s)?"
    r"(?P<body>.*)$"
)

SCOPE_OPEN_RE = re.compile(r"^<(?P<name>[^/>][^>]*)>$")
SCOPE_CLOSE_RE = re.compile(
    r"^</(?P<name>[^>]+)>\s*(?:\((?P<duration>[^)]+)\))?$"
)


@dataclass
class LogEntry:
    timestamp: str
    thread_id: str
    level: str
    module: str
    indent: int
    message: str
    scope_open: Optional[str] = None
    scope_close: Optional[str] = None
    duration: str = ""
    ctx_path: Tuple[str, ...] = ()
    raw: str = ""


def parse_log_line(line: str) -> LogEntry:
    stripped = line.rstrip("\r\n")
    match = LOG_LINE_RE.match(stripped)
    if not match:
        return LogEntry(
            timestamp="",
            thread_id="main",
            level="info",
            module="raw",
            indent=0,
            message=stripped,
            raw=stripped,
        )

    body = match.group("body")
    leading_spaces = len(body) - len(body.lstrip(" "))
    indent = leading_spaces // 2
    message = body.lstrip(" ")

    scope_open = None
    scope_close = None
    duration = ""

    open_m = SCOPE_OPEN_RE.match(message)
    if open_m:
        scope_open = open_m.group("name")
    else:
        close_m = SCOPE_CLOSE_RE.match(message)
        if close_m:
            scope_close = close_m.group("name")
            duration = close_m.group("duration") or ""

    ctx_raw = match.group("ctx")
    ctx_path = tuple(ctx_raw.split("/")) if ctx_raw else ()

    return LogEntry(
        timestamp=match.group("ts"),
        thread_id=match.group("tid") or "main",
        level=match.group("level").lower(),
        module=match.group("module"),
        indent=indent,
        message=message,
        scope_open=scope_open,
        scope_close=scope_close,
        duration=duration,
        ctx_path=ctx_path,
        raw=stripped,
    )


class LogViewerApp:
    POLL_INTERVAL_MS = 150

    def __init__(self, root: tk.Tk, initial_file: Optional[str] = None) -> None:
        self.root = root
        self.root.title("Logger Viewer")
        self.root.geometry("1150x700")

        self.file_path: Optional[str] = initial_file
        self.file_offset: int = 0
        self.file_inode: Optional[int] = None
        self.paused: bool = False
        self.all_expanded: bool = True

        self.entries: List[LogEntry] = []
        self.threads: List[str] = []
        self.modules: List[str] = []

        # Per-thread stack of open tree item IDs: {thread_id: [(scope_name, item_id), ...]}
        self.scope_stacks: Dict[str, List[Tuple[str, str]]] = {}
        # Context ID -> tree item ID (persists after context creator exits for detached subthreads)
        self.context_items: Dict[str, str] = {}

        self._build_ui()

        if self.file_path:
            self._load_file(self.file_path)

        self.root.after(self.POLL_INTERVAL_MS, self._poll_file)

    def _build_ui(self) -> None:
        # --- Top toolbar
        toolbar = ttk.Frame(self.root, padding=(8, 6))
        toolbar.pack(fill=tk.X)

        ttk.Button(toolbar, text="Open...", command=self._choose_file).pack(
            side=tk.LEFT, padx=(0, 6)
        )

        self.pause_btn = ttk.Button(toolbar, text="Pause", command=self._toggle_pause)
        self.pause_btn.pack(side=tk.LEFT, padx=(0, 6))

        ttk.Button(toolbar, text="Reload", command=self._reload_file).pack(
            side=tk.LEFT, padx=(0, 6)
        )

        ttk.Button(toolbar, text="Clear", command=self._clear_view).pack(
            side=tk.LEFT, padx=(0, 6)
        )

        self.expand_btn = ttk.Button(
            toolbar, text="Fold All", command=self._toggle_expand_all
        )
        self.expand_btn.pack(side=tk.LEFT, padx=(0, 12))

        self.follow_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(toolbar, text="Follow tail", variable=self.follow_var).pack(
            side=tk.LEFT, padx=(0, 12)
        )

        self.wrap_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            toolbar,
            text="Wrap lines",
            variable=self.wrap_var,
            command=self._rebuild_tree,
        ).pack(side=tk.LEFT, padx=(0, 12))

        self.group_scopes_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            toolbar,
            text="Group by scope",
            variable=self.group_scopes_var,
            command=self._rebuild_tree,
        ).pack(side=tk.LEFT, padx=(0, 12))

        self.hide_empty_scopes_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            toolbar,
            text="Hide empty scopes",
            variable=self.hide_empty_scopes_var,
            command=self._rebuild_tree,
        ).pack(side=tk.LEFT, padx=(0, 12))

        self.raw_mode_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            toolbar,
            text="Raw",
            variable=self.raw_mode_var,
            command=self._rebuild_tree,
        ).pack(side=tk.LEFT, padx=(0, 12))

        self.file_label_var = tk.StringVar(value="No file loaded")
        ttk.Label(toolbar, textvariable=self.file_label_var, foreground="#555555").pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )

        # --- Filter bar
        filters = ttk.Frame(self.root, padding=(8, 0, 8, 6))
        filters.pack(fill=tk.X)

        ttk.Label(filters, text="Min Level:").pack(side=tk.LEFT, padx=(0, 4))
        self.level_var = tk.StringVar(value="trace")
        level_cb = ttk.Combobox(
            filters,
            textvariable=self.level_var,
            values=["trace", "debug", "info", "warning", "error", "critical"],
            state="readonly",
            width=10,
        )
        level_cb.pack(side=tk.LEFT, padx=(0, 12))
        level_cb.bind("<<ComboboxSelected>>", lambda _e: self._rebuild_tree())

        ttk.Label(filters, text="Thread:").pack(side=tk.LEFT, padx=(0, 4))
        self.thread_var = tk.StringVar(value="All")
        self.thread_cb = ttk.Combobox(
            filters,
            textvariable=self.thread_var,
            values=["All"],
            state="readonly",
            width=12,
        )
        self.thread_cb.pack(side=tk.LEFT, padx=(0, 12))
        self.thread_cb.bind("<<ComboboxSelected>>", lambda _e: self._rebuild_tree())

        ttk.Label(filters, text="Module:").pack(side=tk.LEFT, padx=(0, 4))
        self.module_var = tk.StringVar(value="All")
        self.module_cb = ttk.Combobox(
            filters,
            textvariable=self.module_var,
            values=["All"],
            state="readonly",
            width=16,
        )
        self.module_cb.pack(side=tk.LEFT, padx=(0, 12))
        self.module_cb.bind("<<ComboboxSelected>>", lambda _e: self._rebuild_tree())

        ttk.Label(filters, text="Search:").pack(side=tk.LEFT, padx=(0, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_args: self._rebuild_tree())
        search_entry = ttk.Entry(filters, textvariable=self.search_var, width=28)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # --- Treeview
        tree_frame = ttk.Frame(self.root)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))

        columns = ("time", "thread", "level", "module", "duration")
        self.tree = ttk.Treeview(
            tree_frame, columns=columns, show="tree headings", selectmode="browse"
        )

        self.tree.heading("#0", text="Scope / Message", anchor=tk.W)
        self.tree.heading("time", text="Time", anchor=tk.W)
        self.tree.heading("thread", text="Thread", anchor=tk.W)
        self.tree.heading("level", text="Level", anchor=tk.W)
        self.tree.heading("module", text="Module", anchor=tk.W)
        self.tree.heading("duration", text="Duration", anchor=tk.E)

        self.tree.column("#0", width=520, minwidth=200, stretch=True)
        self.tree.column("time", width=165, minwidth=120, stretch=False)
        self.tree.column("thread", width=80, minwidth=60, stretch=False)
        self.tree.column("level", width=75, minwidth=60, stretch=False)
        self.tree.column("module", width=120, minwidth=80, stretch=False)
        self.tree.column("duration", width=90, minwidth=70, stretch=False, anchor=tk.E)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        for lvl, color in LEVEL_COLORS.items():
            self.tree.tag_configure(lvl, foreground=color)

        scope_font = tkfont.nametofont("TkDefaultFont").copy()
        scope_font.configure(weight="bold")
        self.tree.tag_configure("scope", font=scope_font)

        # --- Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(
            self.root, textvariable=self.status_var, padding=(8, 3), relief=tk.SUNKEN
        )
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def _choose_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Open Log File",
            filetypes=[("Log files", "*.log *.txt"), ("All files", "*.*")],
        )
        if path:
            self._load_file(path)

    def _reload_file(self) -> None:
        if self.file_path:
            self._load_file(self.file_path)

    def _toggle_pause(self) -> None:
        self.paused = not self.paused
        self.pause_btn.configure(text="Resume" if self.paused else "Pause")
        self._update_status()

    def _toggle_expand_all(self) -> None:
        self.all_expanded = not self.all_expanded
        self.expand_btn.configure(text="Fold All" if self.all_expanded else "Expand All")
        self._set_open_recursive("", self.all_expanded)

    def _set_open_recursive(self, parent: str, is_open: bool) -> None:
        for item_id in self.tree.get_children(parent):
            self.tree.item(item_id, open=is_open)
            self._set_open_recursive(item_id, is_open)

    def _clear_view(self) -> None:
        self.entries.clear()
        self.scope_stacks.clear()
        self.context_items.clear()
        self.tree.delete(*self.tree.get_children())
        self._update_status()

    def _load_file(self, path: str) -> None:
        self.file_path = os.path.abspath(path)
        self.file_offset = 0
        self.file_inode = None
        self.entries.clear()
        self.threads.clear()
        self.modules.clear()
        self.scope_stacks.clear()
        self.context_items.clear()
        self.tree.delete(*self.tree.get_children())
        self.file_label_var.set(self.file_path)
        self._read_new_lines()

    def _poll_file(self) -> None:
        if self.file_path and not self.paused:
            self._read_new_lines()
        self.root.after(self.POLL_INTERVAL_MS, self._poll_file)

    def _read_new_lines(self) -> None:
        if not self.file_path or not os.path.exists(self.file_path):
            return

        try:
            stat = os.stat(self.file_path)
        except OSError:
            return

        # Handle file truncation or replacement (e.g. app restarted with truncate=true)
        if (
            self.file_inode is not None and stat.st_ino != self.file_inode
        ) or stat.st_size < self.file_offset:
            self.file_offset = 0
            self.entries.clear()
            self.scope_stacks.clear()
            self.context_items.clear()
            self.tree.delete(*self.tree.get_children())

        self.file_inode = stat.st_ino
        if stat.st_size == self.file_offset:
            return

        try:
            with open(self.file_path, "r", encoding="utf-8", errors="replace") as fh:
                fh.seek(self.file_offset)
                new_lines = fh.readlines()
                self.file_offset = fh.tell()
        except OSError:
            return

        if not new_lines:
            return

        filters_updated = False
        last_item = None

        for line in new_lines:
            if not line.strip():
                continue
            entry = parse_log_line(line)
            self.entries.append(entry)

            if entry.thread_id not in self.threads:
                self.threads.append(entry.thread_id)
                filters_updated = True
            if entry.module not in self.modules:
                self.modules.append(entry.module)
                filters_updated = True

            item = self._insert_entry_if_matches(entry)
            if item is not None:
                last_item = item

        if filters_updated:
            self.thread_cb.configure(values=["All"] + self.threads)
            self.module_cb.configure(values=["All"] + self.modules)

        if last_item is not None and self.follow_var.get():
            self.tree.see(last_item)

        self._update_status()

    def _matches_filter(self, entry: LogEntry) -> bool:
        min_level = LEVEL_ORDER.get(self.level_var.get(), 0)
        if LEVEL_ORDER.get(entry.level, 0) < min_level:
            return False

        thread_filter = self.thread_var.get()
        if thread_filter != "All" and entry.thread_id != thread_filter:
            return False

        module_filter = self.module_var.get()
        if module_filter != "All" and entry.module != module_filter:
            return False

        query = self.search_var.get().strip().lower()
        if query and query not in entry.raw.lower():
            return False

        return True

    def _insert_entry_if_matches(self, entry: LogEntry) -> Optional[str]:
        raw_mode = self.raw_mode_var.get()
        group_scopes = (not raw_mode) and self.group_scopes_var.get()
        stack = self.scope_stacks.setdefault(entry.thread_id, [])

        if group_scopes and entry.scope_close is not None:
            # Close matching scope on this thread's stack and attach duration
            for idx in range(len(stack) - 1, -1, -1):
                name, item_id = stack[idx]
                if name == entry.scope_close:
                    del stack[idx:]
                    if self.tree.exists(item_id):
                        if self.hide_empty_scopes_var.get() and not self.tree.get_children(item_id):
                            self.tree.delete(item_id)
                        elif entry.duration:
                            self.tree.set(item_id, "duration", entry.duration)
                    return None
            # Unmatched close: fall through and display as normal line

        if not self._matches_filter(entry):
            return None

        parent_id = (stack[-1][1] if stack else "") if group_scopes else ""
        if group_scopes and not parent_id and entry.ctx_path:
            ctx_id = entry.ctx_path[-1]
            if ctx_id in self.context_items:
                parent_id = self.context_items[ctx_id]
            elif len(entry.ctx_path) > 1 and entry.ctx_path[-2] in self.context_items:
                parent_id = self.context_items[entry.ctx_path[-2]]
        if parent_id and not self.tree.exists(parent_id):
            parent_id = ""

        is_scope_node = group_scopes and entry.scope_open is not None
        label = entry.raw if raw_mode else (entry.scope_open if is_scope_node else entry.message)
        if self.wrap_var.get() and not is_scope_node:
            col_px = self.tree.column("#0", "width")
            wrap_width = max(40, col_px // 7)
            lines = textwrap.wrap(label, width=wrap_width) or [label]
        else:
            lines = [label]

        tags = (entry.level, "scope") if is_scope_node else (entry.level,)
        item_id = self.tree.insert(
            parent_id,
            tk.END,
            text=lines[0],
            values=(
                entry.timestamp,
                entry.thread_id,
                entry.level,
                entry.module,
                entry.duration,
            ),
            tags=tags,
            open=self.all_expanded,
        )

        for cont_line in lines[1:]:
            self.tree.insert(
                parent_id,
                tk.END,
                text=cont_line,
                values=("", "", "", "", ""),
                tags=(entry.level,),
                open=True,
            )

        if is_scope_node:
            stack.append((entry.scope_open, item_id))
            if entry.ctx_path and entry.ctx_path[-1] not in self.context_items:
                self.context_items[entry.ctx_path[-1]] = item_id

        return item_id

    def _rebuild_tree(self) -> None:
        self.scope_stacks.clear()
        self.context_items.clear()
        self.tree.delete(*self.tree.get_children())

        last_item = None
        for entry in self.entries:
            item = self._insert_entry_if_matches(entry)
            if item is not None:
                last_item = item

        if last_item is not None and self.follow_var.get():
            self.tree.see(last_item)

        self._update_status()

    def _update_status(self) -> None:
        state = "Paused" if self.paused else "Tailing"
        warnings = 0
        errors = 0
        criticals = 0
        for entry in self.entries:
            if entry.level == "warning":
                warnings += 1
            elif entry.level == "error":
                errors += 1
            elif entry.level == "critical":
                criticals += 1

        self.status_var.set(
            f"{state} | Entries: {len(self.entries)} | Warnings: {warnings} | Errors: {errors} | Criticals: {criticals}"
        )


def main() -> None:
    initial_file = sys.argv[1] if len(sys.argv) > 1 else None
    root = tk.Tk()
    LogViewerApp(root, initial_file=initial_file)
    root.mainloop()


if __name__ == "__main__":
    main()
