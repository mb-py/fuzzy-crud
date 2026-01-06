import time
from datetime import datetime, date
from typing import List, Callable, Any
from dataclasses import fields, MISSING

from rich.console import Console, Group, group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.box import ROUNDED
from rich.rule import Rule

import keyboard
from typing import Literal
from datascrivener import TypeScribe
from datamodel import BTW, RRN, VIN

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
        table = Table(expand=True, box=ROUNDED, border_style=table_style)
        # --- Table Size and Scrolling Parameters---
        table_max_size = self.console.size.height -19
        table_max_depth = self.scribe.count - 1 if self.scribe.count else 0
        cursor_max_depth = table_max_size if table_max_size > table_max_depth else table_max_size//2
        start_idx, end_idx = 0, 0
        # --- Columns ---
        all_cols = self.scribe.get_columns()
        for col in all_cols:
            width = 1 if col in ["Geslacht", "Huisnummer"] else 2 if col in ["Bouwjaar", "Prijs", "Postcode"] else 3 if col in ["BTW/RRN", "Gemeente", "Straat", "Merk", "Van", "Tot"] else 4
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

        title_text = f"[b {title_style}]DATATABLE[/] ({self.scribe.count})"
        if title_suffix:
            title_text += f" - {title_suffix}"
        
        return Panel(table, title=title_text, border_style=panel_style, box=ROUNDED)
    
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
    
    def start_editing(self, index: int):
        """Initialize editor for editing an existing object"""
        self.is_creating = False
        self.obj = self.scribe[index]
        self._initialize_fields()
    
    def start_creating(self, obj_type: type):
        """Initialize editor for creating a new object"""
        self.is_creating = True
        self.obj_type = obj_type
        self.obj = None
        self.names.clear()
        self.types.clear()
        self.values.clear()
        self.errors.clear()
        self.object_refs.clear()
        
        # Get default values from dataclass fields
        for f in fields(obj_type):
            if f.name == 'nummer':  # Skip auto-generated fields
                continue
            self.names.append(f.name)
            self.types.append(f.type)
            
            # Get default value
            if f.default is not MISSING:
                self.values.append(f.default)
            elif f.default_factory is not MISSING:
                self.values.append("")
            else:
                self.values.append("")
        
        self.field_idx = 0
    
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
    
    def move_prev(self):
        """Move to previous field"""
        max_index = len(self.names)
        self.field_idx = (self.field_idx - 1 ) % max_index
    
    def validate_and_submit(self, data: str) -> bool:
        """Validate and submit data for current field. Returns True if valid."""
        idx = self.field_idx
        if idx >= len(self.names):
            return False
        
        field_type = self.types[idx]
        field_name = self.names[idx]
        
        try:
            if not self.is_creating:
                self.scribe.update(self.obj, field_name, data)
                # Get the updated value back
                updated_value = getattr(self.obj, field_name)
                self.values[idx] = updated_value
            else:
                self.values[idx] = data
            self.errors[idx] = ""
            return True
            
        except (ValueError, TypeError) as e:
            # Store error
            self.errors[idx] = f"Invalid {field_type.__name__} : {e}"
            if data:
                self.values[idx] = data
            return False
    
    def _convert_value(self, value: str, target_type: type) -> Any:
        """Convert string value to target type with validation"""
        if target_type.__name__ in ['BTW', 'RRN', 'VIN', 'str']:
            return target_type(value)
        
        if not value:
            return None
        
        # Handle date types
        if target_type is date or 'date' in str(target_type):
            return date.fromisoformat(value)
        
        # Handle bool
        if target_type is bool:
            if value not in ['True', 'False']:
                raise ValueError("Must be True or False")
            return value == 'True'
        
        # Handle numeric types
        if target_type in (int, float):
            return target_type(value)
        
        # Default: keep as string
        return value
    
    def set_field_value(self, field_name: str, value: Any):
        """Directly set a field value (for object selection)"""
        idx = self.names.index(field_name)
        try:
            if not self.is_creating:
                # For editing, use scribe's update method with the actual object
                self.scribe.update(self.obj, field_name, value)
                self.values[idx] = value
            else:
                # For creating, store both the display value and object reference
                self.values[idx] = value
                self.object_refs[field_name] = value  # Store actual object for from_dict
            self.errors[idx] = ""
        except (ValueError, IndexError) as e:
            self.errors[idx] = str(e) if str(e) else "Error setting value"

    
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
                
                if hasattr(val, 'uid') and not self.is_creating:
                    display_text = f"{getattr(val, 'uid')}"
                else:
                    display_text = str(val) if val else "<empty>"

                #if name in ('klant', 'voertuig') and not self.is_creating:
                
                yield Text(f"{display_text}", style=selected)
                if err:
                    yield Text(f"⚠ {err}", style="red")
                yield Text("")
        
        obj_name = self.obj_type.__name__ if self.obj_type else "Object"
        return Panel(
            display_fields(), 
            title=f"[bold]{title} - {obj_name}[/]", 
            border_style="blue", 
            box=ROUNDED
        )