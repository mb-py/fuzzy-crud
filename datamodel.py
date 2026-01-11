from dataclasses import dataclass, field
from datetime import date
from typing import ClassVar, Generator, Any, Self
import numpy as np
from enum import Enum

# --- Field Type Definities (String-Fu) ---
class Gender(str, Enum):
    Male = "M"
    Female = "V"
    
    @property
    def description(self) -> str:
        """Human-readable value"""
        return {
            "M": "Man",
            "V": "Vrouw",
        }[self.value]
    
    @classmethod
    def parse(cls, data: str) -> Gender:
        """Parse from strings"""
        data = data.strip().capitalize()
        # char match
        for gender in cls:
            if gender.value == data.upper():
                return gender
        # woord match
        synonym = {
            "Man": cls.Male,
            "Male": cls.Male,
            "Vrouw": cls.Female,
            "Female": cls.Female,
        }
        if data in synonym:
            return synonym[data]
        
        raise ValueError(f"Invalid attack-helicopter: {data}.")
    
    def __str__(self) -> str:
        """Display the description by default"""
        return self.name 
    
class VoertuigCategorie(str, Enum):
    M1 = "M1"   # Personenwagen <9 zitplaatsen
    M2 = "M2"   # Bus MTM <5t
    M3 = "M3"   # Bus MTM >5t
    N1 = "N1"   # Lichte bedrijfsauto   MTM <3.5t
    N2 = "N2"   # Zware bedrijfsauto    MTM <12t
    N3 = "N3"   # Zware bedrijfsauto    MTM >12t
    
    @property
    def description(self) -> str:
        """Human-readable value"""
        return {
            "M1": "Personenwagen",
            "M2": "Minibus",
            "M3": "Bus",
            "N1": "Bestelbus",
            "N2": "Bakwagen",
            "N3": "Vrachtwagen"
            }[self.value]
    
    @classmethod
    def parse(cls, data: str) -> VoertuigCategorie:
        """Parse from code (M1, N1) or name (Personenwagen, Bestelbus) strings"""
        data = data.strip().capitalize()
        # code match
        for categorie in cls:
            if categorie.value == data.upper():
                return categorie
        # woord match
        synonym = {
            "Personenwagen": cls.M1,
            "Personenauto": cls.M1,
            "Auto": cls.M1,
            "Minibus": cls.M2,
            "Bus": cls.M3,
            "Bestelwagen": cls.N1,
            "Bestelbusje": cls.N1,
            "Combi": cls.N1,
            "Bakwagen": cls.N2,
            "Vrachtwagen": cls.N3
            }
        if data in synonym:
            return synonym[data]
        # Fail
        raise ValueError(f"Invalid category: {data}")
    
    def __str__(self) -> str:
        """Display the description by default"""
        return self.description  

class VIN(str):
    legal_characters: ClassVar[str] = '0123456789ABCDEFGHJKLMNPRSTUVWXYZ'
    legal_chk_digits: ClassVar[str] = '0123456789X'
    weights: ClassVar[list[int]] = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]
    vintoi: ClassVar[dict[str,int]] = { '0': 0, 
        '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, 
        'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6, 'G': 7, 'H': 8, 
        'J': 1, 'K': 2, 'L': 3, 'M': 4, 'N': 5,         'P': 7,         'R': 9, 
                'S': 2, 'T': 3, 'U': 4, 'V': 5, 'W': 6, 'X': 7, 'Y': 8, 'Z': 9
        }
    
    def __new__(cls, data: str = ''):
        data = data.upper().strip()
        if not data:
            return cls.generate()
        return super().__new__(cls, data)
    
    @classmethod
    def isvalid(cls, data: str) -> bool:
        if len(data) != 17 or any(char not in cls.legal_characters for char in data):
            return False
        return data[8] == cls._checksum(data)
    
    @classmethod
    def _checksum(cls, data: str) -> str:
        #Transliterate VIN tekens (vintoi.keys / vindigits) naar Numerische Waarde (vintoi.values)
        translt: list[int] = [cls.vintoi[c] for c in data[0:17]]
        #Som, het Product van Values en Weights, Modulo 11
        chk_sum: int = sum(cls.weights[i] * v for i, v in enumerate(translt)) % 11
        return cls.legal_chk_digits[chk_sum]
    
    @classmethod
    def generate(cls) -> VIN:
        base = ''.join(np.random.choice(list(cls.legal_characters), size=17))
        chk = cls._checksum(base)
        data = base[:8] + chk + base[9:]
        return VIN(data)
  
