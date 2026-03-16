# main.py - GHOST.SYS
# Tämä on sovelluksen pääohjelma, tämä käynnistää kaiken
# Käynnistää:
#   - FastAPI palvelimen
#   - määrittelee kaikki API-endpointit (URL-osoitteet joita frontend kutsuu)
#   - Käynnistää taustatehtävän joka kerää metriikat
#   - Siivoaa vanhan datan kerran päivässä automaattisesti
#   - Tarjoaa frontendille-tiedostot suoraan selaimeen

# Käynnistys:
#   -python main.py

import os
import asyncio
import uvicorn                              # Palvelin joka ajaa FastAPI-sovellusta
from fastapi import FastAPI                 # FastAPI-framework
from fastapi.staticfiles import StaticFiles # Tarjoaa frontend-tiedostot
from fastapi.responses import FileResponse  # Palauttaa HTML-tiedoston
from contextlib import asynccontextmanager  # Käynnistys/sammutus -hallinta

# Omat moduulit - tuodaan funktiot muista tiedostoista
from collector import collect_metrics
from database import init_db, save_metrics, get_history, get_weekly_summary, cleanup_old_data
from analyzer import run_full_analysis, get_alerts

# Taustatehtävät
# asyncio mahdollistaa tehtävien ajamisen "taustalla" samalla kun
# palvelin vastaa frontendin pyyntöihin. Ilman asynciota palvelin
# jumuituisi odottamaan jokaista mittausta.

async def collect_loop():

    # Taustatehtävä joka kerää metriikat joka 5.sekunti ja tallentaa ne
    # Pyörii koko ajan palvelimen käynnissä ollessa

    print("[COLLECTOR] Metriikoiden keruu käynnistetty - vali: 5s")

    while True:
        try:
            # Kerätään metriikat (live tai demo moodin mukaan)
            data = collect_metrics()

            # Tallennetaan tietokantaan
            save_metrics(data)

        except Exception as e:
            # Jos jokin menee pieleen, logitetaan virhe mutta ei kaadeta palvelinta
            print(f"[COLLECTOR] Virhe metriikoiden keräyksessä: {e}")

        # Odotetaan 5 sekuntia ennen seuraavaa mittausta
        # asyncio.sleep ei blokkaa palvelinta - muut pyynnöt toimivat nomraalisti
        await asyncio.sleep(5)

async def cleanup_loop():

    # Siivoaa vanhan datan kerran päivässä
    # Poistaa yli 30 päivää vanhat mittaukset tietokannasta

    print("[CLEANUP] Automaattinen siivous käynnistetty - väli: 24h")

    while True:
        # Odottaa 24 tuntia (86400 sekuntia)
        await asyncio.sleep(86400)

        try:
            cleanup_old_data(days=30)
        except Exception as e:
            print(f"[CLEANUP] Virhe siivouksessa: {e}")

# Sovelluksen käynnistys ja sammutus
# @asynccontextmanager-dekoraattori määrittelee mitä tapahtuu kun
# sovellus käynnistyy (yield ennen) ja sammutetaan (yield jälkeen).
@asynccontextmanager
async def lifespan(app: FastAPI):

    # Käynnistys
    print("\n" + "="*50)
    print("  GHOST.SYS käynnistyy...")
    print("="*50)

    # Alustetaan tietokanta (luo taulut jos ei ole)
    init_db()

    # Tarkistetaan moodi
    mode = os.getenv("MODE", "live").lower()
    print(f"[MODE] Käynnissä: {'DEMO (simuloitu data)' if mode == 'demo' else 'LIVE (oikea data)'}")
    print(f"[API]  http://localhost:8000")
    print(f"[DOCS] http://localhost:8000/docs")
    print("="*50 + "\n")

    # Käynnistetään taustatehtävät
    # asyncio.create_task käynnistää funktion taustalla — ei jää odottamaan
    collector_task = asyncio.create_task(collect_loop())
    cleanup_task   = asyncio.create_task(cleanup_loop())

    # yield = tästä kohtaa sovellus pyörii normaalisti
    yield

    # --- SAMMUTUS ---
    # Tänne tullaan kun palvelin sammutetaan (Ctrl+C)
    print("\n[GHOST.SYS] Sammutetaan...")
    collector_task.cancel()
    cleanup_task.cancel()

