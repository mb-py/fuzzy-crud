import time
from datetime import datetime
from typing import List

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.box import ROUNDED

# Importing the keyboard listener
import pygetwindow as gw
import keyboard

# Assuming datascrivener.py is in the same directory
from hawktui import DataTable, commandField, inspectObject
from datastore import klanten, read_data
read_data()

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
        self.cmd = commandField(self.scribe)

        @self.cmd.on("changed")
        def update_suggestion(value: str | None):
            if not self.inspect:
                query = value if value else  ""
                suggestion = self.scribe.get_suggestion(query)
                self.cmd.suggest(suggestion)
        
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
            return False # Suppress everything while focused
        
        key = event.name
        if key == 'esc':
            self.running = False
            return False
        
        key_name = event.name
        edit = self.editor

        # Check for Quit
        if key_name == 'esc':
            self.running = False
            return
        try:
            # Context: Input Field
            if self.focus == "input":
                self.cmd.key_event(event)
            
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

        return False

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