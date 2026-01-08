import time
from datetime import datetime, date
from typing import List, Callable, Any
from dataclasses import fields, MISSING

from rich.console import Console, Group, group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.box import ROUNDED, SIMPLE, SQUARE, MINIMAL
from rich.rule import Rule

import keyboard
from typing import Literal
from datascrivener import TypeScribe
from datamodel import Particulier, Professioneel, Voertuig, Reservering, Klant, VoertuigCategorie, BTW, RRN, VIN, Bouwjaar

EventTypes = Literal["changed", "submitted", "accepted"]

class commandField():
    def __init__(self, scribe: TypeScribe):
        self.scribe = scribe
        self._data: str | None = None
        self.suggestion_text: str | None = None
        self._subscribers: dict[str, list[Callable[[str | None], None]]] = {
                "changed": [],
                "submitted": [],
                "accepted": []
        }
    # Standard property logic
    @property
    def input_text(self) -> str:
        return self._data if self._data is not None else ""

    @input_text.setter
    def input_text(self, new_input: str):
        if self._data != new_input:
            self._data = new_input
            self._emit("changed")

    def _emit(self, event_name: EventTypes):
        """Internal helper to fire all callbacks for a specific channel."""
        for callback in self._subscribers.get(event_name, []):
            callback(self._data)

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
            self._emit("accepted")
        elif key == 'enter':
            self._emit("submitted")

    def clear(self):
        self.input_text = ""
        self.suggestion_text = ""
    
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

class DataTable():

    def __init__(self, console: Console, scribe: TypeScribe):
        self.console = console
        self.scribe = scribe
        self.cursor_index = 0        
        self._subscribers: dict[str, list[Callable[[str | None], None]]] = {
                "timeit": [],
                "submitted": [],
                "accessed": []
        }

    def get_selected(self) -> Any:
        """Get the currently selected object"""
        if 0 <= self.cursor_index < self.scribe.count:
            return self.scribe[self.cursor_index]
        return None

    def cursor_down(self):
        max_index = self.scribe.count - 1 if self.scribe.count > 0 else 0
        if self.cursor_index < max_index:
            self.cursor_index += 1

    def cursor_up(self):
        min_index = 0
        if self.cursor_index > min_index:
            self.cursor_index -= 1
        
    def compose(self, focused:bool, title_suffix: str = "") -> Panel:
        # --- Styling ---
        title_style = "white"  if focused else "bright_black"
        panel_style = "bright_black"
        table_style = "bright_black"
        # --- Table ---
        table = Table(expand=True, box=MINIMAL, border_style=table_style)
        # --- Table Size and Scrolling Parameters---
        table_max_size = self.console.size.height -19
        table_max_depth = self.scribe.count - 1 if self.scribe.count else 0
        cursor_max_depth = table_max_size if table_max_size > table_max_depth else table_max_size//2
        start_idx, end_idx = 0, 0
        # --- Columns ---
        all_cols = self.scribe.get_columns()
        for col in all_cols:
            width = 4
            if col in ["Geslacht", "Huisnummer"]:
                width = 1 
            if col in ["Bouwjaar", "Prijs", "Postcode", "Nummer"]:
                width = 2
            if col in ["BTW/RRN", "VIN", "Straat", "Merk", "Model", "Van", "Tot", "Status"]:
                width = 3
            if col in ["Klant"]:
                width = 5

            table.add_column(col, ratio=width, overflow="ellipsis")
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

        scribe_name = self.scribe.__class__.__name__.replace('Scribe', '')
        filtered = '(All)' if self.scribe._active_filter is None else '(Filtered)'
        hidden = len(self.scribe._hidden)
        stats = f"{self.scribe.count} ({hidden} hidden)" if hidden > 0 else f"{self.scribe.count}"
        title_text = f"[b {title_style}]{scribe_name}{filtered}[/]  - Showing {stats}"
        if title_suffix:
            title_text += f" - {title_suffix}"
        
        return Panel(table, title=title_text, border_style=panel_style, box=SQUARE)
    
