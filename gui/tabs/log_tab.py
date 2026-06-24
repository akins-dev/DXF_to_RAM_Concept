"""
log_tab.py
==========
Tab for the scrollable, colour-coded run log.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from gui.theme import *
from gui.widgets import styled_btn


class LogTab(tk.Frame):
    """Run log tab with colour-coded messages."""

    def __init__(self, parent, app):
        super().__init__(parent, bg=C_PANEL)
        self.app = app
        self._build()

    def _build(self):
        ctrl = tk.Frame(self, bg=C_PANEL)
        ctrl.pack(fill="x", padx=8, pady=4)
        styled_btn(ctrl, "Clear Log", self._clear).pack(side="left", padx=4)
        styled_btn(ctrl, "Copy All", self._copy).pack(side="left", padx=4)

        self.log_text = tk.Text(
            self,
            bg="#0F172A",
            fg=C_TEXT,
            insertbackground=C_TEXT,
            font=("Consolas", 9),
            wrap="word",
            state="disabled",
            relief="flat",
        )
        sb = ttk.Scrollbar(self, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log_text.pack(fill="both", expand=True, padx=8, pady=4)

        self.log_text.tag_configure("WARN", foreground=C_WARN)
        self.log_text.tag_configure("ERROR", foreground=C_ERROR)
        self.log_text.tag_configure("SUCCESS", foreground=C_SUCCESS)
        self.log_text.tag_configure("INFO", foreground=C_ACCENT2)
        self.log_text.tag_configure("NORMAL", foreground=C_TEXT)

    def append(self, msg: str, level: str = "NORMAL"):
        """Append a message to the log."""
        self.log_text.configure(state="normal")
        # Auto-detect level from content
        if "error" in msg.lower() or "failed" in msg.lower() or "fatal" in msg.lower():
            tag = "ERROR"
        elif "⚠" in msg or "warn" in msg.lower() or "skip" in msg.lower():
            tag = "WARN"
        elif "✓" in msg or "complete" in msg.lower() or "saved" in msg.lower():
            tag = "SUCCESS"
        elif "---" in msg or msg.startswith("Adding") or msg.startswith("Generat"):
            tag = "INFO"
        else:
            tag = level
        self.log_text.insert("end", msg + "\n", tag)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _copy(self):
        content = self.log_text.get("1.0", "end")
        self.winfo_toplevel().clipboard_clear()
        self.winfo_toplevel().clipboard_append(content)
