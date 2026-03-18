# GHOST.SYS - Resource Analytics Dashboard

Reaaliaikainen monitorointi dashboard rakennettu Python + FastAPI backendillä ja vanilla JavaScript frontendillä.

**Live demo:** [ghost-sys.onrender.com](https://ghost-sys-1.onrender.com) *(demo-moodi, simuloitu data)*

---

## Ominaisuudet

**Live metriikat** — CPU, muisti, levy ja verkkoliikenne päivittyvät 3 sekunnin välein

**Prosessitaulu** — näyttää top 10 prosessia CPU-käytön mukaan, zombie-prosessit korostettuna

**Bottleneck analyysi** — tunnistaa automaattisesti mikä resurssi on järjestelmän pullonkaula

**Memory leak -tunnistus** — analysoi muistin kasvutrendiä historiadatasta ja varoittaa jos kasvu on epänormaalia

**Levy-ennuste** — laskee nykyisen kasvuvauhdin perusteella milloin levy täyttyy

**Hälytykset** — automaattiset varoitukset kriittisistä tilanteista vakavuusjärjestyksessä

**7 päivän CPU-trendi** — Chart.js kaavio viikon keskiarvoista ja huipuista

**RAM-trendikäyrä** — viimeisen 2 tunnin muistin käyttö reaaliajassa

**Verkkoliikenne** — reaaliaikainen nopeus (KB/s / MB/s) sekä 24h yhteensä

---

## Teknologiat

**Backend**
- Python 3.11
- FastAPI — REST API ja staattisten tiedostojen tarjoilu
- psutil — järjestelmämetriikoiden lukeminen käyttöjärjestelmältä
- SQLite — historiadatan tallennus
- Uvicorn — ASGI-palvelin

**Frontend**
- Vanilla JavaScript — ei frameworkeja
- Chart.js — kaaviot
- CSS custom properties + clamp() — responsiivinen tyyli ilman kiinteitä pikselikokoja

---

## Rakenne

```
ghost-sys/
├── backend/
│   ├── main.py         # FastAPI sovellus, API-endpointit, taustatehtävät
│   ├── collector.py    # Metriikoiden keruu (live + demo-moodi)
│   ├── analyzer.py     # Analyysit: bottleneck, memory leak, zombie, ennusteet
│   └── database.py     # SQLite: tallennus, haku, siivous
├── frontend/
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
├── requirements.txt
└── render.yaml
```

---

## Ajaminen paikallisesti

```bash
# Kloonaa repo
git clone https://github.com/Jukkapalm/ghost-sys.git
cd ghost-sys

# Asenna riippuvuudet
pip install -r requirements.txt

# Käynnistä live-moodissa (lukee oikeat metriikat koneeltasi)
python backend/main.py

# TAI käynnistä demo-moodissa (simuloitu data)
$env:MODE="demo"; python backend/main.py  # PowerShell
MODE=demo python backend/main.py          # Linux/Mac
```

Avaa selaimessa: `http://localhost:8000`

---

## Moodit

**LIVE** — lukee oikeat metriikat psutil-kirjastolla suoraan käyttöjärjestelmältä

**DEMO** — generoi simuloitua dataa: CPU vaihtelee siniaaltomaisesti, muisti kasvaa hitaasti (memory leak -simulaatio), 3 zombie-prosessia valmiina

> Live demo Renderissä pyörii demo-moodissa koska ilmaisella palvelimella resurssit ovat minimaaliset.