class BTW(str):
    legal_characters: ClassVar[str] = '0123456789.'

    def __new__(cls, data: str = ''):
        data = data.upper().strip()
        if not data:
            return cls.generate()
        return super().__new__(cls, data)

    @classmethod
    def isvalid(cls, data: str) -> bool:
        if len(data) != 12 or any(char not in BTW.legal_characters for char in data):
            return False
        if len(data.replace('.','')) != 10 or not (data[4] == data[8] == "."):
            return False
        return data[-2:] == cls._checksum(data)
    
    @classmethod
    def _checksum(cls, data: str) -> str:
        numbersonly = data.replace('.','')
        btw_num: str = numbersonly[:8]
        chk_num: int = 97 - int(btw_num) % 97
        return str(chk_num)

    @classmethod
    def generate(cls) -> BTW:
        x, y, z = np.random.randint(100,1000), np.random.randint(100,1000), np.random.randint(0,10)
        data = f"{np.random.choice([0,1])}{x:04d}.{y:03d}.{z:01d}"
        data += cls._checksum(data)
        return BTW(data)

class RRN(str):
    legal_characters: ClassVar[str] = '0123456789.-'

    def __new__(cls, data: str = ''):
        data = data.upper().strip()
        '''if not data:
            return cls.generate(date(1950,1,1), True)'''
        return super().__new__(cls, data)

    @classmethod
    def isvalid(cls, data: str) -> bool:
        if len(data) != 15 or any(char not in cls.legal_characters for char in data):
            print("wrong length of chars")
            return False
        if len(data.replace('.','').replace('-','')) != 11:
            print("wrong length ")
            return False
        if not(data[2] == data[5] == data[12] == ".") or not(data[8] == "-"):
            print("bad formatting")
            return False
        return data[-2:] == cls._checksum(data)
    
    @classmethod
    def _checksum(cls, data: str) -> str:
        numbersonly = data.replace('.','').replace('-','')
        rrn_num: str = ''
        if int(numbersonly[:2]) <= date.today().year%100: #eeuwenwisseling
            rrn_num += '2'
        rrn_num += numbersonly[:9]
        chk_num: int = 97 - int(rrn_num) % 97
        return f"{chk_num:02d}"

    @classmethod
    def generate(cls, geboortedatum: date, is_man: bool) -> RRN:
        x: str = geboortedatum.strftime("%y.%m.%d")
        y: int = np.random.randint(0,499)*2     #0 =< y =< 996
        y += 1 if is_man else 2                 #0 < y < 999
        data = f"{x}-{y:03d}."
        data += cls._checksum(data)
        return RRN(data)

class Bouwjaar(date):
    def __new__(cls, year: int | str):
        return super().__new__(cls, int(year), 1, 1)

    def __repr__(self):
        return '{0}({1}, 1, 1)'.format(self.__class__.__name__, self.year)
    
    def __str__(self):
        return self.strftime("%Y")

    def __reduce__(self):
        return (self.__class__, (self.year,))

# --- Generator en Helper functies ---
def _deserialize_obj(data: dict[str, Any], key: str, datamap: dict[str, Any]) -> None: #!depreciated
    id = data.get(key)
    if isinstance(id, str):
        data[key] = datamap[id]

def today_generator() -> Generator[str, None, None]:
    today: str = date.today().strftime("%y%m%d")
    i: int = 0
    while True:
        i += 1
        yield f"{today}-{i:03d}"

RESERVATIE_NUMMER: Generator = today_generator()

# --- Dataclasses ---
@dataclass
class Klant:
    naam: str
    straat: str
    huisnummer: int
    postcode: int
    gemeente: str

    @property #voor lookup dictionary of str reference
    def uid(self) -> str | None: 
        raise NotImplementedError

    @property
    def strftype(self) -> str:
        return self.__class__.__name__.capitalize()
    
@dataclass
class Particulier(Klant):
    geboortedatum: date
    geslacht: Gender
    rijksregisternummer: RRN = field(kw_only=True)

    def __post_init__(self):
        #maak rijksregisternummers
        if not RRN.isvalid(self.rijksregisternummer):
            self.rijksregisternummer = RRN.generate(self.geboortedatum, self.geslacht == "M")

    @property
    def uid(self) -> str | None: 
        if self.rijksregisternummer == '00.00.00-000.29':
            return None
        return self.rijksregisternummer
        
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        #maak een instance van JSON Object of Dict
        d = data.copy() #data blijft droog   try
        try: 
            d['huisnummer'] = int(d.get('huisnummer', 0))
            d['postcode'] = int(d.get('postcode', 0))
            d['geboortedatum'] = date.fromisoformat(d.get('geboortedatum', '2001-01-01'))
            d['geslacht'] = Gender.parse(d.get('geslacht', 'M'))
            d['rijksregisternummer'] = RRN(d.get('rijksregisternummer', ''))
        except ValueError:
            pass
        return cls(**d)

