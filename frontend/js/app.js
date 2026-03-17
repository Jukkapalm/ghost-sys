// app.js - GHOST.SYS
// Vastaa frontendin toiminnasta
//  - Hakee dataa backendistä (polling joka 3 sekunti)
//  - Päivittää live mittarit(CPU, RAM, levy, verkko)
//  - Piirtää Chart.js grafiikat (CPU terendi, RAM trendi)
//  - Näyttää prosessitaulun zombie-prosesseineen
//  - Näyttää hälytykset vakavuusjärjestyksessä
//  - Päivittää temrinaali-lokin

// CONFIG - asetukset
const CONFIG = {
    api: {
        metrics: '/api/metrics',
        history: '/api/history',
        weekly: '/api/weekly',
        analysis: '/api/analysis',
        alerts: '/api/alerts',
        status: '/api/status',
        network24h: '/api/network24h',
    },

    // Päivitysväli millisekunteina
    pollInterval: 3000,
    analysisInterval: 15000,
    chartInterval: 30000,

    // Värikoodit
    colors: {
        ok: '#00ff41',
        warning: '#ffb800',
        critical: '#ff3333',
        purple: '#c84fff',
    }
};

// State - sovelluksen tila
// Tallennetaan Chart.JS-instanssit ja viimeisin data
const STATE = {
    cpuChart: null,
    ramChart: null,
    lastData: null,

    prevNetSent: null,
    prevNetRecv: null,
    prevNetTime: null,
};

// Apufunktio - palauttaa värin käyttöasteen perusteella
function getStatusColor(percent) {
    if (percent >= 85) return CONFIG.colors.critical;
    if (percent >= 65) return CONFIG.colors.warning;
    return CONFIG.colors.ok;
}

// Apufunktio - lisää viestin terminaali-lokiin
function addTerminalLog(type, message) {
    const el = document.getElementById('terminal-log');
    if (!el) return;

    const tags = {
        ok: '<span class="log-ok">[OK]</span>',
        warn: '<span class="log-warn">[WARN]</span>',
        err: '<span class="log-err">[ALERT]</span>',
        sys: '<span class="log-sys">[SYS]</span>',
    };

    const tag = tags[type] || tags.sys;
    const time = new Date().toLocaleTimeString('fi-FI');

    el.innerHTML = `${tag} ${message} <span class="text-muted">· ${time}</span> <span class="terminal-cursor"></span>`;
}

// Käynnistää kellon joka päivittyy joka sekunti
function startClock() {
    function tick() {
        const el = document.getElementById('clock');
        if (el) el.textContent = new Date().toLocaleTimeString('fi-FI');
    }
    tick();
    setInterval(tick, 1000);
}

// API funktiot
// Hakee dataa annetusta URL:sta ja palauttaa JSON
// Palauttaa null jos jotain menee pieleen
async function fetchData(url) {
    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error(`[GHOST.SYS] Fetch virhe (${url}):`, error);
        addTerminalLog('err', `Yhteys backendiin katkesi - yritetään uudelleen`);
        return null;
    }
}