class ObjectEditor():
    """Handles editing and creating objects with validation"""
    def __init__(self, scribe: TypeScribe):
        self.scribe = scribe
        self.obj: Any = None
        self.obj_type: type | None = None
        self.names: list[str] = []
        self.types: list[Any] = []
        self.values: list[Any] = []
        self.errors: list[str] = []  # Track validation errors
        self.object_refs: dict[str, Any] = {} 
        self.field_idx = 0
        self.is_creating = False
        self.is_editing_field = False
    
    def start_editing(self, index: int):
        """Initialize editor for editing an existing object"""
        self.is_creating = False
        self.is_editing_field = False
        self.obj = self.scribe[index]
        self._initialize_fields()
    
    def start_creating(self, obj_type: type):
        """Initialize editor by creating a new default object immediately"""
        self.is_creating = True
        self.is_editing_field = False
        self.obj_type = obj_type
        
        # Create the actual object
        # Add it to the scribe immediately
        try:
            self.obj = self.scribe.create_default(self.obj_type)
            assert self.obj is not None
            self._initialize_fields()
            self.field_idx = 0 
        except Exception as e:
            raise ValueError(f"Failed to create default object: {e}")
    
    def _initialize_fields(self):
        """Initialize fields from existing object"""
        if self.obj is None:
            return
        
        self.obj_type = self.obj.__class__
        assert self.obj_type is not None
        self.names.clear()
        self.types.clear()
        self.values.clear()
        self.errors.clear()
        
        for f in fields(self.obj):
            if f.name == 'nummer':  # Skip auto-generated
                continue
            val = getattr(self.obj, f.name)
            #strfval = str(val.uid if hasattr(val, 'uid') else val)
            self.names.append(f.name)
            self.types.append(f.type)
            self.values.append(val)
            self.errors.append("")
        
        self.field_idx = 0
    
    @property
    def current_field_name(self) -> str:
        """Get the name of the currently selected field"""
        if 0 <= self.field_idx < len(self.names):
            return self.names[self.field_idx]
        return ""
    
    @property
    def current_value(self) -> str:
        """Get the current value as string"""
        if 0 <= self.field_idx < len(self.values):
            return self.values[self.field_idx]
        return ""
    
    @property
    def current_type(self) -> type | None:
        """Get the type of the current field"""
        if 0 <= self.field_idx < len(self.values):
            return self.types[self.field_idx]
        return None
    
    def needs_selection(self) -> bool:
        """Check if current field needs object selection"""
        field_name = self.current_field_name
        return field_name in ('klant', 'voertuig')
    
    def move_next(self):
        """Move to next field"""
        max_index = len(self.names)
        self.field_idx = (self.field_idx + 1 ) % max_index
        self.is_editing_field = False
    
    def move_prev(self):
        """Move to previous field"""
        max_index = len(self.names)
        self.field_idx = (self.field_idx - 1 ) % max_index
        self.is_editing_field = False

    def start_field_edit(self):
        """Start editing the current field (will transfer focus to command field)"""
        self.is_editing_field = True
    
    def finish_field_edit(self):
        """Finish editing the current field"""
        self.is_editing_field = False
    
    def can_change_type(self) -> bool:
        """Check if the current object type can be changed (only during creation)"""
        if not self.is_creating:  # Can ONLY change type when creating
            return False
        # Can change between Particulier/Professioneel for Klanten
        if self.obj_type in (Particulier, Professioneel):
            return True
        return False
    
    def get_alternate_types(self) -> list[type]:
        """Get list of alternate types for current object"""
        if self.obj_type in (Particulier, Professioneel):
            return [Particulier, Professioneel]
        return []
    
    def change_type(self, direction: int):
        """Change object type (for creation only). Direction: -1 for left/h, +1 for right/l"""
        if not self.can_change_type():
            return
        
        alternates = self.get_alternate_types()
        if not alternates or self.obj_type not in alternates:
            return
        
        current_idx = alternates.index(self.obj_type)
        new_idx = (current_idx + direction) % len(alternates)
        new_type = alternates[new_idx]
        
        if new_type != self.obj_type:
            if self.obj is not None:
                self.scribe.remove(self.obj)
                self.scribe.refresh(all=False)
            try:
                self.obj = self.scribe.create_default(new_type)
                assert self.obj is not None
                self._initialize_fields()
                self.field_idx = 0 
            except Exception as e:
                # Failed to create new type
                self.obj = None
    
    def cancel_creation(self):
        """Remove the created object if canceling during creation"""
        if self.is_creating and self.obj is not None:
            self.scribe.remove(self.obj)
            self.scribe.refresh(all=False)
        self.is_creating = False
    
    def validate_and_submit(self, data: str) -> bool:
        """Validate and submit data for current field. Returns True if valid."""
        idx = self.field_idx
        if idx < 0 or idx >= len(self.names):
            return False
        field_name = self.names[idx]
        try:
            # Always use update method (same for creating and editing)
            self.scribe.update(self.obj, field_name, data)
            
            # Get the updated value back
            updated_value = getattr(self.obj, field_name)
            self.values[idx] = updated_value
            self.errors[idx] = ""
            return True
        except (ValueError, TypeError) as e:
            # Store error
            self.errors[idx] = str(e)
            if data:
                self.values[idx] = data
            return False
        
    def compose(self, title: str = "Edit") -> Panel:
        """Render the editor panel"""
        @group()
        def display_fields():     
            for i in range(len(self.names)):
                name = self.names[i]
                val = self.values[i]
                err = self.errors[i]
                
                # Color coding
                if err:
                    color = "bold red"
                else:
                    color = "bold white"
                
                selected = f"r {color}" if self.field_idx == i else color
                
                yield Rule(f"{name.replace('_', ' ').title()}", style="bold white")
                
                if hasattr(val, 'uid'):
                    display_text = f"{getattr(val, 'uid')}"
                else:
                    display_text = str(val) if val else "<empty/false>"

                #if name in ('klant', 'voertuig') and not self.is_creating:
                
                yield Text(f"{display_text}", style=selected)
                if err:
                    yield Text(f"⚠ {err}", style="red")
                yield Text("")
        
        obj_name = self.obj_type.__name__ if self.obj_type else "Object"

        return Panel(
            display_fields(), 
            title=f"[bold]{title} - {obj_name}[/]", 
            border_style="white", 
            box=SQUARE
        )
    