@dataclass
class Professioneel(Klant):
    btwnummer: BTW

    @property
    def uid(self) -> str | None: 
        if self.btwnummer == '00000.000.000':
            return None
        return self.btwnummer

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        #maak een instance van JSON Object of Dict
        d = data.copy() #data blijft droog
        try:
            #strings
            d['huisnummer'] = int(d.get('huisnummer', 0))
            d['postcode'] = int(d.get('postcode', 0))
            #hydrateer BTW fields
            d['btwnummer'] = BTW(d.get('btwnummer', ''))
        except ValueError:
            pass
        return cls(**d)

@dataclass   
class Voertuig:
    chassisnummer: VIN
    merk: str
    model: str
    bouwjaar: Bouwjaar
    categorie: VoertuigCategorie
    beschikbaar: bool = field(default=True)
    dagprijs: float = field(default=35.99)

    @property
    def uid(self) -> str | None: 
        if self.chassisnummer == '00000000000000000':
            return None
        return self.chassisnummer
    
    @property
    def status(self) -> str:
        return "beschikbaar" if self.beschikbaar else "gereserveerd"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        #maak een instance van JSON Object of Dict
        d = data.copy()
        #hydrateer VIN, Bouwjaar fields
        d['chassisnummer'] = VIN(d.get('chassisnummer', ''))
        d['bouwjaar'] = Bouwjaar(d.get('bouwjaar', '1'))
        d['categorie'] = VoertuigCategorie.parse(d.get('categorie', 'M1'))
        return cls(**d)

@dataclass
class Reservering:
    nummer: str = field(default_factory=lambda: next(RESERVATIE_NUMMER), kw_only=True)
    klant: Klant
    voertuig: Voertuig
    van: date
    tot: date
    ingeleverd: bool | date = field(default=False)

    @property
    def uid(self) -> str | None:
        if self.klant.uid is None or self.voertuig.uid is None:
            return None
        return self.nummer
    
    @property
    def status(self) -> str:
        if self.ingeleverd:
            return "ingeleverd"
        return "lopend"
    
    @property
    def duur(self) -> int:
        return (self.tot - self.van).days + 1
    
    @property
    def strfklant(self) -> str: 
        return self.klant.naam
    
    @property
    def strftype(self) -> str:
        return self.klant.strftype
    
    @property
    def strfmerk(self) -> str: 
        return self.voertuig.merk
    
    @property
    def strfmodel(self) -> str: 
        return self.voertuig.model
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        #maak een instance van JSON Object of Dict
        d = data.copy()
        #hydrateer date fields
        try: 
            d['van'] = date.fromisoformat(d.get('van','1999-12-30'))
            d['tot'] = date.fromisoformat(d.get('tot','1999-12-31'))
            status = d.get('ingeleverd', '1999-12-31')
            d['ingeleverd'] = status if type(status) is bool else date.fromisoformat(status)
        except ValueError:
            pass
            
        return cls(**d)

@dataclass
class Factuur:
    reservering: Reservering
    bedrag: float = field(default=0)

    @property
    def uid(self) -> str | None: 
        return self.reservering.nummer
    
    @property
    def duur(self) -> int: 
        return self.reservering.duur
    
    @property
    def strfklant(self) -> str: 
        return self.reservering.strfklant
    
    @property
    def strftype(self) -> str: 
        return self.reservering.strftype
    
    @property
    def strfmerk(self) -> str: 
        return self.reservering.strfmerk
    
    @property
    def strfmodel(self) -> str: 
        return self.reservering.strfmodel
    
    
    def __post_init__(self):
        self.reservering.voertuig.beschikbaar = True
        self.reservering.ingeleverd = True
        if self.bedrag == 0:
            dagprijs = self.reservering.voertuig.dagprijs
            duur = self.reservering.duur
            self.bedrag = dagprijs * duur

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        #maak een instance van JSON Object of Dict
        d = data.copy()
        '''#hydrateer Reservering
        _deserialize_obj(d, 'reservering', map_reserveringen)'''
        return cls(**d)
    
    @classmethod
    def from_finalize_reservatie(cls, r: Reservering, inleverdatum: date|None = None):
        r, bedrag = cls.finalize_reservatie(r, inleverdatum)
        return cls(r, bedrag)
    
    @classmethod
    def finalize_reservatie(cls, r: Reservering, inleverdatum: date|None = None):
        wagen = r.voertuig
        bedrag = wagen.dagprijs * r.duur
        r.ingeleverd = True
        wagen.beschikbaar = True
        if inleverdatum is not None and inleverdatum > r.tot:
            r.ingeleverd = inleverdatum
            telaat = (inleverdatum - r.tot).days
            bedrag += (wagen.dagprijs * telaat)*2
        return r, bedrag

if __name__ == "__main__":
    rrn = RRN('00.00.00-000.29')
    print(rrn, RRN._checksum('00.00.00-000.29'))