// UI päivitys funktiot live mittareille
function updateMetricCards(data) {

    // CPU
    const cpuPct = data.cpu.percent;
    const cpuColor = getStatusColor(cpuPct);

    const cpuVal = document.getElementById('cpu-value');
    if (cpuVal) { cpuVal.textContent = `${cpuPct}%`; cpuVal.style.color = cpuColor; }

    const cpuBar = document.getElementById('cpu-bar');
    if (cpuBar) { cpuBar.style.width = `${cpuPct}%`; cpuBar.style.background = cpuColor; }

    const cpuCard = document.getElementById('cpu-card');
    if (cpuCard) cpuCard.style.borderTopColor = cpuColor;

    const cpuSub = document.getElementById('cpu-sub');
    if (cpuSub) cpuSub.textContent = `${data.cpu.count} cores`;

    // RAM
    const ramPct   = data.ram.percent;
    const ramColor = getStatusColor(ramPct);

    const ramVal = document.getElementById('ram-value');
    if (ramVal) { ramVal.textContent = `${ramPct}%`; ramVal.style.color = ramColor; }

    const ramBar = document.getElementById('ram-bar');
    if (ramBar) { ramBar.style.width = `${ramPct}%`; ramBar.style.background = ramColor; }

    const ramCard = document.getElementById('ram-card');
    if (ramCard) ramCard.style.borderTopColor = ramColor;

    const ramSub = document.getElementById('ram-sub');
    if (ramSub) ramSub.textContent = `${data.ram.used_gb} / ${data.ram.total_gb} GB`;

    // Levy
    const diskPct   = data.disk.percent;
    const diskColor = getStatusColor(diskPct);

    const diskVal = document.getElementById('disk-value');
    if (diskVal) { diskVal.textContent = `${diskPct}%`; diskVal.style.color = diskColor; }

    const diskBar = document.getElementById('disk-bar');
    if (diskBar) { diskBar.style.width = `${diskPct}%`; diskBar.style.background = diskColor; }

    const diskCard = document.getElementById('disk-card');
    if (diskCard) diskCard.style.borderTopColor = diskColor;

    const diskSub = document.getElementById('disk-sub');
    if (diskSub) diskSub.textContent = `${data.disk.used_gb} / ${data.disk.total_gb} GB`;

    // Verkko
    const netBar = document.getElementById('net-bar');
    if (netBar) {
        const netPct = Math.min(100, (data.network.recv_mb / 1000) * 100);
        netBar.style.width      = `${netPct}%`;
        netBar.style.background = CONFIG.colors.ok;
    }

    // Verkko-panelin isot arvot - lasketaan reaaliaikainen nopeus
    const nowTime = Date.now();
    const sentNow = data.network.sent_mb;
    const recvNow =data.network.recv_mb;

    const netUp = document.getElementById('net-up');
    const netDown = document.getElementById('net-down');

    // Alle 1 MB/s näytetään KB/s jotta luvut pysyvät luettavina
    function formatSpeed(mbps) {
        if (mbps >= 1)    return `${mbps.toFixed(1)} MB/s`;
        if (mbps >= 0.01) return `${(mbps * 1024).toFixed(0)} KB/s`;
        return '0 KB/s';
    }

    if (STATE.prevNetTime !== null && (nowTime - STATE.prevNetTime) > 500) {
        // Kuinka monta sekuntia edellisestä mittauksesta kului
        const deltaSec  = (nowTime - STATE.prevNetTime) / 1000;

        // Kuinka paljon dataa siirtyi välissä (ei voi olla negatiivinen)
        const deltaSent = Math.max(0, sentNow - STATE.prevNetSent);
        const deltaRecv = Math.max(0, recvNow  - STATE.prevNetRecv);

        // Nopeus = siirretty data / aika
        const speedSent = deltaSent / deltaSec;
        const speedRecv = deltaRecv / deltaSec;

        if (netUp)   netUp.textContent   = formatSpeed(speedSent);
        if (netDown) netDown.textContent = formatSpeed(speedRecv);

        const netVal = document.getElementById('net-value');
        if (netVal) netVal.textContent = `↑${formatSpeed(speedSent)} ↓${formatSpeed(speedRecv)}`;

    } else {
        // Ensimmäinen mittaus - ei vielä vertailukohtaa
        if (netUp)   netUp.textContent   = '-- KB/s';
        if (netDown) netDown.textContent = '-- KB/s';

        const netVal = document.getElementById('net-value');
        if (netVal) netVal.textContent = '↑-- ↓--';
    }

    // Tallennetaan tämä mittaus seuraavaa vertailua varten
    STATE.prevNetSent = sentNow;
    STATE.prevNetRecv = recvNow;
    STATE.prevNetTime = nowTime;
}

// Päivittää prosessitaulun
// Zombiet tulevat punaisella
function updateProcessTable(data) {
    const tbody = document.getElementById('process-tbody');
    if (!tbody) return;

    const zombieCount = data.processes.zombie;

    // Zombie badge
    const zombieBadge = document.getElementById('zombie-badge');
    if (zombieBadge) {
        zombieBadge.textContent = `${zombieCount} ZOMBIE`;
        zombieBadge.className   = zombieCount > 0 ? 'panel-badge red' : 'panel-badge';
    }

    // Tyhjennetään ja rakennetaan taulu uudelleen
    tbody.innerHTML = '';

    data.processes.top.forEach(proc => {
        const row       = document.createElement('tr');
        if (proc.zombie) row.className = 'zombie';

        const cpuColor = getStatusColor(proc.cpu);

        // Muisti näytetään G jos yli 1024M
        const memText = proc.mem_mb > 1024 ? `${(proc.mem_mb / 1024).toFixed(1)}G` : `${proc.mem_mb}M`;

        // Status - zombie saa Z-badgen, muut R tai S
        const statusHtml = proc.zombie ? '<span class="zombie-badge">Z</span>' : `<span style="color: ${CONFIG.colors.ok}">${proc.status === 'running' ? 'R' : 'S'}</span>`;

        row.innerHTML = `
            <td class="text-muted">${proc.pid}</td>
            <td class="text-purple">${proc.name || '—'}</td>
            <td style="color: ${cpuColor}">${proc.cpu}%</td>
            <td>${memText}</td>
            <td>${statusHtml}</td>
        `;

        tbody.appendChild(row);
    });

    addTerminalLog('sys', `${data.processes.total} prosessia · ${zombieCount} zombie`);
}

