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

import pygetwindow as gw
import keyboard

from hawktui import commandField, ObjectEditor, DataTable
from datastore import klanten, voertuigen, reserveringen, read_data
from appstate import AppState, AppMode, ModeKeyBindings
from datamodel import Reservering, Particulier, Professioneel, Voertuig

read_data()

class TerminalApp:
    def __init__(self, window):
        self.console = Console(color_system='256', stderr=True)
        self.window = window
        self.running = True
        self.live = None
        self.logs: List[Text] = []
        self.is_hooked = False
        
        # State management
        self.state = AppState()
        self.state.active_scribe = klanten
        
        # Layout
        self.layout: Layout | None = None
        self.title = "Fuzzy CRUD"
        
        # Components
        self.cmd = commandField(self.state.active_scribe)
        self.editor = ObjectEditor(self.state.active_scribe)
        self.table = DataTable(self.console, self.state.active_scribe)
        self.selection_table: DataTable | None = None
        
        # Setup event handlers
        self._setup_command_handlers()
    
    def _setup_command_handlers(self):
        """Setup command field event handlers"""
        
        @self.cmd.on("changed")
        def on_query_changed(value: str | None):
            if self.state.mode == AppMode.SEARCHING or self.state.mode == AppMode.SELECTING:
                query = value if value else ""
                delta = time.perf_counter_ns()
                
                # Use appropriate scribe for search
                scribe = self.state.selection_scribe if self.state.mode == AppMode.SELECTING else self.state.active_scribe
                assert scribe is not None
                suggestion = scribe.get_suggestion(query)
                
                delta = time.perf_counter_ns() - delta
                self.add_log(f"Query: {delta/1000:.1f}μs")
                self.cmd.suggest(suggestion)
                
                if self.layout:
                    self.update_display()
        
        @self.cmd.on("submitted")
        def on_submit(value: str | None):
            if self.state.mode == AppMode.SEARCHING:
                self.state.enter_browsing()
            elif self.state.mode in (AppMode.EDITING, AppMode.CREATING):
                data = value if value else ""
                if self.editor.validate_and_submit(data):
                    if self.editor.field_idx >= len(self.editor.names):
                        # Done editing/creating
                        if self.state.mode == AppMode.CREATING:
                            self._finalize_creation()
                        self.state.enter_browsing()
                    else:
                        self.editor.move_next()
                    self.cmd.clear()
                else:
                    self.add_log(f"Invalid value for {self.editor.current_field_name}")
            
            if self.layout:
                self.update_display()
        
        @self.cmd.on("accepted")
        def on_accept(value: str | None):
            if self.state.mode in (AppMode.EDITING, AppMode.CREATING):
                if value:
                    self.editor.validate_and_submit(value)
                self.editor.move_next()
                self.cmd.clear()
                if self.editor.field_idx >= len(self.editor.names):
                    if self.state.mode == AppMode.CREATING:
                        self._finalize_creation()
                    self.state.enter_browsing()
            
            if self.layout:
                self.update_display()
    
    def _finalize_creation(self):
        """Create the new object and add it to the scribe"""
        assert self.state.active_scribe is not None
        try:
            # Build kwargs from editor values
            kwargs = {}
            for i, name in enumerate(self.editor.names):
                value_str = self.editor.values[i]
                if value_str:
                    # Try to convert to appropriate type
                    value = self.editor._convert_value(value_str, self.editor.types[i])
                    kwargs[name] = value
            
            # Create the object
            if self.editor.obj_type:
                new_obj = self.editor.obj_type(**kwargs)
                self.state.active_scribe.add(new_obj)
                self.add_log(f"Created new {self.editor.obj_type.__name__}")
                self.state.active_scribe.refresh(all=True)
        except Exception as e:
            self.add_log(f"Error creating object: {e}")
    
    def add_log(self, message: str):
        """Add a log message"""
        self.logs.append(
            Text.assemble(
                (f"[{datetime.now().strftime('%H:%M')}] ", "dim"),
                (message)
            )
        )
        if len(self.logs) > 4:
            self.logs.pop(0)
    
    def make_layout(self) -> Layout:
        """Create the application layout"""
        layout = Layout(name="root")
        layout.split(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="logs", size=6),
            Layout(name="input_area", size=3),
            Layout(name="footer", size=1),
        )
        
        sidepanel_size = 25 if self.state.sidepanel_open else 3
        layout["body"].split_row(
            Layout(name="sidepanel", size=sidepanel_size),
            Layout(name="datatable", ratio=1),
        )
        
        return layout
    
    def header(self) -> Panel:
        """Create header panel"""
        grid = Table.grid(expand=True)
        grid.add_column(justify="left", ratio=1)
        grid.add_column(justify="right")
        
        header_text = Text()
        header_text.append(f" {self.title}", style="bold white")
        
        # Add mode indicator
        mode_name = self.state.mode.name.title()
        header_text.append(f" — {mode_name}", style="bold bright_black")
        
        # Add scribe name
        scribe_name = self.state.active_scribe.__class__.__name__.replace("Scribe", "")
        header_text.append(f" / {scribe_name}", style="bright_black")
        
        grid.add_row(
            header_text,
            Text(datetime.now().strftime("%H:%M:%S"), style="bright_black"),
        )
        return Panel(grid, style="bright_black", box=ROUNDED)
    
    def sidepanel(self) -> Panel:
        """Create sidepanel content"""
        if not self.state.sidepanel_open:
            return Panel("")
        
        if self.state.mode == AppMode.EDITING:
            return self.editor.compose("Edit")
        elif self.state.mode == AppMode.CREATING:
            return self.editor.compose("Create")
        
        return Panel("")
    
    def datatable_panel(self) -> Panel:
        """Create datatable panel"""
        if self.state.mode == AppMode.SELECTING:
            # Show selection table
            if self.selection_table:
                title_suffix = f"Select {self.state.selecting_for}"
                return self.selection_table.compose(focused=True, title_suffix=title_suffix)
        
        return self.table.compose(focused=self.state.is_table_focused)
    
    def input_field(self) -> Panel:
        """Create input field panel"""
        placeholder = "Fuzzy Find"
        
        if self.state.mode in (AppMode.EDITING, AppMode.CREATING):
            placeholder = self.editor.current_value
            if hasattr(self.editor.current_value, 'uid'):
                placeholder = getattr(self.editor.current_value, 'uid')
            placeholder = str(placeholder)
        
        return self.cmd.compose(focused=self.state.is_input_focused, placeholder=placeholder)
    
    def footer(self) -> Text:
        """Create footer with keybindings"""
        footer = Text(justify="center")
        bindings = ModeKeyBindings.get_bindings(self.state.mode)
        
        for binding in bindings:
            footer.append(f" {binding.key} ", style="bold white")
            footer.append(f" {binding.description}  ", style="dim")
        
        return footer
    
    def on_key_event(self, event: keyboard.KeyboardEvent) -> bool:
        """Handle keyboard events based on current mode"""
        if event.event_type != keyboard.KEY_DOWN:
            return False
        
        key = event.name
        if not key:
            return False
        
        try:
            # Handle ESC - universal back/cancel
            if key == 'esc':
                self._handle_escape()
                return False
            
            # Route to mode-specific handlers
            if self.state.mode == AppMode.BROWSING:
                self._handle_browsing_keys(key)
            elif self.state.mode == AppMode.SEARCHING:
                self._handle_searching_keys(key, event)
            elif self.state.mode in (AppMode.EDITING, AppMode.CREATING):
                self._handle_editing_keys(key, event)
            elif self.state.mode == AppMode.SELECTING:
                self._handle_selecting_keys(key)
            
            if self.layout:
                self.update_display()
        
        except Exception as e:
            self.add_log(f"Error: {e}")
        
        return False
    
    def _handle_escape(self):
        """Handle ESC key"""
        if self.state.mode == AppMode.SELECTING:
            self.state.exit_selecting()
            self.selection_table = None
        elif self.state.mode in (AppMode.EDITING, AppMode.CREATING, AppMode.SEARCHING):
            self.state.enter_browsing()
            self.cmd.clear()
        else:
            self.running = False
    
    def _handle_browsing_keys(self, key: str):
        """Handle keys in browsing mode"""
        if key == 'f':
            self.state.enter_searching()
            self.cmd.clear()
        elif key == 'j' or key == 'down':
            self.table.cursor_down()
        elif key == 'k' or key == 'up':
            self.table.cursor_up()
        elif key == 'e':
            # Edit selected item
            self.editor.start_editing(self.table.cursor_index)
            self.state.enter_editing(self.table.cursor_index)
            self.cmd.clear()
        elif key == 'c':
            # Create new item
            obj_type = self._get_create_type()
            if obj_type:
                self.editor.start_creating(obj_type)
                self.state.enter_creating(obj_type)
                self.cmd.clear()
        elif key == 'd':
            # Delete (placeholder)
            self.add_log("Delete not implemented yet")
    
    def _handle_searching_keys(self, key: str, event: keyboard.KeyboardEvent):
        """Handle keys in searching mode"""
        if key in ('enter', 'tab', 'backspace', 'space') or len(key) == 1:
            self.cmd.key_event(event)
    
    def _handle_editing_keys(self, key: str, event: keyboard.KeyboardEvent):
        """Handle keys in editing/creating mode"""
        if key == 's' and self.editor.needs_selection():
            # Enter selection mode
            field_name = self.editor.current_field_name
            if field_name == 'klant':
                self.state.enter_selecting('klant', klanten, self.state.mode)
                self.selection_table = DataTable(self.console, klanten)
                klanten.refresh(all=True)
            elif field_name == 'voertuig':
                self.state.enter_selecting('voertuig', voertuigen, self.state.mode)
                self.selection_table = DataTable(self.console, voertuigen)
                voertuigen.refresh(all=True)
            self.cmd.clear()
        elif key in ('enter', 'tab', 'backspace', 'space') or len(key) == 1:
            self.cmd.key_event(event)
    
    def _handle_selecting_keys(self, key: str):
        """Handle keys in selecting mode"""
        if not self.selection_table:
            return
        
        if key == 's':
            # Select current item
            selected = self.selection_table.get_selected()
            if selected and self.state.selecting_for:
                self.editor.set_field_value(self.state.selecting_for, selected)
                self.add_log(f"Selected {self.state.selecting_for}: {selected.uid}")
                self.state.exit_selecting()
                self.editor.move_next()
                self.selection_table = None
                self.cmd.clear()
        elif key == 'j' or key == 'down':
            self.selection_table.cursor_down()
        elif key == 'k' or key == 'up':
            self.selection_table.cursor_up()
        elif key == 'f':
            self.cmd.clear()
    
    def _get_create_type(self) -> type | None:
        """Determine what type to create based on active scribe"""
        if self.state.active_scribe is klanten:
            # Could prompt for Particulier vs Professioneel
            return Particulier
        elif self.state.active_scribe is voertuigen:
            return Voertuig
        elif self.state.active_scribe is reserveringen:
            return Reservering
        return None
    
    def update_display(self):
        """Update all layout components"""
        if not self.layout:
            return
        
        sidepanel_size = 25 if self.state.sidepanel_open else 3
        self.layout["sidepanel"].size = sidepanel_size
        
        self.layout["header"].update(self.header())
        self.layout["sidepanel"].update(self.sidepanel())
        self.layout["datatable"].update(self.datatable_panel())
        self.layout["input_area"].update(self.input_field())
        self.layout["footer"].update(self.footer())
        
        # Update logs
        log_content = Text()
        for log in self.logs:
            log_content.append(log)
            log_content.append("\n")
        self.layout["logs"].update(
            Panel(log_content, title="Activity", border_style="bright_black", box=ROUNDED)
        )
    
    def run(self):
        """Main application loop"""
        self.layout = self.make_layout()
        self.update_display()
        
        try:
            with Live(self.layout, refresh_per_second=20, screen=True, redirect_stdout=False) as self.live:
                while self.running:
                    # Dynamic window focus detection
                    is_active = (gw.getActiveWindow() == self.window)
                    if is_active and not self.is_hooked:
                        keyboard.hook(self.on_key_event, suppress=True)
                        self.is_hooked = True
                    elif not is_active and self.is_hooked:
                        keyboard.unhook_all()
                        self.is_hooked = False
                    
                    self.update_display()
                    time.sleep(0.05)
        finally:
            keyboard.unhook_all()

if __name__ == "__main__":
    terminal = None
    while terminal is None:
        terminal = gw.getActiveWindow()
    if terminal:
        app = TerminalApp(terminal)
        app.run()