# FASTAPI-sovellus
# Luodaan FastAPI-instanssi joka hallitsee kaikkia pyyntöjä
# lifespan-paramatri kertoo mitä tehdään käynnistyksessä ja sammutuksessa

app = FastAPI(
    title = "GHOST.SYS API",
    description = "Resource Analytics Dashboard - Server Metrics API",
    version = "0.1.0",
    lifespan = lifespan
)

# API -endpointit
# Endpoint = URL-osoite johon frontend lähettää pyyntöjä
# @app.get("/polku") määrittelee että tämä funktio vastaa GET-pyyntöihin.

# FastAPI muuntaa automaattisesti Python-dictionaryt JSON-vastauksiksi

@app.get("/api/metrics")
async def api_metrics():

    # Palauttaa viimeisimmät metriikat
    # Frontend kutsuu tätä joka 3. sekunti päivittääkseen live-näkymän
    # Palautus: CPU, RAM, levy, verkko ja prosessitiedot

    return collect_metrics()

@app.get("/api/history")
async def api_history(hours: int = 24):

    # Palauttaa historiadatan trendikaaviota varten
    # Parametri: hours: kuinka monen tunnin historia palautetaan (oletus: 24)
    # Palautus: lista mittauksista aikajärjestyksessä

    return get_history(hours=hours)

@app.get("/api/weekly")
async def api_weekly():

    # Palauttaa viimeisen 7 päivän päiväkohtaiset yhteenvedot
    # Käytetään viikko trendi kaaviossa
    # Palautus: lista päiväkohtaisista keskiarvoista ja huippuarvoista

    return get_weekly_summary()

@app.get("/api/analysis")
async def api_analysis():

    # Palauttaa täyden analyysin - zombie-prosessit, memory leak, bottleneck, CPU-trendi ja levy-ennuste
    # Palautus: dictionary jossa kaikki analyysitulokset

    return run_full_analysis()

@app.get("/api/alerts")
async def api_alerts():

    # Palauttaa aktiiviset hälyytykset vakavuusjärjestyksessä
    # Frontend näyttää nämä hälytys-paneelissa
    # Palautus: lista hälytyksiä - kriittiset ensin

    current = collect_metrics()
    history = get_history(hours=24)
    return get_alerts(current, history)

@app.get("/api/status")
async def api_status():

    # Yksinkertainen status-endpoint - kertoo onko palvelin käynnissä
    # Hyödyllinen esim Renderin health check -tarkistuksiin
    # Palautus: {"status": "ok", "mode": "live/demo"}

    mode = os.getenv("MODE", "live").lower()
    return {
        "status": "ok",
        "mode": mode,
        "version": "0.1.0"
    }

# Frontend-tiedostojen tarjoilu
# StaticFiles tarjoaa frontend-kansion tiedostot suoraan selaimelle.
# Tämä tarkoittaa että erillinen web-palvelin (nginx jne.) ei tarvita —
# FastAPI hoitaa kaiken itse.

# Lasketaan frontend-kansion polku
# backend/main.py → .. → ghost-sys/ → frontend/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# Tarjotaan frontend-kansio /static-polusta
# Tämä mahdollistaa esim. /static/style.css ja /static/app.js
#app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
async def root():

    # Juuriosoite - palauttaa dashboard-sivun (index.html)
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    return FileResponse(index_path)

# Käynnistys
# Tämä lohko suoritetaan kun ajat: python main.py
# uvicorn on ASGI-palvelin joka ajaa FastAPI-sovellusta.
# host="0.0.0.0"  → kuuntelee kaikilla verkkorajapinnoilla
#                   (tarvitaan Renderissä jotta se on saavutettavissa)
# port=8000       → portti johon yhdistetään
# reload=False    → ei automaattista uudelleenkäynnistystä tuotannossa

if __name__ == "__main__":
    uvicorn.run(
        "main:app",      # "tiedostonimi:FastAPI-instanssin nimi"
        host = "0.0.0.0",
        port = 8000,
        reload = False,
        log_level="debug"
    )