// Päivittää hälytys-panelin
function updateAlerts(alerts) {
    const list = document.getElementById('alerts-list');
    const dot = document.getElementById('alert-dot');
    const countEl = document.getElementById('alert-count');

    if (!list) return;

    // Hälytykset yläpalkissa
    if (countEl) {
        countEl.textContent = alerts.length;
        countEl.style.color = alerts.length > 0 ? CONFIG.colors.critical : CONFIG.colors.ok;
    }

    // Vilkkuva piste vain kriittisillä hälytyksillä
    const hasCritical = alerts.some(a => a.severity === 'critical');
    if (dot) dot.className = hasCritical ? 'alert-dot' : 'alert-dot hidden';

    if (alerts.length === 0) {
        list.innerHTML = '<div class="no-alerts">Ei aktiivisia hälytyksiä ✓</div>';
        return;
    }

    list.innerHTML = '';

    const tagNames = { critical: 'KRIITTINEN', warning: 'VAROITUS', info: 'INFO' };

    alerts.forEach(alert => {
        const item      = document.createElement('div');
        item.className  = `alert-item ${alert.severity}`;
        item.innerHTML = `
            <div class="alert-tag">${tagNames[alert.severity] || alert.severity}</div>
            <div class="alert-msg">${alert.message}</div>
            <div class="alert-time">${alert.type}</div>
        `;
        list.appendChild(item);
    });

    // Kriittiset terminaaliin
    const critical = alerts.filter(a => a.severity === 'critical');
    if (critical.length > 0) addTerminalLog('err', critical[0].message);
}

// Päivittää bottleneckin analyysin
function updateBottleneck(analysis) {
    const list  = document.getElementById('bottleneck-list');
    const msg   = document.getElementById('bottleneck-msg');
    const badge = document.getElementById('bottleneck-badge');

    if (!list || !analysis.bottleneck) return;

    const bk = analysis.bottleneck;

    if (badge) {
        badge.textContent = `▲ ${bk.bottleneck}`;
        badge.className   = `panel-badge ${bk.severity === 'critical' ? 'red' : bk.severity === 'warning' ? 'yellow' : 'green'}`;
    }

    list.innerHTML = '';

    bk.all.forEach(resource => {
        const color = getStatusColor(resource.percent);
        const row   = document.createElement('div');
        row.className = 'bk-row';
        row.innerHTML = `
            <div class="bk-name">${resource.name}</div>
            <div class="bk-track">
                <div class="bk-fill" style="width: 0%; background: ${color}" data-width="${resource.percent}"></div>
            </div>
            <div class="bk-pct" style="color: ${color}">${resource.percent}%</div>
        `;
        list.appendChild(row);

        // Animoidaan bar sisään - setTimeout mahdollistaa CSS-transition
        setTimeout(() => {
            const fill = row.querySelector('.bk-fill');
            if (fill) fill.style.width = `${resource.percent}%`;
        }, 100);
    });

    if (msg) msg.textContent = bk.message;
}

