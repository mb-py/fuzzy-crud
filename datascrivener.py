"""
THE SCOPE CREEP IS REAL
"""
from datamodel import Klant, Particulier, Professioneel, Voertuig, Reservering, RESERVATIE_NUMMER, BTW, RRN, VIN, Bouwjaar
from abc import ABC, abstractmethod
from typing import Any, get_type_hints, cast
from datetime import date
from rapidfuzz import process, fuzz, utils
import string
import weakref
from collections.abc import Iterator
from dataclasses import fields, MISSING, asdict

class Fuzzable[T]:
    """
    Wrapper that encapsulates scoring logic,  and matching string.
    Responsibility for 'fuzzy matching' and 'comparison' lies here.
    """
    def __init__(self, obj: T, *searchable_attributes: str):
        self._obj_ref = weakref.ref(obj)
        self._search_cache: tuple[str, ...]
        self.match: str | None = None
        self.score: float = -1

        self.refresh_cache(*searchable_attributes)

    @property
    def obj(self) -> T:
        if self._obj_ref() is None:
            raise RuntimeError("Fuzzable accessed after underlying object was collected.")
        # Dereference: returns the object if it exists
        return cast(T, self._obj_ref())

    def refresh_cache(self, *args):
        """Rebuilds the strings used for fuzzy matching."""
        self._search_cache = tuple(str(getattr(self.obj, attr, None)) for attr in args if getattr(self.obj, attr, None) is not None)
        self.match = None

    def fuzz(self, query: str) -> float:
        """
        Calculate the normalized edit distance of all searchable values.
        Extracts the best match in a list of choices.
        """
        minimum=40 + min(30, 6*len(query))
        fuzzed = process.extractOne(query, choices=self._search_cache, scorer=fuzz.WRatio, score_cutoff=minimum, processor=utils.default_process)
        self.match, self.score = fuzzed[:2] if fuzzed else (None, 0)
        return self.score

    def __gt__(self, other: 'Fuzzable'):
        return self.score > other.score
    
    def __lt__(self, other: 'Fuzzable'):
        return self.score < other.score

