# Tämä tiedosto on projektin ydin.
# Lukee paikallisena koneen metriikat psutil-kirjaston avulla.
# Demossa generoi simuloitua dataa - piikkejä, trendejä, zombie-prosesseja jne.
# Jos mode-muuttujaa ei ole asetettu, käytetään oletuksena paikallista

import os
import random
import math
import time
import psutil
from datetime import datetime

# Apufunktio, palauttaa värikoodin käyttöliittymää varten: "ok", "warning", "critical".
def get_status(value: float, warn_at: int = 65, crit_at: int = 85) -> str:
    if value >= crit_at:
        return "critical"
    elif value >= warn_at:
        return "warning"
    return "ok"

#psutil-kirjasto joka osaa lukea käyttöjärjestelmän tietoja.
def collect_live_metrics() -> dict:

    # Lukee metriikat psutil-kirjastolla ja palauttaa dictionaryn jossa kaikki tiedot.

    # Mittaa CPU-käytön prosentin 1 sekunnin aikana.
    # interval = 1 psutil odottaa sekunnin ja mittaa keskiarvon
    # tarkempi kuin interval = 0 joka antaa pelkän hetkellisen arvon.
    cpu_percent = psutil.cpu_percent(interval=1)

    # Montako loogista CPU-ydintä koneessa on
    cpu_count = psutil.cpu_count(logical=True)

    # RAM / Muisti
    # virtual_memory() palauttaa olion jossa on total, available, used, percent jne.
    ram = psutil.virtual_memory()
    ram_percent = ram.percent
    ram_used_gb = ram.used / (1024**3) # Muunnetaan tavuista gigatavuiksi
    ram_total_gb = ram.total / (1024**3)

    # Levy
    # disk_usage('/') lukee juurilevyn käyttötiedot.
    # windowsilla käytetään 'C:\\' juurilevyn sijaan.
    disk_path = 'C:\\' if os.name == 'nt' else '/'
    disk = psutil.disk_usage(disk_path)
    disk_percent = disk.percent
    disk_used_gb = disk.used / (1024**3)
    disk_total_gb = disk.total / (1024**3)

    # disk_io_counters() lukee levyn luku/kirjoitusmäärät käynnistymisestä lähtien.
    # Koska halutaan nopeus (MB/s), lasketaan ero kahden mittauksen välillä.
    # Tässä otetaan vain hetkellinen arvo - tarkempi laskenta tehdään db:ssä
    disk_io = psutil.disk_io_counters()
    disk_read_mb = round(disk_io.read_bytes / (1024**2), 1) if disk_io else 0
    disk_write_mb = round(disk_io.write_bytes / (1024**2), 1) if disk_io else 0

    # Verkko
    # net_io_counter() palauttaa kaikki verkkorajapinnat yhteensä.
    net_io = psutil.net_io_counters()
    net_sent_mb = round(net_io.bytes_sent / (1024**2), 1)
    net_recv_mb = round(net_io.bytes_recv / (1024**2), 1)

    # Prosessit
    # processes() palauttaa listan kaikista käynnissä olevista prosesseista.
    # Käydään läpi jokainen ja haetaan tiedot - status 'zombie' tarkoittaa
    # prosessia joka on lopettanut mutta jota parent-prosessi ei ole siivonnut.
    processes = []
    zombie_count = 0

    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info', 'status']):

        try:
            # proc.info on dictionary jossa on kaikki pyydetyt kentät
            info = proc.info

            # Lasketaan muisti megatavuissa
            mem_mb = round(info['memory_info'].rss / (1024**2), 1) if info['memory_info'] else 0

            is_zombie = info['status'] == psutil.STATUS_ZOMBIE

            if is_zombie:
                zombie_count += 1 # Lasketaan zombiet erikseen hälytystä varten

            processes.append({
                "pid": info['pid'],
                "name": info['name'],
                "cpu": round(info['cpu_percent'], 1),
                "mem_mb": mem_mb,
                "status": info['status'],
                "zombie": is_zombie
            })

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # Prosessi saattaa loppua kesken iteration tai ei ole oikeuksia
            # lukea sitä - ohitetaan se
            pass

    # Järjestetään prosessit CPU-käytön mukaan laskevasti (suurin ensin)
    processes.sort(key=lambda p: p['cpu'], reverse=True)

    # Otetaan vain top 10 prosessia käyttöliittymää varten
    top_processes = processes[:10]

    # Kootaan kaikki yhteen dictionaryyn
    return {
        "timestamp": datetime.now().isoformat(),
        "mode": "live",
        "cpu": {
            "percent": cpu_percent,
            "count": cpu_count,
            "status": get_status(cpu_percent)
        },
        "ram": {
            "percent": ram_percent,
            "used_gb": round(ram_used_gb, 1),
            "total_gb": round(ram_total_gb, 1),
            "status": get_status(ram_percent)
        },
        "disk": {
            "percent": disk_percent,
            "used_gb": round(disk_used_gb, 1),
            "total_gb": round(disk_total_gb, 1),
            "read_mb": disk_read_mb,
            "write_mb": disk_write_mb,
            "status": get_status(disk_percent)
        },
        "network": {
            "sent_mb": net_sent_mb,
            "recv_mb": net_recv_mb,
            "status": "ok" # Verkko ei yleensä ole pullonkaula - voidaan laajentaa myöhemmin
        },
        "processes": {
            "total": len(processes),
            "zombie": zombie_count,
            "top": top_processes
        }
    }

