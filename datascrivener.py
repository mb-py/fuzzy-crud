"""
THE SCOPE CREEP IS REAL
"""
from datamodel import Klant, Particulier, Professioneel, Voertuig, Reservering, RESERVATIE_NUMMER, BTW, RRN, VIN, Bouwjaar
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Any, get_type_hints
from datetime import date
from rapidfuzz import process, fuzz, utils
from dataclasses import asdict
import string

T = TypeVar("T")

class Fuzzable(Generic[T]):
    """
    Wrapper that encapsulates scoring logic,  and matching string.
    Responsibility for 'fuzzy matching' and 'comparison' lies here.
    """
    def __init__(self, obj: T, *searchable_attributes: str):
        self.obj = obj
        self.attrs = searchable_attributes
        self.score: float = -1
        self.match: str | None = None

    def fuzz(self, query: str) -> float:
        """
        Calculate the normalized edit distance of all searchable values.
        Extracts the best match in a list of choices.
        """
        minimum=40 + min(30, 6*len(query))
        values = [str(getattr(self.obj, attr)) for attr in self.attrs]
        fuzzed = process.extractOne(query, choices=values, scorer=fuzz.WRatio, score_cutoff=minimum, processor=utils.default_process)
        self.match, self.score = fuzzed[:2] if fuzzed else (None, 0)
        return self.score

    def __gt__(self, other: 'Fuzzable'):
        return self.score > other.score
    
    def __lt__(self, other: 'Fuzzable'):
        return self.score < other.score

class TypeScribe(ABC, Generic[T]):
    """
    For when global lists aren't powerful enough. ୧(๑•̀ᗝ•́)૭
    """
    """You want to have list, I keep list. You want to read from list, I read from list. You want to a new list, I write list."""
    def __init__(self):
        self._objects: list[T] = []
        self._current_view: list[Fuzzable[T]] = []
        self._current_type: str | None = None
        self._hidden: list[Fuzzable[T]] = []
        self._last_query: str = ""

    @property
    def all(self) -> list[T]:
        """Return all managed objects."""
        return self._objects

    @property
    def view(self) -> list[T]:
        """Returns the objects in the current view."""
        return [item.obj for item in self._current_view]
    
    @property
    def count(self) -> int:
        """Return the total number of objects in the current view."""
        return len(self._current_view)
 
    @property
    def map(self) -> dict[str, T]:
        """Note: Objects T must implement a .uid property."""
        return {getattr(obj, 'uid'): obj for obj in self._objects}

    def clear(self) -> None:
        self._objects.clear()
        self._current_view.clear()
        self._hidden.clear()
        self._last_query = ""
    
    #CONSTRUCT
    def _hydrate(self, data: dict[str, Any], key: str, lookup: dict[str, T]) -> None:
        """Lookup and replaces a UID string in a dictionary with a object."""
        val = data.get(key)
        if isinstance(val, str) and val in lookup:
            data[key] = lookup[val]

    def add(self, obj: T) -> None:
        self._objects.append(obj)
        self._current_view.append(Fuzzable(obj, *self._set_searchable_attrributes(obj)))

    @abstractmethod
    def from_array(self, data_list: list[dict[str, Any]], *maps: dict[str, Any]) -> None:
        """
        Instantiate objects from a json array or list of dictionaries. Objects might need maps from other scribes.
        [T].from_dict(d) for d in list 
        """
        pass

    def refresh(self, all=True) -> None:
        """Reset the search state and populate the current view heap."""
        self._current_view.clear()
        self._hidden.clear()
        if all:
            self._last_query = ""
            self._current_type = None
            self._current_view = [Fuzzable(obj, *self._set_searchable_attrributes(obj)) for obj in self._objects]
        if not all:
            collection = [obj for obj in self._objects if self._issubtype(obj)] if self._current_type else self._objects
            self._current_view = [Fuzzable(obj, *self._set_searchable_attrributes(obj)) for obj in collection]
            query = self._last_query.strip(string.punctuation)
            if query:
                self.run_query(query)

    #VIEW
    def __getitem__(self, index: int) -> T:
        """
        I'm a list. I am speed. (و •̀ ᴗ•́ )و
        Indexing on view respects active data views, filters, and sorts.
        """
        return self._current_view[index].obj

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

    @abstractmethod
    def _set_searchable_attrributes(self, obj: T) -> tuple[str,...]:
        """Returns a list of attribute names from a fuzzeable object usuable for a search query."""
        pass

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
                    self._current_view.append(item)
                else:
                    self._hidden.append(item)
                    break
        elif query: #!null queries will not fuzz
            for word in query.split(" "):
                #Prune
                i = 0
                while i < len(self._current_view):
                    item = self._current_view[i]
                    if item.fuzz(word) > 0:
                        i += 1
                    else:
                        self._hidden.append(item)
                        self._current_view.remove(item)
        if sort:
            self._current_view = sorted(self._current_view, key=lambda x: x.score, reverse=True)
        #! record last query
        self._last_query = query

    def get_suggestion(self, query: str) -> str | None:
        """Performs a query on the current view and returns the best matching the attribute value."""
        query = query.strip('.- ')
        self.run_query(query, sort=True)
        # get suggestion from top of the heap
        suggestion = self._current_view[0].match if self._current_view else None
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

    @abstractmethod
    def get_rows(self) -> list[list[str]]:
        """Converts the object into a list of strings for display in a DataTable."""
        pass

    # UPDATE
    @abstractmethod
    def update(self, obj: T | int, attr: str, value: Any) -> bool:
        '''
        Updates object. Returns boolean for validation.
        '''
        pass
        