class TypeScribe[T](ABC):
    """
    For when global lists aren't powerful enough. ୧(๑•̀ᗝ•́)૭
    Keeps all my objects safe and only lets others peek from a window.
    """
    def __init__(self, *objects: T):
        self._objects: list[T] = []
        self._window: list[Fuzzable[T]] = []
        self._hidden: list[Fuzzable[T]] = []
        self._current_type: str | None = None
        self._last_query: str = ""

        for obj in objects:
            self.add(obj)

    @property
    def all(self) -> list[T]:
        """Return all managed objects."""
        return self._objects

    @property
    def view(self) -> list[T]:
        """Returns the objects in the window."""
        return [fuzzable.obj for fuzzable in self._window[:]]
    
    @property
    def count(self) -> int:
        """Return the total number of objects in the current view."""
        return len(self._window)
 
    @property
    def map(self) -> dict[str, T]:
        """Note: Objects T must implement a .uid property."""
        return {getattr(obj, 'uid'): obj for obj in self._objects}

    @property
    @abstractmethod
    def searchable_attrributes(self) -> tuple[str,...]:
        """Returns a list of usuable attribute names for a fuzzeable object."""
        pass

    #LIST DUNDERS
    def __getitem__(self, index: int) -> T:
        """
        I'm a list. I am speed. (و •̀ ᴗ•́ )و
        Indexing on view respects active data views, filters, and sorts.
        """
        return self._window[index].obj

    def __len__(self) -> int:
        return len(self._window)

    def __iter__(self):
        # This yields the actual dataclasses during iteration
        for fuzzable in self._window:
            yield fuzzable.obj

    def clear(self) -> None:
        self._objects.clear()
        self._window.clear()
        self._hidden.clear()
        self._last_query = ""
    
    #CREATE
    def _hydrate(self, data: dict[str, Any], key: str, lookup: dict[str, T]) -> None:
        """Lookup and replaces a UID string in a dictionary with a object."""
        val = data.get(key)
        if isinstance(val, str) and val in lookup:
            data[key] = lookup[val]

    def add(self, obj: T) -> None:
        self._objects.append(obj)
        self._add_fuzzable(obj)

    def _add_fuzzable(self, obj: T):
        fuzzable = Fuzzable(obj, *self.searchable_attrributes)
        self._window.append(fuzzable)
        weakref.finalize(obj, TypeScribe._remove_fuzzable, fuzzable, self._window, self._hidden)

    #REMOVE
    @staticmethod
    def _remove_fuzzable(fuzzable: Fuzzable, *lists: list[Fuzzable]):
        for l in lists:
            try:
                l.remove(fuzzable)
            except ValueError:
                pass

    #CONSTRUCT
    @abstractmethod
    def from_array(self, data_list: list[dict[str, Any]], *maps: dict[str, Any]) -> None:
        """
        Instantiate objects from a json array or list of dictionaries. Objects might need maps from other scribes.
        [T].from_dict(d) for d in list 
        """
        pass

    def refresh(self, all=True) -> None:
        """Reset the search state and populate the current view heap."""
        self._window.clear()
        self._hidden.clear()
        if all:
            self._last_query = ""
            self._current_type = None
            self._window = [Fuzzable(obj, *self.searchable_attrributes) for obj in self._objects]
        if not all:
            collection = [obj for obj in self._objects if self._issubtype(obj)] if self._current_type else self._objects
            self._window = [Fuzzable(obj, *self.searchable_attrributes) for obj in collection]
            query = self._last_query.strip(string.punctuation)
            if query:
                self.run_query(query)
                
    @abstractmethod
    def _issubtype(self, obj: T) -> bool:
        """Checks if an object's class name or specific attribute matches a set category."""
        pass

    @abstractmethod
    def get_subtypes(self) -> list[str | None]:
        """Returns a list of type names or attribute values used as categories in this scribe."""
        return [None]

    def set_subtype(self, filter: str | None = None):
        """Sets a type name or attribue value of a category of objects in this scribe."""
        self._current_type = filter
        self.refresh(all=False)
        
    def run_query(self, query: str, sort=True) -> None:
        """Processes a fuzzy query, updates the internal _current_view heap"""
        query = query.strip(string.punctuation)
        #! if backspace
        if query < self._last_query:
             #Recover from _hidden (LIFO)
            last_word = query.split(" ")[-1]
            while self._hidden:
                item = self._hidden.pop()
                if not query or item.fuzz(last_word) > 0:
                    self._window.append(item)
                else:
                    self._hidden.append(item)
                    break
        elif query: #!null queries will not fuzz
            for word in query.split(" "):
                #Prune
                i = 0
                while i < len(self._window):
                    item = self._window[i]
                    if item.fuzz(word) > 0:
                        i += 1
                    else:
                        self._hidden.append(item)
                        self._window.remove(item)
        if sort:
            self._window = sorted(self._window, key=lambda x: x.score, reverse=True)
        #! record last query
        self._last_query = query

    def get_suggestion(self, query: str) -> str | None:
        """Performs a query on the current view and returns the best matching the attribute value."""
        query = query.strip('.- ')
        self.run_query(query, sort=True)
        # get suggestion from top of the heap
        suggestion = self._window[0].match if self._window else None
        # formatting fix
        if suggestion:
            s_words = suggestion.split(" ")
            q_words = query.split(" ")
            if len(q_words)>len(s_words):
                q_words[-1] = s_words[-1]
                return " ".join(q_words)
            return suggestion
        return None

    #TABULATE
    @abstractmethod
    def get_columns(self) -> tuple[str,...]:
        """Converts the object into a list of strings for display in a DataTable."""
        pass

    def get_rows(self, start: int | None = None, end: int | None = None) -> Iterator[list[str]]:
        """
        Formats and yields rows that are actually requested.
        """
        for fuzzable in self._window[start:end]:
            yield self._format_row(fuzzable.obj)

    @abstractmethod
    def _format_row(self, obj: T) -> list[str]:
        """Transform the dataclass object into a list of strings for a table."""
        pass

    # UPDATE
    @abstractmethod
    def update(self, obj: T | int, attr: str, value: Any) -> bool:
        '''
        Updates object. Returns boolean for validation.
        '''
        pass

    #CREATE
    def create_default(self, obj_type: type) -> dict[str, Any]:
        """
        Create a dictionary of default values for creating a new object.
        Returns a dict with field names as keys and default values.
        """
        defaults = {}
        
        for f in fields(obj_type):
            if f.name == 'nummer':  # Skip auto-generated fields
                continue
            
            # Get default value
            if f.default is not MISSING:
                defaults[f.name] = f.default
            elif f.default_factory is not MISSING:
                try:
                    defaults[f.name] = f.default_factory()
                except:
                    defaults[f.name] = None
            else:
                # Type-based defaults
                if f.type is bool:
                    defaults[f.name] = False
                elif f.type is int:
                    defaults[f.name] = 0
                elif f.type is float:
                    defaults[f.name] = 0.0
                elif f.type is str:
                    defaults[f.name] = ""
                elif f.type is date:
                    defaults[f.name] = date.today()
                else:
                    defaults[f.name] = None
        
        return defaults
        