# Simuloitu data live demoa varten
# CPU piikkejä syntyy satunnaisesti
# Memory kasvaa hitaasti (simuloi memory leakia)
# 3 zombie-prosessia on aina olemassa

# Tallennetaan käynnistysaika jotta voidaan laskea "kuinka kauan käynnissä"
_demo_start_time = time.time()

# Muistin "leak" - kasvaa hiljalleen käynnistymisestä lähtien
_demo_memory_base = 45.0 # Oletusarvo

def collect_demo_metrics() -> dict:
    
    # Generoi simuloitua dataa, vaihtelee, piikkailee, ja trendit näkyvät
    
    # Kuinka monta sekuntia on kulunut käynnistymisestä
    elapsed = time.time() - _demo_start_time

    # CPU simulaatio
    cpu_base = 55 +20 * math.sin(elapsed / 60)

    # Satunnainen kohina tekee siitä realistisemman (+/- 8%)
    cpu_noise = random.gauss(0, 8)

    # Satunnainen piikki - 5% todennäköisyys joka kutsulla
    cpu_spike = 30 if random.random() < 0.05 else 0
    cpu_percent = max(5, min(98, cpu_base + cpu_noise + cpu_spike))

    # RAM simulaatio
    # Muisti kasvaa hiljalleen (simuloi memory leakia) - 0.001% per sekunti
    # Nollataan 80%:n jälkeen jotta demo ei jumiudu korkeaan arvoon
    memory_growth = (elapsed * 0.001) % 35
    ram_percent = _demo_memory_base + memory_growth + random.gauss(0, 2)
    ram_percent = max(30, min(92, ram_percent))
    ram_total_gb = 16.0
    ram_used_gb = round(ram_total_gb * ram_percent / 100, 1)

    # Levy simulaatio
    disk_percent = 70 + random.gauss(0, 2)
    disk_total_gb = 500.0
    disk_used_gb = round(disk_total_gb * disk_percent / 100, 1)
    disk_read_mb = round(max(0, 20 + random.gauss(0, 10)), 1)
    disk_write_mb = round(max(0, 15 + random.gauss(0, 8)), 1)

    # Verkko simulaatio
    net_sent = round(max(0, 12 + random.gauss(0, 5)), 1)
    net_recv = round(max(0, 47 + random.gauss(0, 15)), 1)

    # Simuloidut prosessit
    # Kiinteä lista prosesseista + 3 zombie prosessia
    top_processes = [
        {"pid": 1284, "name": "postgres",  "cpu": round(max(0, 32 + random.gauss(0, 5)), 1),  "mem_mb": 2150, "status": "running", "zombie": False},
        {"pid": 2041, "name": "nginx",     "cpu": round(max(0, 18 + random.gauss(0, 3)), 1),  "mem_mb": 340,  "status": "running", "zombie": False},
        {"pid": 3302, "name": "python3",   "cpu": round(max(0, 14 + random.gauss(0, 4)), 1),  "mem_mb": 890,  "status": "running", "zombie": False},
        {"pid": 4471, "name": "defunct",   "cpu": 0.0, "mem_mb": 0, "status": "zombie",  "zombie": True},
        {"pid": 4502, "name": "defunct",   "cpu": 0.0, "mem_mb": 0, "status": "zombie",  "zombie": True},
        {"pid": 5118, "name": "defunct",   "cpu": 0.0, "mem_mb": 0, "status": "zombie",  "zombie": True},
    ]

    return {
        "timestamp": datetime.now().isoformat(),
        "mode": "demo",
        "cpu": {
            "percent":  round(cpu_percent, 1),
            "count":    8,
            "status":   get_status(cpu_percent)
        },
        "ram": {
            "percent":  round(ram_percent, 1),
            "used_gb":  ram_used_gb,
            "total_gb": ram_total_gb,
            "status":   get_status(ram_percent)
        },
        "disk": {
            "percent":  round(disk_percent, 1),
            "used_gb":  disk_used_gb,
            "total_gb": disk_total_gb,
            "read_mb":  disk_read_mb,
            "write_mb": disk_write_mb,
            "status":   get_status(disk_percent)
        },
        "network": {
            "sent_mb":  net_sent,
            "recv_mb":  net_recv,
            "status":   "ok"
        },
        "processes": {
            "total":  247,
            "zombie": 3,
            "top":    top_processes
        }
    }

# Pääfunktio - valitsee moodin automaattisesti
# Tätä funktiota kutsutaan muualta (main.py, database.py jne.)
# Ohjelma tarkistaa MODE-ympäristömuuttujan ja kutsuu oikea funktiota

def collect_metrics() -> dict:

    #os.getenv lukee ympäristömuuttujan - jos sitä ei ole, käytetään oletusta "live"
    mode = os.getenv("MODE", "live").lower()

    if mode == "demo":
        return collect_demo_metrics()
    else:
        return collect_live_metrics()
    
# Testaus - voidaan ajaa suoraan: python collector.py
# Tämä lohko suoritetaan vain kun tiedosto ajetaan suoraan,
# ei kun se importoidaan toisesta tiedostosta.
# Hyödyllinen testaamiseen kehityksen aikana

if __name__ == "__main__":
    import json # Tulostetaan data siististi JSON-muodossa

    print("=== GHOST.SYS collector.py testi ===\n")

    print("--- LIVE MOODI ---")
    live_data = collect_live_metrics()
    print(json.dumps(live_data, indent=2, ensure_ascii=False))

    print("\n--- DEMO MOODI ---")
    demo_data = collect_demo_metrics()
    print(json.dumps(demo_data, indent=2, ensure_ascii=False))