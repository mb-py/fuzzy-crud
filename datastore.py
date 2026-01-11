import json
from pathlib import Path
from datamodel import Particulier, Professioneel
from datascrivener import KlantScribe, VoertuigScribe, ReserveringScribe, FactuurScribe
from typing import Any

# Initialize the Scribes (Black Boxes)
klanten = KlantScribe()
voertuigen = VoertuigScribe()
reserveringen = ReserveringScribe()
facturen = FactuurScribe()

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

    klant_data = json_data.get('particulier', []) + json_data.get('professioneel', [])
    voertuigen_data = json_data.get('voertuigen', [])
    reserveringen_data = json_data.get('reserveringen', [])
    facturen_data = json_data.get('facturen', [])
    
    klanten.clear()
    klanten.from_array(klant_data)
    voertuigen.clear()
    voertuigen.from_array(voertuigen_data)

    reserveringen.clear()
    reserveringen.from_array(reserveringen_data, klanten.uids, voertuigen.uids)
    
    facturen.clear()
    facturen.from_array(facturen_data, reserveringen.uids)

def save_data():
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
        "facturen": [{
            "reservering": f.uid,
            "bedrag": f.bedrag
        } for f in facturen.all]
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4, default=str)


if __name__ == "__main__":
    # Test load
    DATA_FILE = "test.json"
    read_data()
    print(f"Loaded {klanten.count} klanten")
    print(f"Loaded {voertuigen.count} voertuigen")
    print(f"Loaded {reserveringen.count} reserveringen")
    
    for r in reserveringen.all:
        print(r.klant.naam)
    save_data()
    
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