class KlantScribe(TypeScribe[Klant]):
    """Scribe for managing Klanten (Particulier/Professioneel)."""
   
    @property
    def searchable_attrributes(self) -> tuple[str,...]:
        return 'uid', 'naam', 'postcode', 'gemeente'

    def from_array(self, data_list: list[dict[str, Any]], *maps: dict[str, Any]) -> None:
        """Accepts a flat list of dictionaries representing Klant objects."""
        for entry in data_list:
            if 'btwnummer' in entry:
                self.add(Professioneel.from_dict(entry))
            else:
                self.add(Particulier.from_dict(entry))
 
    def get_subtypes(self) -> list[str | None]:
        return [None, "Particulier", "Professioneel"]
    
    def _issubtype(self, obj) -> bool:
        if self._current_type is None:
            return True
        return obj.__class__.__name__ == self._current_type

    def get_columns(self) -> tuple[str,...]:
        return "BTW/RRN", "Naam", "Straat", "Huisnummer", "Postcode", "Gemeente"
    
    def _format_row(self, obj: Klant) -> list[str]:
        return [obj.uid, 
                obj.naam,
                obj.straat,
                f"{obj.huisnummer}",
                f"{obj.postcode}",
                obj.gemeente]
    
    def update(self, obj: Klant | int, attr: str, value: Any) -> bool:
        if isinstance(obj, int) and obj >= self.count:
            raise IndexError("Index out of range")
        elif isinstance(obj, int):
            obj = self[obj]
        if not hasattr(obj, attr):
            raise ValueError(f"Failed to find attribute {attr}")
        assert isinstance(obj, (Particulier, Professioneel))
        try:
            if attr in ['huisnummer', 'postcode']:
                value = int(value)
            if attr == 'rijksregisternummer':
                assert isinstance(obj, Particulier)
                value = RRN(value) if RRN.isvalid(value) else RRN('',obj.geboortedatum,obj.geslacht=="M")
            if attr == 'btwnummer':
                assert isinstance(obj, Professioneel)
                value = BTW(value) if BTW.isvalid(value) else BTW('')
            if attr == 'geboortedatum':
                value = date.fromisoformat(value)
            setattr(obj, attr, value)
            return True
        except Exception as e:
            raise ValueError(f"Failed to set attribute: {e}")

class VoertuigScribe(TypeScribe[Voertuig]):
    """Scribe for managing Voertuigen."""

    @property
    def searchable_attrributes(self) -> tuple[str,...]:
        return 'chassisnummer', 'merk', 'model', 'bouwjaar', 'soort', 'status'
    
    def from_array(self, data_list: list[dict[str, Any]], *maps: dict[str, Any]) -> None:
        for entry in data_list:
            self.add(Voertuig.from_dict(entry))
            

    def get_subtypes(self) -> list[str | None]:
        return [None, "Personenwagens", "Bestelbusjes", "Beschikbaar", "Gereserveerd"]
    
    def _issubtype(self, obj: Voertuig) -> bool:
        if self._current_type is None:
            return True
        return obj.status.capitalize() == self._current_type or obj.soort.capitalize() in self._current_type
    
    def get_columns(self) -> tuple[str,...]:
        return "VIN", "Merk", "Model", "Bouwjaar", "Prijs", "Status"
    
    def _format_row(self, obj: Voertuig) -> list[str]:
        return [obj.chassisnummer, 
                obj.merk, obj.model, 
                str(obj.bouwjaar),
                f"€{obj.dagprijs}", 
                obj.status.capitalize()]
    
    def update(self, obj: Voertuig | int, attr: str, value: Any) -> bool:
        """Update a field with validation"""
        if isinstance(obj, int) and obj < self.count:
            obj = self[obj]
        elif isinstance(obj, int):
            raise IndexError("Index out of range")
                
        attr_type = get_type_hints(type(obj)).get(attr)
        if attr_type is None:
            raise ValueError(f"Attribute '{attr}' not found")
        
        # Type conversion
        if not isinstance(value, attr_type):
            try:
                if attr_type is bool:
                    if isinstance(value, str):
                        value = value.lower() in ('true', '1', 'yes')
                elif issubclass(attr_type, (float, VIN, Bouwjaar)):
                    value = attr_type(value)
            except (ValueError, TypeError):
                raise ValueError(f"Cannot convert to {attr_type.__name__}")
        
        try:
            setattr(obj, attr, value)
            # Update availability cache
            self.refresh(all=False)
            return True
        except Exception as e:
            raise ValueError(f"Failed to set attribute: {e}")

