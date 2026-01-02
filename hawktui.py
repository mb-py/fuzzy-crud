import time
from datetime import datetime
from typing import List, Callable

from rich.console import Console, Group, group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.box import ROUNDED, SIMPLE
from rich.rule import Rule
from rich.style import Style

# Importing the keyboard listener
import pygetwindow as gw
import keyboard
from typing import Literal
from datascrivener import TypeScribe
from dataclasses import fields

EventTypes = Literal["changed", "submitted", "accessed"]

class commandField():
    def __init__(self, scribe: TypeScribe):
        self.scribe = scribe
        self._data: str | None = None
        self.suggestion_text: str | None = None
        self._subscribers: dict[str, list[Callable[[str | None], None]]] = {
                "changed": [],
                "submitted": [],
                "accessed": []
        }
    # Standard property logic
    @property
    def input_text(self) -> str:
        return self._data if self._data is not None else ""

    @input_text.setter
    def input_text(self, new_input: str):
        if self._data != new_input:
            self._data = new_input
            self._emit("changed", self._data)

    def _emit(self, event_name: EventTypes, data: str | None):
        """Internal helper to fire all callbacks for a specific channel."""
        for callback in self._subscribers.get(event_name, []):
            callback(data)

    # --- The Decorator Factory ---
    def on(self, event_name: EventTypes):
        """A factory that returns a decorator for a specific event."""
        def decorator(func: Callable[[str | None], None]):
            if event_name not in self._subscribers:
                self._subscribers[event_name] = []
            self._subscribers[event_name].append(func)
            return func
        return decorator
    
    def key_event(self, event: keyboard.KeyboardEvent):
        if event.name is None: return
        key: str = event.name
        data = self._data if self._data is not None else ""
        if len(key) == 1:
            self.input_text = data + key
        elif key == 'backspace':
            self.input_text = data[:-1]
        elif key == 'space':
            self.input_text = data + " " 
        elif key == 'tab' and self.suggestion_text is not None:
            self.input_text = self.suggestion_text
        elif key == 'enter':
            self._emit("submitted", self._data)

    def clear(self):
        self.input_text = ""
    
    def suggest(self, text: str | None):
        if text is not None:
            self.suggestion_text = text
    
    def compose(self, focused: bool, placeholder: str | None = None) -> Panel:
        # --- Styling ---
        cursor_style = "white"  if focused else "bright_black"
        input_text_style = "bright_white"
        ghost_text_style= "bright_black"
        border_style = "bright_black"
        # --- Textfield ---
        content = Text("> ", style=cursor_style)
        if placeholder and not self.input_text:
            self.suggestion_text = placeholder
        has_suggestion: bool = self.suggestion_text is not None and len(self.suggestion_text) > len(self.input_text)
        cursor_visible: bool = focused and int(time.time() * 2) % 2 == 0
        # Entered text in bold white
        content.append(self.input_text, style=input_text_style)
        # Suggestion text in grey after the input
        if has_suggestion:
            ghost_text = self.suggestion_text[len(self.input_text):] if self.suggestion_text is not None else ""
            if cursor_visible:
                if len(ghost_text) > 1:
                    # Remove first char of ghost text
                    content.append(ghost_text[:1], style=f"r {cursor_style}")
                    content.append(ghost_text[1:], style=ghost_text_style)
                else:
                    content.append("█", style=cursor_style)
            else:
                # Just render the ghost text normally
                content.append(ghost_text, style=ghost_text_style)
        elif cursor_visible:
            # No suggestion, only cursor
            content.append("█", style=cursor_style)

        return Panel(content, title=f"[b {cursor_style}]Command Input[/]", border_style=border_style, box=ROUNDED) 

