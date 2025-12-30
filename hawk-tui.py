import os
import sys
import time
import threading
import logging
from datetime import datetime, date
from typing import List, Optional

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

# Assuming datascrivener.py is in the same directory
from datascrivener import KlantScribe, VoertuigScribe, TypeScribe
from datastore import klanten, read_data
from dataclasses import fields
read_data()

class commandInput():

    def __init__(self, scribe: TypeScribe):
        self.scribe = scribe
        self.input_text: str = ""
        self.suggestion_text: str | None = None

    def key(self, name: str):
        if len(name) == 1:
            self += name
        elif name == 'backspace':
            self -= 1
        elif name == 'space':
            self += " "
        elif name == 'tab' and self.suggestion_text is not None:
            self.input_text = self.suggestion_text
        elif name == 'enter':
            return self.input_text

            '''if self.inspect:
                edit.field_idx = (edit.field_idx + 1) % len(edit.fields)
                self.cmd.clear()
                self.cmd.suggest(f"{edit.fields[edit.field_idx].capitalize()}:")
            else:'''

    def __iadd__ (self, other: str):
        if len(other) == 1:
            self.input_text += other
        return self
    
    def __isub__ (self, i: int):
        self.input_text = self.input_text[:-i]
        return self

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
        all_cols = self.scribe.get_columns()
        all_rows = self.scribe.get_rows()
        # --- Columns ---
        for col in all_cols:
            r = 1 if col in ["Geslacht", "Huisnummer"] else 2 if col in ["Bouwjaar", "Prijs", "Postcode"] else 3 if col in ["BTW/RRN", "Gemeente", "Straat", "Merk", "Van", "Tot"] else 4
            table.add_column(col, ratio=r, overflow="ellipsis")
        # --- Resizing ---
        table_max_depth = self.scribe.count - 1
        if self.cursor_index > table_max_depth:
            self.cursor_index = table_max_depth
        # --- Scrolling ---
        table_max_size = self.console.size.height -19
        cursor_max_depth = table_max_size if table_max_size > table_max_depth else table_max_size//2
        start_idx, end_idx = 0, 0
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
        visible_rows = all_rows[start_idx:end_idx]
        for i, row in enumerate(visible_rows):
            selected: bool = (start_idx + i == self.cursor_index)
            color = 255 - abs(start_idx + i - self.cursor_index) // (1 + table_max_size//20)
            row_style = "r bright_white" if selected and focused else f"color({color})"
            table.add_row(*[str(item) for item in row], style=row_style)
        # Add the '...' trimming row at the bottom
        if end_idx < table_max_depth:
            table.add_row(*["..." for _ in all_cols], style="color(240)")

        return Panel(table, title=f"[b {title_style}]DATATABLE[/] ({self.scribe.count})", border_style=panel_style, box=ROUNDED)

