# Tämä tiedosto analysoi kerättyä metriikkadataa ja etsii ongelmia
# Etsii zombie prosesseja ja tunnistaa niiden vanhempiprosessin
# Tunnistaa memory leak -patternin
# Analysoi mikä resurssi on pullonkaula (CPU/RAM/levy/verkko)
# Laskee CPU-trendin - onko käyttö kasvussa vai laskussa
# Ennustaa milloin levy täyttyy nykyisellä kasvuvauhdilla
# Hälytykset yhdessä listassa

# Tätä kutsutaan main.py:stä kun frontend pyytää analyysidataa.

from database import get_history, get_weekly_summary   
from collector import collect_metrics            
from datetime import datetime  

# Zombie prosessien analyysi
# Ne eivät kuluta CPU:ta tai muistia mutta vievät prosessitaulusta tilaa
# Liian monta zombieta voi hidastaa järjestelmää

def analyze_zombies(processes: list) -> dict:

    # Analysoi prosessilistan
    zombies = [p for p in processes if p.get("zombie", False)]

    # Lasketaan vakavuusaste zombien määrän perusteella
    if len(zombies) == 0:
        severity = "ok"
        message = "Ei zombie-prosesseja"
    elif len(zombies) <= 3:
        severity = "warning"
        message = f"{len(zombies)} zombie-prosessia havaittu - seuraa tilannetta"
    else:
        severity = "critical"
        message = f"{len(zombies)} zombie-prosessia - järjestelmä saattaa olla epävakaa"

    return {
        "count": len(zombies),
        "zombies": zombies,
        "severity": severity,
        "message": message
    }

# Memory leak -patternin tunnistus
# Memory leak tarkoittaa että ohjelma varaa muistia mutta ei vapauta sitä.
# Se näkyy datassa tasaisena muistin kasvuna ajan kuluessa.

def analyze_memory_leak(history: list) -> dict:

    # Tunnistaa memory leak -patternin historiadatasta
    if len(history) < 10:
        return {
            "detected": False,
            "severity": "ok",
            "message": "Liian vähän dataa analyysiin - kerää enemmän historiaa",
            "growth_per_hour": 0,
            "days_until_full": None
        }
    
    # Jaetaan data kahteen puoliskoon
    mid = len(history) // 2
    first_half = history[:mid]
    second_half = history[mid:]

    # Lasketaan muistin keskiarvo molemmille puoliskoille
    avg_first = sum(r["ram_percent"] for r in first_half) / len(first_half)
    avg_second = sum(r["ram_percent"] for r in second_half) / len(second_half)

    # Kasvu prosenttiyksikköä per mittausjakso
    growth = avg_second - avg_first

    # Muutetaan kasvu tuntikohtaiseksi
    growth_per_hour = round(growth / (len(history) / 720), 2)

    # Ennustetaan milloin muisti täyttyy (100%) nykyisellä kasvuvauhdilla
    if growth_per_hour > 0 and len(history) > 0:
        current_ram = history[-1]["ram_percent"]
        hours_until_full = (100 - current_ram) / growth_per_hour
        days_until_full = round(hours_until_full / 24, 1)
    else:
        days_until_full = None

    # Määritellään vakavuusaste kasvuvauhdin perusteella
    if growth_per_hour <= 0:
        # Muisti ei kasva - kaikki ok
        detected = False
        severity = "ok"
        message = "Ei memory leak -patternia havaittu"
    elif growth_per_hour < 0.5:
        # Pieni kasvu - seurataan
        detected = True
        severity = "warning"
        message = f"Lievä muistin kasvu havaittu: +{growth_per_hour}% / tunti"
    else:
        # Selvä leak-pattern
        detected = True
        severity = "critical"
        message = f"Memory leak -pattern tunnistettu: +{growth_per_hour}% / tunti"

    return {
        "detected": detected,
        "severity": severity,
        "message": message,
        "growth_per_hour": growth_per_hour,
        "days_until_full": days_until_full
    }

