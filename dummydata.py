from datamodel import *
from _old_datastore import *
from datetime import timedelta

def generate_dummy_klanten(count: int = 10):
    jongensnamen = [
        "Jan", "Marc", "Luc", "Jean", "Pierre", "Dieter", "Hans", "Dirk", "Stijn", "Koen",
        "Thomas", "Bram", "Jeroen", "Niels", "Wout", "Arne", "Gilles", "Laurent", "Benoît", "Olivier",
        "Matthias", "Sven", "Ruben", "Maarten", "Florian", "Pascal", "Guillaume", "Christophe", "Lars", "Tobias"
    ]
    meisjesnamen = [
        "An", "Marie", "Isabelle", "Petra", "Elena", "Karin", "Sofie", "Katrijn", "Monique",
        "Emma", "Lotte", "Hanne", "Julie", "Charlotte", "Nathalie", "Claire", "Aline", "Chloé",
        "Ingrid", "Sabine", "Martine", "Leonie", "Marlies", "Eva", "Sarah", "Noémie"
    ]
    familienamen = [
        "Peeters", "Janssens", "Maes", "Willems", "Mertens", "Dubois", "Lambert", "Müller", "Schneider", "Hendrix",
        "Claes", "Goossens", "De Smet", "Vermeulen", "Jacobs", "Lefevre", "Moreau", "Weber", "Fischer", "Beckers",
        "Dupont", "Girard", "Keller", "Schmidt", "Kraus", "Bauer", "Bernard", "Rousseau", "Huber", "Vandenberghe"
    ]
    activiteiten = [
        "Logistics", "Solutions", "Security", "Schilderwerken", "Tuinonderhoud", 
        "Dakwerken", "Sanitair", "Elektriciteitswerken", "Renovaties", "Verhuisservice"
        ]
    gemeentes = [
        ("Hasselt", 3500), ("Genk", 3600), ("Maasmechelen", 3630), ("Tongeren", 3700), ("Lommel", 3920), 
        ("Beringen", 3580), ("Sint-Truiden", 3800), ("Maaseik", 3680), ("Diepenbeek", 3590), ("Zonhoven", 3520), 
        ("Heusden-Zolder", 3550), ("Houthalen-Helchteren", 3530), ("Bilzen", 3740), ("Lanaken", 3620), ("Dilsen-Stokkem", 3650), 
        ("Leopoldsburg", 3970), ("Peer", 3990), ("Nieuwerkerken", 3850), ("Wellen", 3830), ("Kinrooi", 3640)]
    
    for i in range(count):
        plaatsnaam, pc = gemeentes[np.random.randint(0,len(gemeentes))]
        achternaam = np.random.choice(familienamen)
        activiteit = np.random.choice(activiteiten)
        
        if np.random.choice([True, False]): # Male
            voornaam = np.random.choice(jongensnamen)
            geslacht = "M"
        else: # Female
            voornaam = np.random.choice(meisjesnamen)
            geslacht = "V"
        
        if i % 3 == 0: # 1/3 Professioneel
            lijst_klanten.append(Professioneel(
                naam=f"{voornaam[0]}. {achternaam} {activiteit}", 
                straat="Industrieweg", 
                huisnummer=np.random.randint(1, 200), 
                postcode=pc, 
                gemeente=plaatsnaam, 
                btwnummer=BTW()
            ))
        else:
            lijst_klanten.append(Particulier(
                naam=f"{voornaam} {achternaam}", 
                straat="Dorpsstraat", 
                huisnummer=np.random.randint(1, 150), 
                postcode=pc, 
                gemeente=plaatsnaam, 
                geslacht=geslacht, 
                geboortedatum=date(1970, 1, 1) + timedelta(days=np.random.randint(0, 12345))
        ))

def generate_dummy_vloot(tries: int = 2):
    wagens = { # [N1, M1, M1, M1]
        "Mercedes-Benz": ["Vito", "A-Klasse", "C-Klasse", "CLA"],
        "Renault": ["Master", "Clio", "Megane", "Captur"],
        "Opel": ["Vivaro", "Corsa", "Astra", "Mokka"],
        "Ford": ["Transit", "Fiesta", "Focus", "Mondeo"],
        "Volkswagen": ["Crafter", "Golf", "Polo", "Passat"],
        "Peugeot": ["Partner", "208", "308", "508"],
        "Toyota": ["Proace", "Corolla", "Yaris", "RAV4"],
        "BMW": [None, "1-Reeks", "3-Reeks", "i3"]
        }
    
    for merk, modellen in wagens.items():
        for i, model in enumerate(modellen):
            cat: VoertuigCategorie = "N1" if i == 0 else "M1"
            for _ in range(tries):
                if np.random.choice([True, False]) and model is not None:
                    lijst_voertuigen.append(Voertuig(
                        chassisnummer=VIN(),
                        merk=merk,
                        model=model,
                        bouwjaar=Bouwjaar(np.random.randint(2017, 2025)),
                        categorie=cat,
                        dagprijs=round(np.random.uniform(45.0, 95.0) if cat == "N1" else np.random.uniform(32.0, 65.0), 2)
                    ))

def generate_dummy_reservaties(count: int = 10):
    start_period, end_period = date(2025, 9, 1), date(2025, 11, 30)
    delta_days = (end_period - start_period).days
    klanten = lijst_klanten.copy()
    voertuigen = lijst_voertuigen.copy()
    for _ in range(count):
        i, j = np.random.randint(0, len(klanten)), np.random.randint(0, len(voertuigen))
        k, v = klanten.pop(i), voertuigen.pop(j)
        d_start = start_period + timedelta(days=np.random.randint(0, delta_days - 7))
        d_end = d_start + timedelta(days=np.random.randint(1, 7))
        re = np.random.choice([True, False])
        v.beschikbaar = True if re else False
        res = Reservering(klant=k, voertuig=v, van=d_start, tot=d_end, ingeleverd=re)
        lijst_reserveringen.append(res)

if __name__ == "__main__":
    generate_dummy_klanten(20)
    generate_dummy_vloot(3)
    generate_dummy_reservaties(20)
    update_data()