class MenuItem:
    """A menu item with action"""
    def __init__(self, label: str | None, action: Callable[[], None], is_separator: bool = False):
        self.label = label
        self.action = action
        self.is_separator = is_separator

class Menu:
    """Main menu component"""
    def __init__(self):
        self.items: list[MenuItem] = []
        self.selected_idx = 0
    
    def add_item(self, label: str, action: Callable[[], None]):
        """Add a menu item"""
        self.items.append(MenuItem(label, action))
    
    def add_separator(self, label: str | None = None):
        """Add a visual separator"""
        self.items.append(MenuItem(label, lambda: None, is_separator=True))
    
    def move_down(self):
        """Move selection down, skipping separators"""
        if self.selected_idx < len(self.items) - 1:
            self.selected_idx += 1
            # Skip separators
            while self.selected_idx < len(self.items) and self.items[self.selected_idx].is_separator:
                self.selected_idx += 1
    
    def move_up(self):
        """Move selection up, skipping separators"""
        if self.selected_idx > 0:
            self.selected_idx -= 1
            # Skip separators
            while self.selected_idx >= 0 and self.items[self.selected_idx].is_separator:
                self.selected_idx -= 1
    
    def execute_selected(self):
        """Execute the currently selected menu item"""
        if 0 <= self.selected_idx < len(self.items):
            item = self.items[self.selected_idx]
            if not item.is_separator:
                item.action()
    
    def compose(self) -> Panel:
        """Render the menu panel"""
        @group()
        def display_menu():
            for i, item in enumerate(self.items):
                if item.is_separator:
                    yield Text("")
                    if item.label:
                        yield Rule(title=item.label, style="white")
                    else:
                        yield Rule(style="white")
                else:
                    is_selected = (i == self.selected_idx)
                    style = "r bright_white" if is_selected else "white"
                    prefix = "► " if is_selected else "  "
                    yield Text(f"{prefix}{item.label}", style=style)
        
        border_style = "white"
        return Panel(
            display_menu(),
            title="",
            border_style=border_style,
            box=SQUARE
        )