class inspectObject():
    def __init__(self, scribe: TypeScribe):
        self.scribe = scribe
        self.obj = self.scribe[0]
        self.obj_type = self.obj.__class__
        self.fields: list[str] = []
        self.field_idx = 0
    
    def point(self, i):
        self.field_idx = 0
        self.fields.clear()
        self.obj = self.scribe[i]
        self.obj_type = self.obj.__class__

    def compose(self, edit: bool) -> Panel:
        self.fields.clear()
        title = "Edit" if edit else "Create"
        @group()
        def make_stuff():
            obj_fields = fields(self.obj_type)        
            idx = 0
            for f in obj_fields:
                # Skip internal or complex calculated fields if necessary
                if f.name in ["uid"]:
                    continue
                self.fields.append(f.name)
                val = str(getattr(self.obj, f.name)) if self.obj else ""
                selected = "reverse" if self.field_idx == idx else "bold white"
                yield Rule(f"{f.name.title()}", style="bold white")
                yield Text(f"{val}\n", style=selected)
                idx += 1
            self.fields.append("Exit")
            selected = "cyan" if self.field_idx == idx else "bright_black"
            yield Panel(Text(f"Return", style="bold white"), border_style=selected, box=ROUNDED)
        return Panel(make_stuff(), title=f"[bold]{title} - {self.obj_type.__name__}[/]", border_style="blue", box=ROUNDED)

class DataTable():

    def __init__(self, console: Console, scribe: TypeScribe):
        self.console = console
        self.scribe = scribe
        self.cursor_index = 0

    def cusor_down(self):
        max_index = self.scribe.count - 1 if self.scribe.count > 0 else 0
        if self.cursor_index < max_index:
            self.cursor_index = self.cursor_index + 1

    def cursor_up(self):
        min_index = 0
        if self.cursor_index > min_index:
            self.cursor_index = self.cursor_index - 1
        
    def compose(self, focused:bool) -> Panel:
        # --- Styling ---
        title_style = "white"  if focused else "bright_black"
        panel_style = "bright_black"
        table_style = "bright_black"
        # --- Table ---
        table = Table(expand=True, box=ROUNDED, border_style=table_style)
        # --- Table Size and Scrolling Parameters---
        table_max_size = self.console.size.height -19
        table_max_depth = self.scribe.count - 1 if self.scribe.count else 0
        cursor_max_depth = table_max_size if table_max_size > table_max_depth else table_max_size//2
        start_idx, end_idx = 0, 0
        # --- Columns ---
        all_cols = self.scribe.get_columns()
        for col in all_cols:
            r = 1 if col in ["Geslacht", "Huisnummer"] else 2 if col in ["Bouwjaar", "Prijs", "Postcode"] else 3 if col in ["BTW/RRN", "Gemeente", "Straat", "Merk", "Van", "Tot"] else 4
            table.add_column(col, ratio=r, overflow="ellipsis")
        # Add the '...' trimming row at the top of the table
        if self.cursor_index > cursor_max_depth:
            table.add_row(*["..." for _ in all_cols], style="color(240)")
            start_idx = self.cursor_index - cursor_max_depth + 1
            if self.cursor_index > (table_max_depth - table_max_size//2):
                start_idx = table_max_depth - table_max_size + 2
            # Prevent trimming at the bottom
            if self.cursor_index < (table_max_depth - table_max_size//2):
                end_idx -= 1
        end_idx += start_idx + cursor_max_depth + table_max_size//2
        # --- Render Visible Rows ---
        for i, row in enumerate(self.scribe.get_rows(start_idx, end_idx)):
            selected: bool = (start_idx + i == self.cursor_index)
            color = 255 - abs(start_idx + i - self.cursor_index) // (1 + table_max_size//20)
            row_style = "r bright_white" if selected and focused else f"color({color})"
            table.add_row(*[str(item) for item in row], style=row_style)
        # Add the '...' trimming row at the bottom
        if end_idx < table_max_depth:
            table.add_row(*["..." for _ in all_cols], style="color(240)")
        # --- Keep Cursor in Bounds if Table Shrinks ---
        if self.cursor_index > table_max_depth: 
            self.cursor_index = table_max_depth

        return Panel(table, title=f"[b {title_style}]DATATABLE[/] ({self.scribe.count})", border_style=panel_style, box=ROUNDED)