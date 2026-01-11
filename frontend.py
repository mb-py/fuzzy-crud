import time
from datetime import datetime
from typing import List

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.box import ROUNDED, SIMPLE, MINIMAL, SQUARE

import pygetwindow as gw
import keyboard

from hawktui import commandField, ObjectEditor, DataTable, Menu
from datastore import klanten, voertuigen, reserveringen, facturen, read_data, save_data
from appstate import AppState, AppMode, ModeKeyBindings
from datamodel import Reservering, Particulier, Professioneel, Voertuig, Factuur
from datascrivener import TypeScribe, AttributeFilter, InceptionAttributeFilter, RangeFilter, UIDFilter, CompoundFilter, ReservatiemaandFilter

# --- FILTERS OPDRACHT ---
read_data()
filter_particuliere_klanten = AttributeFilter("strftype", "Particulier")
filter_zakelijke_klanten = AttributeFilter("strftype", "Professioneel")
filter_personenwagens = AttributeFilter('categorie', 'M1')
filter_bestelbusjes = AttributeFilter('categorie', 'N1')
filter_beschikbare_wagens = AttributeFilter('beschikbaar', True)
filter_reserveringen_op_duurtijd = RangeFilter('duur', start=4)
filter_september = ReservatiemaandFilter(9)
filter_oktober = ReservatiemaandFilter(10)
filter_november = ReservatiemaandFilter(11)


filter_vrouwelijke_reserveringen = InceptionAttributeFilter('klant', 'geslacht', 'V')
filter_verhuurd = CompoundFilter(filter_vrouwelijke_reserveringen, filter_particuliere_klanten)

def uidmacro():
    reserveringen.set_filter(filter_verhuurd)
    reserveringen.refresh(all=False)
    uids_verhuurd_aan_vrouwen: list[str] = reserveringen.window_state
    reserveringen.refresh(all=True)
    return uids_verhuurd_aan_vrouwen


