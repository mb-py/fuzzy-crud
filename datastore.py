import json
from pathlib import Path
from datamodel import Particulier, Professioneel, BTW, RRN, VIN
from datascrivener import KlantScribe, VoertuigScribe, ReserveringScribe
from typing import Any
from dataclasses import asdict

# Initialize the Scribes (Black Boxes)
klanten = KlantScribe()
voertuigen = VoertuigScribe()
reserveringen = ReserveringScribe()

DATA_FILE = "data.json"
TEST_FILE = "test.json"

def read_data():
    data_path = Path(DATA_FILE)
    if not data_path.exists():
        return
    
    json_data: dict[str, list[dict[str, Any]]] = {}
    with open(data_path, "r", encoding="utf-8") as f:
        try:
            json_data = json.load(f)
        except json.JSONDecodeError:
            return

    klanten.clear()
    klant_data = json_data.get('particulier', []) + json_data.get('professioneel', [])
    klanten.from_array(klant_data)

    voertuigen.clear()
    voertuigen.from_array(json_data.get('voertuigen', []))
    
    reserveringen.clear()
    reserveringen.from_array(
        json_data.get('reserveringen', []), 
        klanten.map, 
        voertuigen.map
    )

def save_data():
    """
    Placeholder for saving logic. 
    In the future, Scribes could implement a to_dict() method for serialization.
    """
    pass

def test_save():
    data = {
        "particulier": [vars(k) for k in klanten.all if isinstance(k, Particulier)],
        "professioneel": [vars(k) for k in klanten.all if isinstance(k, Professioneel)],
        "voertuigen": [vars(v) for v in voertuigen.all],
        "reserveringen": [{
            "nummer": r.nummer,
            "klant": r.klant.uid,
            "voertuig": r.voertuig.uid,
            "van": r.van,
            "tot": r.tot,
            "ingeleverd": r.ingeleverd
            } for r in reserveringen.all],
        "facturen": []
    }
    with open(TEST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4, default=str)


if __name__ == "__main__":
    # Test load
    read_data()
    print(f"Loaded {klanten.count} klanten")
    print(f"Loaded {voertuigen.count} voertuigen")
    print(f"Loaded {reserveringen.count} reserveringen")
    

    '''for k, v in vars(voertuigen[0]).items():
        print(k, v)

    for k, v in asdict(voertuigen[0]).items():
        print(k, v)
    '''

    print(asdict(klanten[0]))
    from dataclasses import fields

    for f in fields(klanten[0]): 
        print(f.type)
    
    '''
    for k in klanten.all:
        print(type(k), k.naam)
    for v in voertuigen.all:
        print(type(v), v.chassisnummer, v.merk, v.model, v.bouwjaar, v.beschikbaar)

    for r in reserveringen.all:
        print(f"{r.nummer}\t {r.klant.uid}  \t{r.voertuig.chassisnummer}\t {r.ingeleverd==r.voertuig.beschikbaar}")
        print(f"{r.klant.uid}\t {r.klant.naam}, {r.klant.straat} {r.klant.huisnummer}, {r.klant.gemeente}")
        print(f"{r.voertuig.chassisnummer[:10]}...\t {r.voertuig.merk} {r.voertuig.model}\t{r.voertuig.bouwjaar}\n")
    '''