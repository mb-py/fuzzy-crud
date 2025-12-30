from dataclasses import dataclass, field
from datetime import date
from typing import ClassVar, Generator, Literal, Any, Self
import numpy as np

# --- Field Type Definities (string logica?) en Aliases ---
Genders = Literal["M", "V", "F"]
VoertuigCategorie = Literal["M1", "N1"]
'''
Categorie M1: "ontworpen en gebouwd voor het vervoer van personen" = Personenauto, minibus, kampeerauto
Categorie N1: "ontworpen en gebouwd voor het vervoer van goederen" = Lichte bedrijfswagen (lichter dan 3500 kg), bestelbusje
'''

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
            data = cls.generate()
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
    def generate(cls) -> str:
        base = ''.join(np.random.choice(list(cls.legal_characters), size=17))
        chk = cls._checksum(base)
        return base[:8] + chk + base[9:]
        
class BTW(str):
    legal_characters: ClassVar[str] = '0123456789.'

    def __new__(cls, data: str = ''):
        data = data.upper().strip()
        if not data:
            data = cls.generate()
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
    def generate(cls) -> str:
        x, y, z = np.random.randint(100,1000), np.random.randint(100,1000), np.random.randint(0,10)
        data = f"{np.random.choice([0,1])}{x:04d}.{y:03d}.{z:01d}"
        return data + cls._checksum(data)

class RRN(str):
    legal_characters: ClassVar[str] = '0123456789.-'

    def __new__(cls, data: str = '', geboortedatum:date|None = None, is_man:bool|None = None):
        data = data.upper().strip()
        if not data and geboortedatum and (is_man is not None):
            #een "string" met argumenten voelt fout, maar w/e: RRN(geboortedatum=date(...), is_man=True)
            data = cls.generate(geboortedatum, is_man)
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
        if int(numbersonly[:2]) <= 25:
            rrn_num += '2'
        rrn_num += numbersonly[:9]
        chk_num: int = 97 - int(rrn_num) % 97
        return f"{chk_num:02d}"

    @classmethod
    def generate(cls, geboortedatum: date, is_man: bool) -> str:
        x: str = geboortedatum.strftime("%y.%m.%d")
        y: int = np.random.randint(0,499)*2
        y += 1 if is_man else 2
        data = f"{x}-{y:03d}."
        return data + cls._checksum(data)
    
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
def _deserialize_dates(data: dict[str, Any], *keys: str) -> None:
    for key in keys:
        date_str = data.get(key)
        if isinstance(date_str, str):
            data[key] = date.fromisoformat(date_str)

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
    def uid(self) -> str: 
        raise NotImplementedError

@dataclass
class Particulier(Klant):
    geboortedatum: date
    geslacht: Genders
    rijksregisternummer: RRN = field(default=RRN(''), kw_only=True)

    def __post_init__(self):
        #maak rijksregisternummers
        if not self.rijksregisternummer:
            geslacht: bool = self.geslacht == "M"
            self.rijksregisternummer = RRN(geboortedatum=self.geboortedatum, is_man=geslacht)

    @property
    def uid(self) -> str: 
        return self.rijksregisternummer

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        #maak een instance van JSON Object of Dict
        d = data.copy() #data blijft droog   try
        try: 
            d['huisnummer'] = int(d.get('huisnummer', 0))
            d['postcode'] = int(d.get('postcode', 0))
            _deserialize_dates(d, 'geboortedatum')
            d['geslacht'] = str(d.get('geslacht', 'X'))[0].upper()
            d['rijksregisternummer'] = RRN(d.get('rijksregisternummer', ''))
        except ValueError:
            pass
        return cls(**d)

@dataclass
class Professioneel(Klant):
    btwnummer: BTW

    @property
    def uid(self) -> str: 
        return self.btwnummer

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        #maak een instance van JSON Object of Dict
        d = data.copy() #data blijft droog
        try:
            #strings
            d['huisnummer'] = int(d.get('huisnummer', 0))
            d['postcode'] = int(d.get('huisnummer', 0))
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
    def uid(self) -> str: 
        return self.chassisnummer
    
    @property
    def status(self) -> str:
        return "beschikbaar" if self.beschikbaar else "gereserveerd"
    
    @property
    def soort(self) -> str: 
        return "bestelbusje" if self.categorie == "N1" else "personenwagen"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        #maak een instance van JSON Object of Dict
        d = data.copy()
        #hydrateer VIN, Bouwjaar fields
        d['chassisnummer'] = VIN(d.get('chassisnummer', ''))
        d['bouwjaar'] = Bouwjaar(d.get('bouwjaar', '1'))
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
    def uid(self) -> str: 
        return self.nummer
    
    @property
    def status(self) -> str:
        if self.ingeleverd:
            return "ingeleverd"
        return "lopend"
    
    @property
    def fklant(self) -> str: 
        return self.klant.naam
    
    @property
    def fmerk(self) -> str: 
        return f"{self.voertuig.merk}"
    
    @property
    def fmodel(self) -> str: 
        return f"{self.voertuig.model}"
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        #maak een instance van JSON Object of Dict
        d = data.copy()
        #hydrateer Klant, Voertuig, date fields
        _deserialize_dates(d, 'van', 'tot')
        # ingeleverd = bool or te laat (date)
        ingeleverd = d.get('ingeleverd')
        if isinstance(ingeleverd, str):
            match ingeleverd.lower():
                case 'false': d['ingeleverd'] = False
                case 'true':  d['ingeleverd'] = True
                case _: d['ingeleverd'] = date.fromisoformat(ingeleverd)
        return cls(**d)

@dataclass
class Factuur:
    reservering: Reservering
    bedrag: float = field(default=0)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any], map_reserveringen: dict[str, Reservering]) -> Self:
        #maak een instance van JSON Object of Dict
        d = data.copy()
        #hydrateer Reservering
        _deserialize_obj(d, 'reservering', map_reserveringen)
        return cls(**d)