// Päivittää levytila panelin
function updateDiskDetails(data, analysis) {
    const container = document.getElementById('disk-details');
    const badge = document.getElementById('disk-forecast-badge');

    if (!container) return;

    container.innerHTML = '';

    // Ennuste badge
    if (badge && analysis.disk_forecast) {
        const f = analysis.disk_forecast;
        badge.textContent = f.days_until_90 ? `${f.days_until_90}pv → 90%` : f.severity === 'critical' ? 'KRIITTINEN' : 'OK';
        badge.className = `panel-badge ${f.severity === 'critical' ? 'red' : f.severity === 'warning' ? 'yellow' : 'green'}`;
    }

    // Levy bar
    const diskPct   = data.disk.percent;
    const diskColor = getStatusColor(diskPct);

    container.innerHTML = `
        <div class="disk-row">
            <div class="disk-name">C:\\ levy</div>
            <div class="disk-track">
                <div class="disk-fill" style="width: ${diskPct}%; background: ${diskColor}"></div>
            </div>
            <div class="disk-pct" style="color: ${diskColor}">${diskPct}%</div>
        </div>
        ${analysis.disk_forecast ? `<div class="disk-forecast-msg">${analysis.disk_forecast.message}</div>` : ''}
        <div style="margin-top: var(--gap-sm); display: flex; gap: var(--gap-lg);">
            <span class="text-muted" style="font-size: var(--fs-xs)">READ <span class="text-green">${data.disk.read_mb} MB</span></span>
            <span class="text-muted" style="font-size: var(--fs-xs)">WRITE <span class="text-purple">${data.disk.write_mb} MB</span></span>
        </div>
    `;
}

// Päivittää memory leak analyysin
function updateMemoryAnalysis(analysis) {
    const msg   = document.getElementById('leak-msg');
    const badge = document.getElementById('leak-badge');

    if (!analysis.memory_leak) return;

    const leak = analysis.memory_leak;

    if (badge) {
        badge.textContent = leak.detected ? 'LEAK HAVAITTU' : 'OK';
        badge.className   = `panel-badge ${leak.detected ? (leak.severity === 'critical' ? 'red' : 'yellow') : 'green'}`;
    }

    if (msg) {
        msg.textContent = leak.days_until_full ? `${leak.message} · Täyttyy ~${leak.days_until_full} päivässä` : leak.message;
    }
}

// Chart.JS grafiikat
// Luo CPU-viikkotrendi-kaavion (pylväs + viiva)
// Kutsutaan kertaalleen, sen jälkeen vain datan päivitys
function initCpuChart() {
    const canvas = document.getElementById('cpu-chart');
    if (!canvas) return;

    STATE.cpuChart = new Chart(canvas, {
        type: 'bar',
        data: {
            labels: ['Ma', 'Ti', 'Ke', 'To', 'Pe', 'La', 'Su'],
            datasets: [
                {
                    // Pylväät = päivän keskiarvo
                    label: 'CPU keskiarvo %',
                    data: [0, 0, 0, 0, 0, 0, 0],
                    backgroundColor: '#c84fff44',
                    borderColor: '#c84fff',
                    borderWidth: 1,
                    borderRadius: 2,
                },
                {
                    // Viiva = päivän huippu
                    label: 'CPU huippu %',
                    data: [0, 0, 0, 0, 0, 0, 0],
                    backgroundColor: 'transparent',
                    borderColor: '#ff333388',
                    borderWidth: 1,
                    type: 'line',
                    pointRadius: 3,
                    pointBackgroundColor: '#ff3333',
                    tension: 0.3,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    labels: { color: '#7a70a0', font: { size: 11 }, boxWidth: 10 }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#7a70a0', font: { size: 11 } },
                    grid: { color: '#1a1a30' },
                },
                y: {
                    min: 0, max: 100,
                    ticks: { color: '#7a70a0', font: { size: 11 }, callback: v => `${v}%` },
                    grid: { color: '#1a1a3066' },
                }
            }
        }
    });
}

// Luo RAM-trendi käyrän (line chart)
function initRamChart() {
    const canvas = document.getElementById('ram-chart');
    if (!canvas) return;

    STATE.ramChart = new Chart(canvas, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'RAM %',
                data: [],
                borderColor: '#c84fff',
                backgroundColor: '#c84fff22',
                borderWidth: 1.5,
                pointRadius: 0,   // Ei pisteitä — siisti viiva
                tension: 0.4,
                fill: true,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: { legend: { display: false } },
            scales: {
                x: { display: false },
                y: {
                    min: 0, max: 100,
                    ticks: { color: '#7a70a0', font: { size: 10 }, callback: v => `${v}%`, maxTicksLimit: 4 },
                    grid: { color: '#1a1a3066' },
                }
            }
        }
    });
}

