# main.py - GHOST.SYS
# Tämä on sovelluksen pääohjelma, tämä käynnistää kaiken
# Käynnistää:
#   - FastAPI palvelimen
#   - määrittelee kaikki API-endpointit (URL-osoitteet joita frontend kutsuu)
#   - Käynnistää taustatehtävän joka kerää metriikat
#   - Siivoaa vanhan datan kerran päivässä automaattisesti
#   - Tarjoaa frontendille-tiedostot suoraan selaimeen


import os
import asyncio
import psutil as _psutil
import uvicorn                          
from fastapi import FastAPI                
from fastapi.staticfiles import StaticFiles 
from contextlib import asynccontextmanager 

# Omat moduulit - tuodaan funktiot muista tiedostoista
from collector import collect_metrics
from database import init_db, save_metrics, get_history, get_weekly_summary, cleanup_old_data, get_network_24h
from analyzer import run_full_analysis, get_alerts

# Taustatehtävät

async def collect_loop():

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
@asynccontextmanager
async def lifespan(app: FastAPI):

    # Käynnistys
    print("\n" + "="*50)
    print("  GHOST.SYS käynnistyy...")
    print("="*50)

    # Alustetaan tietokanta (luo taulut jos ei ole)
    init_db()

    _net = _psutil.net_io_counters()
    os.environ['NET_START_SENT'] = str(_net.bytes_sent)
    os.environ['NET_START_RECV'] = str(_net.bytes_recv)

    # Tarkistetaan moodi
    mode = os.getenv("MODE", "live").lower()
    print(f"[MODE] Käynnissä: {'DEMO (simuloitu data)' if mode == 'demo' else 'LIVE (oikea data)'}")
    print(f"[API]  http://localhost:8000")
    print(f"[DOCS] http://localhost:8000/docs")
    print("="*50 + "\n")

    # Käynnistetään taustatehtävät
    collector_task = asyncio.create_task(collect_loop())
    cleanup_task   = asyncio.create_task(cleanup_loop())

    yield

    # SAMMUTUS
    print("\n[GHOST.SYS] Sammutetaan...")
    collector_task.cancel()
    cleanup_task.cancel()

# FASTAPI-sovellus
app = FastAPI(
    title = "GHOST.SYS API",
    description = "Resource Analytics Dashboard - Server Metrics API",
    version = "0.1.0",
    lifespan = lifespan
)

# API -endpointit
@app.get("/api/metrics")
async def api_metrics():

    # Palauttaa viimeisimmät metriikat
    return collect_metrics()

@app.get("/api/history")
async def api_history(hours: int = 24):

    # Palauttaa historiadatan trendikaaviota varten
    return get_history(hours=hours)

@app.get("/api/network24h")
async def api_network24h():

    # Palauttaa verkkoliikenteen viimeiseltä 24h
    return get_network_24h()

@app.get("/api/weekly")
async def api_weekly():

    # Palauttaa viimeisen 7 päivän päiväkohtaiset yhteenvedot
    return get_weekly_summary()

@app.get("/api/analysis")
async def api_analysis():

    # Palauttaa täyden analyysin - zombie-prosessit, memory leak, bottleneck, CPU-trendi ja levy-ennuste
    return run_full_analysis()

@app.get("/api/alerts")
async def api_alerts():

    # Palauttaa aktiiviset hälyytykset vakavuusjärjestyksessä
    current = collect_metrics()
    history = get_history(hours=24)
    return get_alerts(current, history)

@app.get("/api/status")
async def api_status():

    # Yksinkertainen status-endpoint - kertoo onko palvelin käynnissä
    mode = os.getenv("MODE", "live").lower()
    return {
        "status": "ok",
        "mode": mode,
        "version": "0.1.0"
    }

# Lasketaan frontend-kansion polku
# backend/main.py → .. → ghost-sys/ → frontend/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
if not os.path.exists(FRONTEND_DIR):
    print(f"[ERROR] Frontend-kansiota ei löydy: {FRONTEND_DIR}")
    print(f"[ERROR] BASE_DIR on: {BASE_DIR}")
    print(f"[ERROR] Tiedostot BASE_DIR:ssä: {os.listdir(BASE_DIR)}")


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

# Käynnistys
if __name__ == "__main__":
    uvicorn.run(
        "main:app",    
        host = "0.0.0.0",
        port = 8000,
        reload = False,
        log_level="info"
    )