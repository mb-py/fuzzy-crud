from enum import Enum, auto
from typing import Protocol, Any
from dataclasses import dataclass, field
from datascrivener import TypeScribe, ObjectFilter

class AppMode(Enum):
    """Application states with clear transitions"""
    BROWSING = auto()      # Viewing datatable, can navigate
    SEARCHING = auto()     # Input field focused for fuzzy search
    EDITING = auto()       # Editing an existing object
    CREATING = auto()      # Creating a new object
    SELECTING = auto()     # Selecting a related object (for Reservering)
    MENU = auto()          # Navigating main menu

@dataclass
class AppState:
    """Centralized application state"""
    mode: AppMode = AppMode.MENU
    
    # Data management
    active_scribe: TypeScribe | None = None
    
    # UI state
    sidepanel_open: bool = True
    menu_idx: int = 0
    
    # Editing/Creating state
    editing_index: int | None = None
    creating_type: type | None = None
    
    # Selection state (for Reservering dependencies)
    selecting_for: str | None = None  # 'klant' or 'voertuig'
    selection_scribe: TypeScribe | None = None
    selection_return_mode: AppMode | None = None
    
    def enter_browsing(self):
        """Transition to browsing mode"""
        self.mode = AppMode.BROWSING
        self.sidepanel_open = False
        self.editing_index = None
        self.creating_type = None
        self.selecting_for = None
        self.selection_scribe = None
        self.selection_return_mode = None
    
    def enter_editing(self, index: int):
        """Transition to editing mode"""
        self.mode = AppMode.EDITING
        self.editing_index = index
        self.sidepanel_open = True
    
    def enter_creating(self, obj_type: type):
        """Transition to creating mode"""
        self.mode = AppMode.CREATING
        self.creating_type = obj_type
        self.editing_index = None
        self.sidepanel_open = True
    
    def enter_selecting(self, field_name: str, scribe: TypeScribe, return_mode: AppMode):
        """Transition to selection mode"""
        self.selection_return_mode = return_mode
        self.mode = AppMode.SELECTING
        self.selecting_for = field_name
        self.selection_scribe = scribe
        self.sidepanel_open = False
    
    def exit_selecting(self):
        """Return from selection mode"""
        if self.selection_return_mode:
            self.mode = self.selection_return_mode
            self.sidepanel_open = True
        self.selecting_for = None
        self.selection_scribe = None
        self.selection_return_mode = None

    def enter_menu(self):
        """Transition to menu mode"""
        self.mode = AppMode.MENU
        self.sidepanel_open = True
        self.menu_idx = 0   

    @property
    def is_input_focused(self) -> bool:
        """Check if input field should be focused"""
        return self.mode == AppMode.SEARCHING
    
    @property
    def is_table_focused(self) -> bool:
        """Check if datatable should be focused"""
        return self.mode in (AppMode.BROWSING, AppMode.SELECTING)

    @property
    def is_sidepanel_focused(self) -> bool:
        """Check if sidepanel should be focused"""
        return self.mode in (AppMode.EDITING, AppMode.CREATING)

class KeyHandler(Protocol):
    """Protocol for keyboard event handlers"""
    def handle(self, key: str, state: AppState) -> bool:
        """Handle a key press. Return True if handled."""
        ...

@dataclass
class KeyBinding:
    """Maps keys to actions with descriptions"""
    key: str
    description: str
    handler: Any  # Callable

class ModeKeyBindings:
    """Keyboard bindings for each mode"""
    
    @staticmethod
    def get_bindings(mode: AppMode) -> list[KeyBinding]:
        """Get keyboard bindings for a specific mode"""
        if mode == AppMode.BROWSING:
            return [
                KeyBinding("m", "Menu", None),
                KeyBinding("f", "Fuzzy Find", None),
                KeyBinding("e", "Edit", None),
                KeyBinding("d", "Delete", None),
                KeyBinding("c", "Create", None),
                KeyBinding("j", "Cursor Down", None),
                KeyBinding("k", "Cursor Up", None),
            ]
        elif mode == AppMode.SEARCHING:
            return [
                KeyBinding("Enter", "Submit", None),
                KeyBinding("Tab", "Autocomplete", None),
                KeyBinding("Esc", "Cancel", None),
            ]
        elif mode == AppMode.EDITING:
            return [
                KeyBinding("e", "Edit Field", None),
                KeyBinding("j", "Cursor Down", None),
                KeyBinding("k", "Cursor Up", None),
                KeyBinding("l", "Change Type", None),
                KeyBinding("Esc", "Return", None),
            ]
        elif mode == AppMode.CREATING:
            return [
                KeyBinding("e", "Edit Field", None),
                KeyBinding("j", "Cursor Down", None),
                KeyBinding("k", "Cursor Up", None),
                KeyBinding("l", "Change Type", None),
                KeyBinding("Esc", "Return", None),
            ]
        elif mode == AppMode.SELECTING:
            return [
                KeyBinding("f", "Fuzzy Find", None),
                KeyBinding("s", "Select", None),
                KeyBinding("j", "Cursor Down", None),
                KeyBinding("k", "Cursor Up", None),
                KeyBinding("Esc", "Cancel", None),
            ]
        elif mode == AppMode.MENU:
            return [
                KeyBinding("f", "Fuzzy Find", None),
                KeyBinding("j", "Down", None),
                KeyBinding("k", "Up", None),
                KeyBinding("Enter", "Select", None),
                KeyBinding("Esc", "Close Menu", None),
            ]
        return []