// Päivittää CPU-viikkokaavion datalla
function updateCpuChart(weeklyData) {
    if (!STATE.cpuChart || !weeklyData || weeklyData.length === 0) return;

    const dayNames = ['Su', 'Ma', 'Ti', 'Ke', 'To', 'Pe', 'La'];

    const labels = weeklyData.map(d => dayNames[new Date(d.day).getDay()]);
    const avgData = weeklyData.map(d => d.cpu_avg);
    const peakData = weeklyData.map(d => d.cpu_peak);
    // Pylväsvärit käyttöasteen mukaan — korkeat punaisella
    const barColors = avgData.map(v => getStatusColor(v) + '88');

    STATE.cpuChart.data.labels = labels;
    STATE.cpuChart.data.datasets[0].data = avgData;
    STATE.cpuChart.data.datasets[0].backgroundColor = barColors;
    STATE.cpuChart.data.datasets[0].borderColor = avgData.map(v => getStatusColor(v));
    STATE.cpuChart.data.datasets[1].data = peakData;
    STATE.cpuChart.update('none');  // 'none' = ei animaatiota päivityksessä
}

// Päivittää RAM-trendikäyrän historiadatalla
function updateRamChart(historyData) {
    if (!STATE.ramChart || !historyData || historyData.length === 0) return;

    // Otetaan max 60 pistettä — enemmän ei mahdu siististi
    const recent = historyData.slice(-60);
    const labels = recent.map(d => new Date(d.timestamp).toLocaleTimeString('fi-FI', { hour: '2-digit', minute: '2-digit' }));
    const ramData = recent.map(d => d.ram_percent);

    STATE.ramChart.data.labels = labels;
    STATE.ramChart.data.datasets[0].data = ramData;
    STATE.ramChart.update('none');
}

// Polling - säännölliset datahaut
// Live metriikat kutsutaan joka 3s
async function pollMetrics() {
    const data = await fetchData(CONFIG.api.metrics);
    if (!data) return;
    STATE.lastData = data;
    updateMetricCards(data);
    updateProcessTable(data);
}

// Analyysit ja hälytykset
// Kutsutaan joka 15s
async function pollAnalysis() {
    const alerts = await fetchData(CONFIG.api.alerts);
    if (alerts) updateAlerts(alerts);

    const analysis = await fetchData(CONFIG.api.analysis);
    if (analysis && STATE.lastData) {
        updateBottleneck(analysis);
        updateDiskDetails(STATE.lastData, analysis);
        updateMemoryAnalysis(analysis);
    }

    const net24h = await fetchData(CONFIG.api.network24h);
    if (net24h) {
        const netTotal = document.getElementById('net-total');
        if (netTotal) netTotal.textContent = `24h: ↑${net24h.sent_mb} MB · ↓${net24h.recv_mb} MB`;
    }
}

// Grafiikat
// Kutsutaan joka 30s
async function pollCharts() {
    const weekly = await fetchData(CONFIG.api.weekly);
    if (weekly) updateCpuChart(weekly);
 
    const history = await fetchData(`${CONFIG.api.history}?hours=2`);
    if (history) updateRamChart(history);
}

// Init käynnistää kaiken
async function init() {
    console.log('[GHOST.SYS] Käynnistyy...');
    addTerminalLog('sys', 'GHOST.SYS käynnistyy — yhdistetään backendiin...');

    // Kello käyntiin
    startClock();

    // Alustetaan grafiikat
    initCpuChart();
    initRamChart();

    // Tarkistetaan yhteys
    const status = await fetchData(CONFIG.api.status);
    if (status) {
        const modeEl = document.getElementById('mode-indicator');
        if (modeEl) modeEl.textContent = status.mode === 'demo' ? 'DEMO' : 'LIVE';
        addTerminalLog('ok', `Yhteys OK · moodi: ${status.mode.toUpperCase()} · v${status.version}`);
    }

    // Ensimmäinen haku heti — ei odoteta intervalleja
    await pollMetrics();
    await pollAnalysis();
    await pollCharts();

    // Käynnistetään säännölliset haut
    // setInterval toistaa funktiota annetun millisekuntimäärän välein
    setInterval(pollMetrics,  CONFIG.pollInterval);
    setInterval(pollAnalysis, CONFIG.analysisInterval);
    setInterval(pollCharts,   CONFIG.chartInterval);

    console.log('[GHOST.SYS] Käynnistys valmis');
}

// KÄYNNISTYS
// DOMContentLoaded varmistaa että HTML on latautunut ennen kuin
// JavaScript yrittää löytää elementtejä
document.addEventListener('DOMContentLoaded', init);