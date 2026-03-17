# database.py - GHOST.SYS
# Tämä tiedosto vastaa kaikesta historian tallentamisesta SQLite-tietokantaan
# Tämä tiedosto luo tietokannan ja taulut jos niitä ei vielä ole
# Tallentaa metriikat tietokantaan joka 5. sekunti
# Hakee historian trendejä varten ( esim. viimeinen 24h tai 7 päivää)
# Siivoaa kaiken yli 30 päivän vanhan datan, näin tietokanta ei kasva liian isoksi
# SQLite-tietokanta tallennetaan projektin juureen tiedostoon ghost-sys.db
# Tiedosto luodaan automaattisesti kun ohjelma käynnistetään ensimmäisen kerran

import sqlite3
import os
from datetime import datetime, timedelta

# Tietokannan sijainti
# Tallentuu projektin juurikansioon

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "ghost-sys.db")

# Tietokanta yhteyden avaaminen
# SQLite luo tietokannan jos sitä ei ole olemassa
def get_connection() -> sqlite3.Connection:

    # Avaa ja palauttaa yhteyden tietokantaan
    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row

    return conn

# Taulujen luominen
# Tätä funktiota kutsutaan kerran kun ohjelma käynnistyy
# "CREATE TABLE IF NOT EXISTS" tarkoittaa että taulu luodaan vain
def init_db():

    conn = get_connection()

    # with-lohko huolehtii että yhteys suljetaan automaattisesti lopussa
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                mode TEXT NOT NULL,
                     
                -- CPU
                cpu_percent REAL NOT NULL,
                cpu_count INTEGER NOT NULL,
                cpu_status TEXT NOT NULL,
                     
                -- RAM / Muisti
                ram_percent REAL NOT NULL,
                ram_used_gb REAL NOT NULL,
                ram_total_gb REAL NOT NULL,
                ram_status TEXT NOT NULL,
                     
                -- Levy
                disk_percent REAL NOT NULL,
                disk_used_gb REAL NOT NULL,
                disk_total_gb REAL NOT NULL,
                disk_read_mb REAL NOT NULL,
                disk_write_mb REAL NOT NULL,
                disk_status TEXT NOT NULL,
                     
                -- Verkko
                net_sent_mb REAL NOT NULL,
                net_recv_mb REAL NOT NULL,
                     
                -- Prosessit
                process_total INTEGER NOT NULL,
                process_zombie INTEGER NOT NULL
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_timestamp
            ON metrics (timestamp)
        """)

    conn.commit()
    conn.close()
    print(f"[DB] Tietokanta alustettu: {DB_PATH}")

# Metriikoiden tallennus
def save_metrics(data: dict):

    conn = get_connection()

    with conn:
        conn.execute("""
            INSERT INTO metrics (
                timestamp, mode,
                cpu_percent, cpu_count, cpu_status,
                ram_percent, ram_used_gb, ram_total_gb, ram_status,
                disk_percent, disk_used_gb, disk_total_gb,
                disk_read_mb, disk_write_mb, disk_status,
                net_sent_mb, net_recv_mb,
                process_total, process_zombie
            ) VALUES (
                :timestamp, :mode,
                :cpu_percent, :cpu_count, :cpu_status,
                :ram_percent, :ram_used_gb, :ram_total_gb, :ram_status,
                :disk_percent, :disk_used_gb, :disk_total_gb,
                :disk_read_mb, :disk_write_mb, :disk_status,
                :net_sent_mb, :net_recv_mb,
                :process_total, :process_zombie
            )
        """, {
            # Ylätason kentät
            "timestamp":      data["timestamp"],
            "mode":           data["mode"],

            # CPU — luetaan sisäkkäisestä dictionarysta
            "cpu_percent":    data["cpu"]["percent"],
            "cpu_count":      data["cpu"]["count"],
            "cpu_status":     data["cpu"]["status"],

            # RAM
            "ram_percent":    data["ram"]["percent"],
            "ram_used_gb":    data["ram"]["used_gb"],
            "ram_total_gb":   data["ram"]["total_gb"],
            "ram_status":     data["ram"]["status"],

            # Levy
            "disk_percent":   data["disk"]["percent"],
            "disk_used_gb":   data["disk"]["used_gb"],
            "disk_total_gb":  data["disk"]["total_gb"],
            "disk_read_mb":   data["disk"]["read_mb"],
            "disk_write_mb":  data["disk"]["write_mb"],
            "disk_status":    data["disk"]["status"],

            # Verkko
            "net_sent_mb":    data["network"]["sent_mb"],
            "net_recv_mb":    data["network"]["recv_mb"],

            # Prosessit
            "process_total":  data["processes"]["total"],
            "process_zombie": data["processes"]["zombie"],
        })

    conn.close()

# Historian haku trendejä varten
def get_history(hours: int = 24) -> list:

    conn = get_connection()

    since = (datetime.now() - timedelta(hours=hours)).isoformat()

    cursor = conn.execute("""
        SELECT
            timestamp,
            cpu_percent,
            ram_percent,
            disk_percent,
            net_sent_mb,
            net_recv_mb,
            process_zombie
        FROM metrics
        WHERE timestamp >= ?
        ORDER BY timestamp ASC
    """, (since,))

    # Muunnetaan sqlite3.Row-oliot tavalliseksi dictionaryiksi
    rows = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return rows

# Viikko yhteenveto - 7 päivänpäiväkohtaiset keskiarvot
def get_weekly_summary() -> list:

    conn = get_connection()

    cursor = conn.execute("""
        SELECT
            DATE(timestamp) AS day,
            ROUND(AVG(cpu_percent), 1) AS cpu_avg,
            ROUND(MAX(cpu_percent), 1) AS cpu_peak,
            ROUND(AVG(ram_percent), 1) AS ram_avg,
            ROUND(MAX(ram_percent), 1) AS ram_peak,
            ROUND(AVG(disk_percent), 1) AS disk_avg,
            SUM(process_zombie) AS total_zombies
        FROM metrics
        WHERE timestamp >= DATE('now', '-7 days')
        GROUP BY DATE(timestamp)
        ORDER BY day ASC
    """)

    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_network_24h() -> dict:

    # Laskee verkkoliikenteen viimeisen 24h aikana
    conn = get_connection()
    since = (datetime.now() - timedelta(hours=24)).isoformat()

    result = conn.execute("""
        SELECT 
            ROUND(SUM(net_sent_mb), 1) AS total_sent,
            ROUND(SUM(net_recv_mb), 1) AS total_recv
        FROM metrics
        WHERE timestamp >= ?
    """, (since,)).fetchone()

    conn.close()

    if not result or result["total_sent"] is None:
        return {"sent_mb": 0, "recv_mb": 0}
    
    return {
        "sent_mb": result["total_sent"],
        "recv_mb": result["total_recv"]
    }

# Vanhan datan siivous
def cleanup_old_data(days: int = 30):

    conn = get_connection()

    # DATE('now', '-30 days') laskee päivämäärän 30 päivää sitten
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    with conn:
        cursor = conn.execute("""
            DELETE FROM metrics
            WHERE timestamp < ?
        """, (cutoff,))

        deleted = cursor.rowcount

    conn.close()

    if deleted > 0:
        print(f"[DB] Siivous: poistettiin {deleted} vanhaa mittausta (>{days} päivää)")

def get_db_stats() -> dict:

    # Palauttaa tietokannan perustilastot
    conn = get_connection()

    # Rivien kokonaismäärä
    total = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]

    # Vanhin ja uusin mittaus
    oldest = conn.execute("SELECT MIN(timestamp) FROM metrics").fetchone()[0]
    newest = conn.execute("SELECT MAX(timestamp) FROM metrics").fetchone()[0]

    # Tietokantatiedoston koko
    db_size_mb = round(os.path.getsize(DB_PATH) / (1024**2), 2) if os.path.exists(DB_PATH) else 0

    conn.close()

    return {
        "total_rows": total,
        "oldest": oldest,
        "newest": newest,
        "db_size_mb": db_size_mb,
        "db_path": DB_PATH
    }

if __name__ == "__main__":
    import json
    from collector import collect_metrics # Tuodaan collector testi dataa varten

    print("=== GHOST.SYS database.py testi ===\n")

    # 1. Alustetaan tietokanta
    print("1. Alustetaan tietokanta...")
    init_db()

    # 2. Kerätään muutama testimittaus ja tallennetaan
    print("\n2. Tallennetaan 3 testimittausta...")
    for i in range(3):
        data = collect_metrics()
        save_metrics(data)
        print(f"   Tallennettu mittaus {i+1}: CPU {data['cpu']['percent']}%")

    # 3. Haetaan historia
    print("\n3. Haetaan viimeinen 24h historia...")
    history = get_history(hours=24)
    print(f"   Löytyi {len(history)} mittausta")

    # 4. Tietokannan tilastot
    print("\n4. Tietokannan tilastot:")
    stats = get_db_stats()
    print(json.dumps(stats, indent=2, ensure_ascii=False))

    print("\n[OK] database.py toimii!")