class ReserveringScribe(TypeScribe[Reservering]):
    """Scribe for managing Reserveringen with dependency mapping."""
    
    @property
    def searchable_attrributes(self) -> tuple[str,...]:
        return 'nummer', 'strfklant', 'strfmodel', 'strfmerk', 'strstatus'
    
    def from_array(self, data_list: list[dict[str, Any]], *maps: dict[str, Any]) -> None:
        map_klanten = next((m for m in maps if m and isinstance(next(iter(m.values())), Klant)), {})
        map_voertuigen = next((m for m in maps if m and isinstance(next(iter(m.values())), Voertuig)), {})

        prefix_today = date.today().strftime("%y%m%d")
        max_num = 0

        for dry in data_list:
            # Hydrate the dictionary locally with objects before passing to the model
            moist = dry.copy()
            self._hydrate(moist, 'klant', map_klanten)
            self._hydrate(moist, 'voertuig', map_voertuigen)

            reservatie = Reservering.from_dict(moist)
            self.add(reservatie)
            if reservatie.nummer.startswith(prefix_today):
                res_num = int(reservatie.nummer[-3:])
                max_num = max(max_num, res_num)
        #synchronise generator
        for _ in range(max_num):
            next(RESERVATIE_NUMMER)
            
    def get_subtypes(self) -> list[str | None]:
        return [None, "Ingeleverd", "Lopend", "Particulier", "Professioneel"] 
    
    def _issubtype(self, obj) -> bool:
        if self._current_type is None:
            return True
        return obj.status.capitalize() == self._current_type or obj.klant.__class__.__name__ == self._current_type

    def get_columns(self) -> tuple[str, ...]:
        return "Nummer", "Klant", "Merk", "Model", "Van", "Tot", "Status"
    
    def _format_row(self, obj: Reservering) -> list[str]:
        return [obj.nummer, 
                obj.strfklant, 
                obj.strfmerk, 
                obj.strfmodel, 
                str(obj.van), 
                str(obj.tot), 
                obj.status.capitalize()]
    
    def update(self, obj: Reservering | int, attr: str, value: Any) -> bool:
        """Update a field with validation"""
        if isinstance(obj, int) and obj < self.count:
            obj = self[obj]
        elif isinstance(obj, int):
            raise IndexError("Index out of range")
        
        from typing import get_type_hints
        from datetime import date
        
        attr_type = get_type_hints(type(obj)).get(attr)
        if attr_type is None:
            raise ValueError(f"Attribute '{attr}' not found")
        
        # Special handling for date fields
        if attr in ('van', 'tot') or 'date' in str(attr_type):
            if isinstance(value, str):
                try:
                    value = date.fromisoformat(value)
                except ValueError:
                    raise ValueError(f"Invalid date format. Use YYYY-MM-DD")
        
        # Validate date logic
        if attr == 'van' and hasattr(obj, 'tot'):
            if isinstance(value, date) and value > obj.tot:
                raise ValueError("Start date cannot be after end date")
        elif attr == 'tot' and hasattr(obj, 'van'):
            if isinstance(value, date) and value < obj.van:
                raise ValueError("End date cannot be before start date")
        
        try:
            setattr(obj, attr, value)
            self.refresh(all=False)
            return True
        except Exception as e:
            raise ValueError(f"Failed to set attribute: {e}")