# Bottleneck - analyysi

def analyze_bottleneck(current_metrics: dict) -> dict:

    # Analysoi nykyiset metriikat ja tunnistaa pullonkaulan
    # Ketätään kaikkien resurssien käyttöasteet yhteen listaan
    resources = [
        {
            "name": "CPU",
            "percent": current_metrics["cpu"]["percent"],
            "status": current_metrics["cpu"]["status"]
        },
        {
            "name": "RAM",
            "percent": current_metrics["ram"]["percent"],
            "status": current_metrics["ram"]["status"]
        },
        {
            "name": "Levy",
            "percent": current_metrics["disk"]["percent"],
            "status": current_metrics["disk"]["status"]
        }
    ]

    # Järjestetään resurssit käyttöäasteen mukaan - suurin ensin
    resources.sort(key=lambda r: r["percent"], reverse=True)

    # Suurin käyttöaste = pullonkaula
    bottleneck = resources[0]

    # Määritellään vakavuus
    if bottleneck["status"] == "critical":
        severity = "critical"
        message = f"Pullonkaula: {bottleneck['name']} {bottleneck['percent']}% - toimenpiteet tarpeellisia"
    elif bottleneck["status"] == "warning":
        severity = "warning"
        message = f"Korkea käyttöaste: {bottleneck['name']} {bottleneck['percent']}% - seuraa tilannetta"
    else:
        severity = "ok"
        message = "Ei pullonkauloja havaittu - järjestelmä toimii normaalisti"

    return {
        "bottleneck": bottleneck["name"],
        "percent": bottleneck["percent"],
        "severity": severity,
        "message": message,
        "all": resources # Kaikki resurssit järjestyksessä
    }

# CPU - trendi
# Lasketaan onko CPU-käyttö kasvussa tai laskussa viimeisen tunnin aikana

def analyze_cpu_trend(history: list) -> dict:

    if len(history) < 6:
        return {
            "trend": "unknown",
            "change": 0,
            "message": "Liian vähän dataa trendi analyysiin"
        }
    
    # Jaetaan data kahteen puoliskoon
    mid = len(history) // 2
    avg_first = sum(r["cpu_percent"] for r in history[:mid]) / mid
    avg_second = sum(r["cpu_percent"] for r in history[mid:]) / (len(history) - mid)

    # Lasketaan muutos prosenttiyksikköinä
    change = round(avg_second - avg_first, 1)

    # Määritellään trendin suunta
    if change > 5:
        trend = "rising"
        message = f"CPU-käyttö kasvussa: +{change}% viimeisen jakson aikana"
    elif change < -5:
        trend = "falling"
        message = f"CPU-käyttö laskussa: {change}% viimeisen jakson aikana"
    else:
        trend = "stable"
        message = f"CPU-käyttö vakaa: muutos {change}%"

    return {
        "trend": trend,
        "change": change,
        "message": message
    }

# Disk - ennuste
# Ennustetaan milloin levy täyttyy nykyisellä kasvuvauhdilla

def analyze_disk_forecast(history: list, current_disk_percent: float) -> dict:

    if len(history) < 10:
        return {
            "severity": "ok",
            "message": "Liian vähän dataa ennusteeseen",
            "days_until_90": None
        }
    
    # Lasketaan levyn kasvuvauhti
    oldest_disk = history[0]["disk_percent"]
    newest_disk = history[-1]["disk_percent"]
    growth = newest_disk - oldest_disk

    # Jos levy ei kasva, ei ongelmaa
    if growth <= 0:
        return {
            "severity": "ok",
            "message": "Levyn käyttö vakaa tai laskussa",
            "days_until_90": None
        }
    
    # Lasketaan kuinka monta päivää dataa on
    try:
        oldest_time = datetime.fromisoformat(history[0]["timestamp"])
        newest_time = datetime.fromisoformat(history[-1]["timestamp"])
        days_of_data = max((newest_time - oldest_time).total_seconds() / 86400, 0.001)
    except Exception:
        days_of_data = 1 # Oletus

    # Kasvu päivässä
    growth_per_day = growth / days_of_data

    # Ennuste - milloin levy saavuttaa 90% (varoitusraja)
    if current_disk_percent < 90:
        days_until_90 = round((90 - current_disk_percent) / growth_per_day, 0) if growth_per_day > 0 else None
    else:days_until_90 = 0 # Jo ylitetty

    # Määritellään vakavuus
    if current_disk_percent >= 90:
        severity = "critical"
        message = f"Levy {current_disk_percent}% täynnä - kriittinen taso ylitetty!"
    elif current_disk_percent >= 75:
        severity = "warning"
        message = f"Levy {current_disk_percent}% täynnä - täyttyy {days_until_90} päivässä"
    else:
        severity = "ok"
        message = f"Levytila ok ({current_disk_percent}%)"

    return {
        "severity": severity,
        "message": message,
        "days_until_90": days_until_90,
        "growth_per_day": round(growth_per_day, 2)
    }