class TerminalApp:
    def __init__(self, window, scribe):
        self.console = Console(color_system='256', stderr=True)
        self.window = window
        self.running = True
        self.live = None
        self.logs: List[Text] = []
        self.is_hooked = False
        
        # State management
        self.state = AppState()
        self.state.active_scribe = scribe
        
        # Layout
        self.layout: Layout | None = None
        self.title = "Fuzzy CRUD"
        
        # Components
        self.menu = self._create_menu()
        self.cmd = commandField(self.state.active_scribe)
        self.editor = ObjectEditor(self.state.active_scribe)
        self.table = DataTable(self.console, self.state.active_scribe)
        self.selection_table: DataTable | None = None
        
        # Setup event handlers
        self._setup_command_handlers()
        
    def _create_menu(self) -> Menu:
        """Create the main menu with all options"""
        menu = Menu()
        # View options
        if self.state.active_scribe == klanten:
            menu.add_separator("Maak Klanten")
            menu.add_item("Maak Particulier", lambda: self._create_from_menu(klanten, Particulier))
            menu.add_item("Maak Professioneel", lambda: self._create_from_menu(klanten, Professioneel))
            menu.add_separator("Toon Klanten")
            menu.add_item("Toon Alle", lambda: self._switch_scribe(klanten))
            menu.add_item("Toon Particulier", lambda: self._switch_scribe(klanten, filter_particuliere_klanten))
            menu.add_item("Toon Professioneel", lambda: self._switch_scribe(klanten, filter_zakelijke_klanten))
        elif self.state.active_scribe == voertuigen:
            menu.add_separator("Maak Voertuigen")
            menu.add_item("Maak Voertuig", lambda: self._create_from_menu(voertuigen, Voertuig))
            menu.add_separator("Toon Voertuigen")
            menu.add_item("Toon Alle", lambda: self._switch_scribe(voertuigen))
            menu.add_item("Toon Personenwagens", lambda: self._switch_scribe(voertuigen, filter_personenwagens))
            menu.add_item("Toon Bestelbusjes", lambda: self._switch_scribe(voertuigen, filter_bestelbusjes))
            menu.add_item("Toon Beschikbaar", lambda: self._switch_scribe(voertuigen, filter_beschikbare_wagens))
            menu.add_item("Gebruikt door Vrouwen", lambda: self._switch_scribe(voertuigen, UIDFilter(uidmacro())))
            menu.add_item("Stel prijsplafond in", lambda: self.state.enter_request())
        elif self.state.active_scribe == reserveringen:
            menu.add_separator("Maak Reserveringen")
            menu.add_item("Maak Reservering", lambda: self._create_from_menu(reserveringen, Reservering))
            menu.add_separator("Toon Reserveringen")
            menu.add_item("Toon Alle", lambda: self._switch_scribe(reserveringen))
            menu.add_item("Toon Particulier", lambda: self._switch_scribe(reserveringen, filter_particuliere_klanten))
            menu.add_item("Toon Zakelijk", lambda: self._switch_scribe(reserveringen, filter_zakelijke_klanten))
            menu.add_item("Toon vanaf 4d", lambda: self._switch_scribe(reserveringen, filter_reserveringen_op_duurtijd))
            menu.add_item("Toon September", lambda: self._switch_scribe(reserveringen, filter_september))
            menu.add_item("Toon Oktober", lambda: self._switch_scribe(reserveringen, filter_oktober))
            menu.add_item("Toon November", lambda: self._switch_scribe(reserveringen, filter_november))
            menu.add_separator("Statistieken")
            menu.add_item("Statistieken per Maand", lambda: self._log_reservatie_statistieken_maand())
            menu.add_item("Statistieken per Ktype", lambda: self._log_reservatie_statistieken_type())
        elif self.state.active_scribe == facturen:
            menu.add_separator("Maak Facturen")
            menu.add_item("Maak Factuur", lambda: self._create_from_menu(facturen, Factuur))
            menu.add_separator("Toon Facturen")
            menu.add_item("Toon Alle", lambda: self._switch_scribe(facturen))
            menu.add_item("Toon Zakelijk", lambda: self._switch_scribe(facturen, filter_zakelijke_klanten))
        menu.add_separator("Ander Menu")
        if self.state.active_scribe != klanten:
            menu.add_item("Klanten", lambda: self._switch_scribe(klanten, browse=False))
        if self.state.active_scribe != voertuigen:
            menu.add_item("Voertuigen", lambda: self._switch_scribe(voertuigen, browse=False))
        if self.state.active_scribe != reserveringen:
            menu.add_item("Reserveringen", lambda: self._switch_scribe(reserveringen, browse=False))
        if self.state.active_scribe != facturen:
            menu.add_item("Facturen", lambda: self._switch_scribe(facturen, browse=False))
            menu.add_item("Auto Inleveren", lambda: self._create_from_menu(facturen, Factuur))
        menu.add_separator("Systeem")
        menu.add_item("Laad Data", lambda: read_data())
        menu.add_item("Save Data", lambda: save_data())
        menu.add_item("Sluit Programma", lambda: self.exit())
        
        return menu
    
    def _req_prijs(self):
        self.cmd
        self.state.enter_request()

    def _switch_scribe(self, scribe: TypeScribe, filter=None, browse=True):
        """Switch to a different scribe"""
        self.state.active_scribe = scribe
        self.table.scribe = scribe
        self.cmd.scribe = scribe
        self.editor.scribe = scribe
        self.table.cursor_index = 0
        if filter:
            self.table.scribe.set_filter(filter)
        else:
            scribe.refresh(all=True)
        if browse:
            self.state.enter_browsing()
        self.menu = self._create_menu()
        self.add_log(f"Switched to {scribe.__class__.__name__.replace('Scribe', '')}")
    
    def _create_from_menu(self, scribe: TypeScribe, obj_type: type):
        """Switch to scribe and start creating an object"""
        # Switch scribe first
        self.state.active_scribe = scribe
        self.table.scribe = scribe
        self.cmd.scribe = scribe
        self.editor.scribe = scribe
        self.menu = self._create_menu()
        scribe.refresh(all=True)
        
        # Start creating
        try:
            self.editor.start_creating(obj_type)
            self.state.enter_creating(obj_type)
            self.cmd.clear()
            self.add_log(f"Creating new {obj_type.__name__}")
        except Exception as e:
            self.add_log(f"Error creating object: {e}")
            self.state.enter_browsing()

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
            elif self.state.mode == AppMode.SELECTING:
                self.editor.finish_field_edit()
                self.cmd.clear()
                self.editor.move_next()
            elif self.state.mode in (AppMode.EDITING, AppMode.CREATING):
                if self.editor.is_editing_field:
                    # Submitting field value
                    data = value if value else ""
                    if self.editor.validate_and_submit(data):
                        self.editor.finish_field_edit()
                        self.cmd.clear()
                        self.editor.move_next()
                        
                        # If finished all fields, finalize
                        if self.editor.field_idx >= len(self.editor.names):
                            self.state.enter_browsing()
                    else:
                        self.add_log(f"Invalid value for {self.editor.current_field_name}")
            elif self.state.mode == AppMode.REQUEST:
                assert self.state.return_mode is not None
                try:
                    if value is not None:
                        prijs = int(value)
                        self.state.exit_mode()
                        self.toon_dagprijs(prijs)
                except:
                    self.add_log(f"Invalid value for filter.")
            
            if self.layout:
                self.update_display()
        
        @self.cmd.on("accepted")
        def on_accept(value: str | None):
            if self.state.mode in (AppMode.EDITING, AppMode.CREATING):
                if self.editor.is_editing_field and value:
                    # TAB to accept suggestion and move to next
                    self.editor.validate_and_submit(value)
                    self.editor.finish_field_edit()
                    self.cmd.clear()
                    self.editor.move_next()
                    
                    if self.editor.field_idx >= len(self.editor.names):
                        self.state.enter_browsing()
            
            elif self.state.mode == AppMode.SELECTING:
                if self.editor.is_editing_field and value:
                    self.editor.finish_field_edit()
                    self.cmd.clear()
                    self.editor.move_next()
                    
            if self.layout:
                self.update_display()
    
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
    
    def toon_dagprijs(self, value):
        self._switch_scribe(voertuigen, RangeFilter('dagprijs', 0, value))
        self.cmd.clear()
            
    def _log_reservatie_statistieken_maand(self):
        """Add a log message"""
        reset_filter = reserveringen._active_filter
        reset_query = reserveringen._last_query
        reserveringen.refresh()
        reserveringen.set_filter(filter_september)
        aantal_september = reserveringen.count
        reserveringen.set_filter(filter_oktober)
        aantal_oktober = reserveringen.count
        reserveringen.set_filter(filter_november)
        aantal_november = reserveringen.count
        reserveringen._active_filter = reset_filter
        reserveringen._last_query = reset_query
        reserveringen.refresh(all=False)
        self.add_log(f"Aantal verhuringen per maand: September {aantal_september}, Oktober {aantal_oktober}, November {aantal_november}")

    def _log_reservatie_statistieken_type(self):
        """Add a log message"""
        reset_filter = reserveringen._active_filter
        reset_query = reserveringen._last_query
        reserveringen.refresh()
        reserveringen.set_filter(filter_particuliere_klanten)
        aantal_particulier = reserveringen.count
        reserveringen.set_filter(filter_zakelijke_klanten)
        aantal_zakelijk = reserveringen.count
        reserveringen._active_filter = reset_filter
        reserveringen._last_query = reset_query
        reserveringen.refresh(all=False)
        self.add_log(f"Aantal verhuringen Particulier/Zakelijke: Particulier {aantal_particulier}, Zakelijk {aantal_zakelijk}")
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
        
        sidepanel_size = 30 if self.state.sidepanel_open else 3
        layout["body"].split_row(
            Layout(name="sidepanel", size=sidepanel_size),
            Layout(name="datatable", ratio=1),
        )
        
        return layout
    
    def update_display(self):
        """Update all layout components"""
        if not self.layout:
            return
        
        sidepanel_size = 30 if self.state.sidepanel_open else 3
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
    
    def header(self) -> Panel:
        """Create header panel"""
        grid = Table.grid(expand=True)
        grid.add_column(justify="left", ratio=1)
        grid.add_column(justify="right")
        
        header_text = Text()
        header_text.append(f"{self.title}", style="bold bright_black")
        
        # Add mode indicator
        mode_name = self.state.mode.name.title()
        header_text.append(f" — {mode_name}", style="bold white")
        
        # Add scribe name
        scribe_name = self.state.active_scribe.__class__.__name__.replace("Scribe", "")
        header_text.append(f" — {scribe_name.capitalize()}", style="bold bright_black")
        
        grid.add_row(
            header_text,
            Text(datetime.now().strftime("%H:%M:%S"), style="bright_black"),
        )
        return Panel(grid, style="bright_black", box=SIMPLE)
    
    def sidepanel(self) -> Panel:
        """Create sidepanel content"""
        if not self.state.sidepanel_open:
            return Panel("", box=SQUARE, border_style='bright_black')
        
        if self.state.mode == AppMode.EDITING:
            return self.editor.compose("Edit")
        elif self.state.mode == AppMode.CREATING:
            return self.editor.compose("Create")
        
        if self.state.mode == AppMode.EDITING:
            return self.editor.compose("Edit")
        elif self.state.mode == AppMode.CREATING:
            return self.editor.compose("Create")
        elif self.state.mode in (AppMode.MENU, AppMode.REQUEST):
            return self.menu.compose()
    
        return Panel("", box=SQUARE, border_style='bright_black')
    
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
            if self.editor.is_editing_field:
                # Show current value when editing
                placeholder = self.editor.current_value
                if hasattr(self.editor.current_value, 'uid'):
                    placeholder = getattr(self.editor.current_value, 'uid')
                placeholder = str(placeholder)
            else:
                placeholder = f"[{self.editor.current_field_name}] Press ENTER to edit"
        elif self.state.mode == AppMode.REQUEST:
            placeholder = f"Voer dagprijs in:"
        focus = self.state.is_input_focused or self.editor.is_editing_field
        return self.cmd.compose(focused=focus, placeholder=placeholder)
    
    def footer(self) -> Text:
        """Create footer with keybindings"""
        footer = Text(justify="center")
        
        bindings = ModeKeyBindings.get_bindings(AppMode.SEARCHING) if self.editor.is_editing_field else ModeKeyBindings.get_bindings(self.state.mode)
        
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
            elif self.state.mode in (AppMode.SEARCHING, AppMode.REQUEST):
                self._handle_input_keys(key, event)
            elif self.state.mode in (AppMode.EDITING, AppMode.CREATING):
                self._handle_editing_keys(key, event)
            elif self.state.mode == AppMode.SELECTING:
                self._handle_selecting_keys(key, event)
            elif self.state.mode == AppMode.MENU:
                self._handle_menu_keys(key)
            
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
        elif self.state.mode in (AppMode.EDITING, AppMode.CREATING) and self.editor.is_editing_field:
            self.editor.finish_field_edit()
            self.cmd.clear()
            self.editor.move_next()
        elif self.state.mode in (AppMode.EDITING, AppMode.CREATING) and not self.editor.is_editing_field:
            self.state.exit_mode()
            if self.state.mode == AppMode.MENU:
                self.state.enter_menu()
            self.cmd.clear()
            self.editor.finish_obj_edit()
        elif self.state.mode == AppMode.BROWSING:
            self.state.enter_menu()
        elif self.state.mode == AppMode.REQUEST:
            assert self.state.return_mode is not None
            self.state.mode = self.state.return_mode
            self.cmd.clear()
        else:
            self.state.enter_browsing()
            self.cmd.clear()
    
    def _handle_browsing_keys(self, key: str):
        """Handle keys in browsing mode"""
        if key == 'f':
            self.state.mode = AppMode.SEARCHING
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
                self.add_log(f"Creating new {obj_type.__name__}")
        elif key == 'd':
                obj = self.table.get_selected()
                self.add_log(f"Deleting {obj.uid}")
                self.table.delete_selected()
                self.update_display()
        elif key == 'm':
            # Open menu
            self.state.enter_menu()
            self.menu.selected_idx = 0

    def _handle_menu_keys(self, key: str):
        """Handle keys in menu mode"""
        if key == 'j' or key == 'down':
            self.menu.move_down()
        elif key == 'k' or key == 'up':
            self.menu.move_up()
        elif key == 'enter':
            # Execute selected menu item
            self.menu.execute_selected()
        elif key == 'f':
            # Execute selected menu item
            self.state.enter_browsing()
            self.state.mode = AppMode.SEARCHING
        elif key == 'tab':
            # Execute selected menu item
            self.state.enter_browsing()

    def _handle_input_keys(self, key: str, event: keyboard.KeyboardEvent):
        """Handle keys in searching mode"""
        if key in ('enter', 'tab', 'backspace', 'space') or len(key) == 1:
            self.cmd.key_event(event)
    
    def _handle_editing_keys(self, key: str, event: keyboard.KeyboardEvent):
        """Handle keys in editing/creating mode"""
        if self.editor.is_editing_field:
            # When editing a field, pass keys to command field
            if key in ('enter', 'tab', 'backspace', 'space') or len(key) == 1:
                self.cmd.key_event(event)
        else:
            # When navigating fields in sidepanel
            if key == 'j' or key == 'down':
                self.editor.move_next()
            elif key == 'k' or key == 'up':
                self.editor.move_prev()
            elif (key == 'e' or key == 'enter') and not self.editor.needs_selection() :
                # Start editing current field
                if not self.editor.is_editing_field:
                    self.editor.start_field_edit()
                self.cmd.clear()
            elif (key == 'h' or key == 'left') and self.editor.can_change_type():
                # Change type left
                self.editor.change_type(-1)
            elif (key == 'l' or key == 'right') and self.editor.can_change_type():
                # Change type right
                self.editor.change_type(1)
            elif (key == 'e' or key == 'enter') and self.editor.needs_selection():
                # Enter selection mode
                field_name = self.editor.current_field_name
                if field_name == 'klant':
                    self.state.enter_selecting('klant', klanten, self.state.mode)
                    self.selection_table = DataTable(self.console, klanten)
                    klanten.refresh(all=True)
                elif field_name == 'voertuig':
                    self.state.enter_selecting('voertuig', voertuigen, self.state.mode)
                    self.selection_table = DataTable(self.console, voertuigen)
                    voertuigen.set_filter(AttributeFilter('beschikbaar', True))
                    voertuigen.refresh(all=False)
                elif field_name == 'reservering':
                    self.state.enter_selecting('reservering', reserveringen, self.state.mode)
                    self.selection_table = DataTable(self.console, reserveringen)
                    reserveringen.set_filter(AttributeFilter('ingeleverd', False))
                    reserveringen.refresh(all=False)
                self.cmd.clear()
    
    def _handle_selecting_keys(self, key: str, event: keyboard.KeyboardEvent):
        """Handle keys in selecting mode"""
        if not self.selection_table:
            return
        
        if self.editor.is_editing_field:
            # When editing a field, pass keys to command field
            if key in ('enter', 'tab', 'backspace', 'space') or len(key) == 1:
                self.cmd.key_event(event)
        else:
            if key == 's' or key == 'enter':
                # Select current item
                selected = self.selection_table.get_selected()
                if selected and self.state.selecting_for:
                    self.editor.validate_and_submit(selected)
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
                self.editor.start_field_edit()

    def _get_create_type(self) -> type | None:
        """Determine what type to create based on active scribe"""
        if self.state.active_scribe is klanten:
            # Could prompt for Particulier vs Professioneel
            return Particulier
        elif self.state.active_scribe is voertuigen:
            return Voertuig
        elif self.state.active_scribe is reserveringen:
            return Reservering
        elif self.state.active_scribe is facturen:
            return Factuur
        return None
    
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

    def exit(self):
        self.running = False

if __name__ == "__main__":
    terminal = None
    while terminal is None:
        terminal = gw.getActiveWindow()
    if terminal:
        app = TerminalApp(terminal, klanten)
        app.run()