class TerminalApp:
    def __init__(self, window):
        self.console = Console(color_system='256', stderr=True)
        # Jank shit
        self.window = window
        self.running = True
        self.live = None
        self.logs: List[Text] = []
        self.is_hooked = False

        # Layout
        self.layout = None
        self.title = "Fuzzy CRUD"
        self.subtitle = "Data Overzicht"

        # Initialize the Scribe
        self.scribe = klanten
        self.editor = inspectObject(klanten)
        self.inspect = False

        # Focus management: "input", "sidepanel", "datatable"
        self.focus = "input"

        #Input Parameters
        self.cmd = commandInput(self.scribe)
        
        # Sidepanel Parameters
        self.sidepanel_open = False
        self.menu_items = ["Dashboard", "Klanten", "Create", "Edit"]
        self.menu_idx = 1 # "Klanten"

        # DataTable parameters
        self.table = DataTable(self.console, self.scribe)

    def add_log(self, message: str):
        self.logs.append(Text.assemble((f"[{datetime.now().strftime('%H:%M')}] ", "dim"), (message)))
        if len(self.logs) > 4: self.logs.pop(0)

    def make_layout(self) -> Layout:
        """Define the application layout structure."""
        layout = Layout(name="root")
        layout.split(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="logs", size=6),
            Layout(name="input_area", size=3),
            Layout(name="footer", size=1),
        )

        layout["body"].split_row(
            Layout(name="sidepanel", size=25 if self.sidepanel_open else 3),
            Layout(name="datatable", ratio=1),
        )

        return layout

    def header(self) -> Panel:
        """Create the top header bar."""
        grid = Table.grid(expand=True)
        grid.add_column(justify="left", ratio=1)
        grid.add_column(justify="right")
        
        header_text = Text()
        header_text.append(f" {self.title}", style="bold white")
        if self.subtitle:
            header_text.append(f" — {self.subtitle}", style="bold bright_black")
            
        grid.add_row(
            header_text,
            Text(datetime.now().strftime("%H:%M:%S"), style="bright_black"),
        )
        return Panel(grid, style="bright_black", box=ROUNDED)

    def sidepanel(self) -> Panel:
        if not self.sidepanel_open:
            return Panel("")
        
        if self.inspect == 0:
            return self.menu()
        
        if self.inspect != 0:
            return self.editor.compose(edit=True)
        
        return Panel("")
    
    def menu(self) -> Panel:
        menu = Text()      
        for i, item in enumerate(self.menu_items):
            # Highlight logic
            is_selected = (i == self.menu_idx)
            style = "dim white"
            
            if self.focus == "sidepanel":  
                if is_selected:
                    style = "reverse"
                else:
                    style = "bold white"
            
            prefix = " > " if is_selected else "   "
            menu.append(f"{prefix}{item.ljust(18)}\n", style=style)
        return Panel(menu, title="[bold]Menu[/]", border_style="bright_black" if self.focus != "sidepanel" else "blue", box=ROUNDED)

    def datatable(self) -> Panel:
        f = True if self.focus == 'datatable' else False
        return self.table.compose(focused=f)

    def input_field(self) -> Panel:
        return self.cmd.compose(focused=True, placeholder="Fuzzy Search")

    def footer(self) -> Text:
        footer = Text(justify="center")
        hints = []
        if self.focus == "input" and not self.inspect:
            hints = [
                ("ENTER", "Focus Table"), 
                ("TAB", "Autocomplete"), 
                ("ESC", "Quit")
            ]
        if self.focus == "input" and self.inspect:
            hints = [
                ("ENTER", "Enter Data"), 
                ("TAB", "Skip Field"), 
                ("ESC", "Quit")
            ]
        if self.focus == "datatable":
            hints = [
                ("m", "Open Menu"), 
                ("j", "Cursor Down"), 
                ("k", "Cursor Up"), 
                ("e", "Edit"), 
                ("s", "Select"), 
                ("d", "Delete"), 
                ("c", "Create"), 
                ("f", "Fuzzy Search"), 
                ("ESC", "Quit")
            ]
        for key, desc in hints:
            footer.append(f" {key} ", style="bold white")
            footer.append(f" {desc}  ", style="dim")
        return footer

    def handle_enter(self):
        edit = self.editor
        if self.focus == "input" and self.sidepanel_open and self.inspect:
            pass
        elif self.focus == "input":
            self.focus = "datatable"

    def cycle_inspect(self, enter: bool):
        edit = self.editor
        name = edit.fields[edit.field_idx]
        if name == "Exit":
            self.sidepanel_open = False
            self.inspect = False
            self.focus = "datatable"
        elif self.input_text:
            setattr(edit.obj, name, self.input_text)
            edit.field_idx = (edit.field_idx + 1) % len(edit.fields)
            self.input_text = ""
            self.suggestion_text = f" {name.capitalize()}:"

    def on_key_event(self, event: keyboard.KeyboardEvent):
        if event.event_type != keyboard.KEY_DOWN:
            return True # Suppress everything while focused
        
        key = event.name
        if key == 'esc':
            self.running = False
            return True
        
        key_name = event.name
        edit = self.editor

        # Check for Quit
        if key_name == 'esc':
            self.running = False
            return
        try:
            # Context: Input Field
            if self.focus == "input" and key_name:
                if key_name == 'enter':
                    self.handle_enter()
                else: # Regular character
                    self.cmd.key(key_name)
            
            # Context: DataTable
            elif self.focus == "datatable":
                selected_row: int = self.table.cursor_index
                if key_name == 'm':
                    self.sidepanel_open = True
                    self.inspect = 0
                    self.focus = "sidepanel"
                elif key_name == 'e':
                    self.editor.point(selected_row)
                    self.editor.compose(edit=True)
                    self.sidepanel_open = True
                    self.inspect = True
                    self.focus = "input"
                    self.cmd.clear()
                    self.cmd.suggest(f" {edit.fields[edit.field_idx].capitalize()}:")
                elif key_name == 'j' or key_name == 'down':
                    #self.selected_row_idx = min(self.selected_row_idx + 1, self.scribe.count - 1)
                    self.table.cusor_down()
                elif key_name == 'k' or key_name == 'up':
                    #self.selected_row_idx = max(self.selected_row_idx - 1, 0)
                    self.table.cursor_up()
                elif key_name == 'f':
                    self.focus = "input"
                elif key_name == 'space':
                    self.sidepanel_open = not self.sidepanel_open
        except Exception as e:
            self.add_log(f"Error: {e}")

        # Global Logic for suggestions
        if not self.inspect:
            query = self.cmd.input_text if self.cmd.input_text else  ""
            suggestion = self.scribe.get_suggestion(query)
            self.cmd.suggest(suggestion)
        return True

    def update_display(self, layout: Layout):
        """Map components to layout slots."""
        layout["sidepanel"].size = 25 if self.sidepanel_open else 3
        layout["header"].update(self.header())
        layout["sidepanel"].update(self.sidepanel())
        layout["datatable"].update(self.datatable())
        layout["input_area"].update(self.input_field())
        layout["footer"].update(self.footer())
        
        log_content = Text()
        for l in self.logs: log_content.append(l); log_content.append("\n")
        layout["logs"].update(Panel(log_content, title="Activity", border_style="bright_black", box=ROUNDED))

    def run(self):

        self.layout = self.make_layout()
        try:
            with Live(self.layout, refresh_per_second=10, screen=True, redirect_stdout=False) as self.live:
                while self.running:
                    # DYNAMIC HOOKING BASED ON WINDOW FOCUS
                    is_active = (gw.getActiveWindow() == self.window)
                    if is_active and not self.is_hooked:
                        keyboard.hook(self.on_key_event, suppress=True)
                        self.is_hooked = True
                    elif not is_active and self.is_hooked:
                        keyboard.unhook_all()
                        self.is_hooked = False
                    self.update_display(self.layout)
                    time.sleep(0.05)
        finally:
            keyboard.unhook_all()

if __name__ == "__main__":
    import pygetwindow as gw
    terminal = None
    while terminal is None:
        terminal = gw.getActiveWindow()
    if terminal:
        app = TerminalApp(terminal)
        app.run()