class KlantScribe(TypeScribe[Klant]):
    """Scribe for managing Klanten (Particulier/Professioneel)."""

    def from_array(self, data_list: list[dict[str, Any]], *maps: dict[str, Any]) -> None:
        """Accepts a flat list of dictionaries representing Klant objects."""
        for entry in data_list:
            if 'btwnummer' in entry:
                self.add(Professioneel.from_dict(entry))
            else:
                self.add(Particulier.from_dict(entry))
    
    def _set_searchable_attrributes(self, obj: Klant) -> tuple[str,...]:
        return 'uid', 'naam', 'postcode', 'gemeente'

    def get_subtypes(self) -> list[str | None]:
        return [None, "Particulier", "Professioneel"]
    
    def _issubtype(self, obj) -> bool:
        if self._current_type is None:
            return True
        return obj.__class__.__name__ == self._current_type

    def get_columns(self) -> tuple[str,...]:
        return "BTW/RRN", "Naam", "Straat", "Huisnummer", "Postcode", "Gemeente"
    
    def get_rows(self) -> list[list[str]]:
        table: list[list[str]] = []
        for obj in self.view:
            table.append([obj.uid, 
                          obj.naam, 
                          obj.straat, 
                          f"{obj.huisnummer}",
                          f"{obj.postcode}",
                          obj.gemeente])
        return table
    
    def update(self, obj: Klant | int, attr: str, value: Any) -> bool:
        if isinstance(obj, int) and obj < self.count:
            obj = self[obj]
        else:
            raise IndexError
        attr_type = get_type_hints(obj).get(attr)
        if attr_type is None:
            raise ValueError("attr not found")
        if issubclass(attr_type, (int, BTW, RRN)) and not isinstance(value, attr_type):
            value = attr_type(value)
        try:
            setattr(obj, attr, value)
            return True #success
        except:
            raise ValueError("incorrect value")

class VoertuigScribe(TypeScribe[Voertuig]):
    """Scribe for managing Voertuigen."""

    def from_array(self, data_list: list[dict[str, Any]], *maps: dict[str, Any]) -> None:
        for entry in data_list:
            self.add(Voertuig.from_dict(entry))
    
    def _set_searchable_attrributes(self, obj: Voertuig) -> tuple[str,...]:
        return 'chassisnummer', 'merk', 'model', 'bouwjaar', 'soort', 'status'

    def get_subtypes(self) -> list[str | None]:
        return [None, "Personenwagens", "Bestelbusjes", "Beschikbaar", "Gereserveerd"]
    
    def _issubtype(self, obj: Voertuig) -> bool:
        if self._current_type is None:
            return True
        return obj.status.capitalize() == self._current_type or obj.soort.capitalize() in self._current_type
    
    def get_columns(self) -> tuple[str,...]:
        return "VIN", "Merk", "Model", "Bouwjaar", "Prijs", "Status"
    
    def get_rows(self) -> list[list[str]]:
        table: list[list[str]] = []
        for obj in self.view:
            table.append([obj.chassisnummer, 
                          obj.merk, obj.model, 
                          str(obj.bouwjaar),
                          f"€{obj.dagprijs}", 
                          obj.status.capitalize()])
        return table
    
    def update(self, obj: Voertuig | int, attr: str, value: Any) -> bool:
        if isinstance(obj, int) and obj < self.count:
            obj = self[obj]
        else:
            raise IndexError
        attr_type = get_type_hints(obj).get(attr)
        if attr_type is None:
            raise ValueError("attr not found")
        if issubclass(attr_type, bool) and isinstance(value, str):
            value = bool(value.capitalize().strip() == "True")
        if issubclass(attr_type, (float, VIN, Bouwjaar)) and not isinstance(value, attr_type):
            value = attr_type(value)
        try:
            setattr(obj, attr, value)
            return True #success
        except:
            raise ValueError("incorrect value")

class ReserveringScribe(TypeScribe[Reservering]):
    """Scribe for managing Reserveringen with dependency mapping."""
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

    def _set_searchable_attrributes(self, obj: Reservering) -> tuple[str,...]:
        return 'nummer', 'fklant', 'fmodel', 'fmerk', 'status'

    def get_subtypes(self) -> list[str | None]:
        return [None, "Ingeleverd", "Lopend", "Particulier", "Professioneel"] 
    
    def _issubtype(self, obj) -> bool:
        if self._current_type is None:
            return True
        return obj.status.capitalize() == self._current_type or obj.klant.__class__.__name__ == self._current_type

    def get_columns(self) -> tuple[str, ...]:
        return "Nummer", "Klant", "Merk", "Model", "Van", "Tot", "Status"
    
    def get_rows(self) -> list[list[str]]:
        table: list[list[str]] = []
        for obj in self.view:
            table.append([obj.nummer, 
                          obj.fklant,
                          obj.fmerk, 
                          obj.fmodel,
                          str(obj.van), 
                          str(obj.tot),
                          obj.status.capitalize()])
        return table
    
    def update(self, obj: Reservering | int, attr: str, value: Any) -> bool:
        return super().update(obj, attr, value)