# Hälytykset - kootaan kaikki analyysit yhteen

def get_alerts(current_metrics: dict, history: list) -> list:

    # Kokoaa kaikki hälytykset yhdeksi listaksi
    alerts = []

    # Zombie analyysi
    zombie_result = analyze_zombies(current_metrics["processes"]["top"])
    if zombie_result["severity"] != "ok":
        alerts.append({
            "type": "zombie",
            "severity": zombie_result["severity"],
            "message": zombie_result["message"],
            "count": zombie_result["count"]
        })

    # Memory leak analyysi
    leak_result = analyze_memory_leak(history)
    if leak_result["detected"]:
        alerts.append({
            "type": "memory-leak",
            "severity": leak_result["severity"],
            "message": leak_result["message"],
            "growth_per_hour": leak_result["growth_per_hour"],
            "days_until_full": leak_result["days_until_full"]
        })

    # CPU tason hälytys
    cpu_percent = current_metrics["cpu"]["percent"]
    if current_metrics["cpu"]["status"] == "critical":
        alerts.append({
            "type": "cpu_high",
            "severity": "critical",
            "message": f"CPU-käyttö kriittinen: {cpu_percent}%",
            "percent": cpu_percent
        })
    elif current_metrics["cpu"]["status"] == "warning":
        alerts.append({
            "type": "cpu_high",
            "severity": "warning",
            "message": f"CPU-käyttö korkea: {cpu_percent}%",
            "percent": cpu_percent
        })

    # Levyn tason hälytys
    disk_result = analyze_disk_forecast(history, current_metrics["disk"]["percent"])
    if disk_result["severity"] != "ok":
        alerts.append({
            "type": "disk_space",
            "severity": disk_result["severity"],
            "message": disk_result["message"],
            "days_until_90": disk_result.get("days_until_90")
        })

    # Järjesttään hälytykset vakavuuden mukaan
    severity_order = {"critical": 0, "warning": 1, "info": 2, "ok": 3}
    alerts.sort(key=lambda a: severity_order.get(a["severity"], 99))

    return alerts


# Täysi analyysi - kaikki kerralla

def run_full_analysis() -> dict:

    # Haetaan viimeisin data ja historia
    current = collect_metrics()
    history = get_history(hours=24)
    weekly = get_weekly_summary()

    return {
        "timestamp": current["timestamp"],
        "zombies": analyze_zombies(current["processes"]["top"]),
        "memory_leak": analyze_memory_leak(history),
        "bottleneck": analyze_bottleneck(current),
        "cpu_trend": analyze_cpu_trend(history),
        "disk_forecast": analyze_disk_forecast(history, current["disk"]["percent"]),
        "alerts": get_alerts(current, history),
        "weekly": weekly
    }

# Testaus - voidaan ajaa suoraan: python analyzer.py

if __name__ == "__main__":
    import json

    print("=== GHOST.SYS analyzer.py testi ===\n")

    result = run_full_analysis()
    print(json.dumps(result, indent=2, ensure_ascii=False))