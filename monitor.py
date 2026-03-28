"""
=============================================================
  Live CPU & Memory Monitor Dashboard
=============================================================
  Project:  Project 1 of 5 (GSoC prep series)
  Concepts: Flask web server, Server-Sent Events (SSE),
            real-time data streaming, psutil, Python generators
  Run with: python app.py
  Then open: http://127.0.0.1:5000
=============================================================
"""

import time
import json
import psutil
from flask import Flask, Response, render_template_string

# ── App setup ────────────────────────────────────────────────
app = Flask(__name__)

# How often (in seconds) we send a new data reading to the browser.
# Lower = more real-time but more CPU usage. 1 second is a good balance.
STREAM_INTERVAL = 1


# ── Data collection ──────────────────────────────────────────

def get_system_stats():
    """
    Reads current CPU and memory usage from the operating system.

    psutil.cpu_percent(interval=None) returns the CPU usage since the
    last call — that is why we call it with interval=None (non-blocking)
    and rely on our own sleep loop instead of blocking here.

    Returns a dict with:
        - cpu    : CPU usage as a percentage (0–100)
        - memory : RAM usage as a percentage (0–100)
        - mem_used_gb : how many GB of RAM are currently in use
        - mem_total_gb: total RAM in GB
        - timestamp   : Unix timestamp of the reading
    """
    cpu = psutil.cpu_percent(interval=None)

    mem = psutil.virtual_memory()
    memory_percent = mem.percent
    mem_used_gb = round(mem.used / (1024 ** 3), 2)   # bytes → GB
    mem_total_gb = round(mem.total / (1024 ** 3), 2)

    return {
        "cpu": cpu,
        "memory": memory_percent,
        "mem_used_gb": mem_used_gb,
        "mem_total_gb": mem_total_gb,
        "timestamp": time.time(),
    }


# ── SSE stream ───────────────────────────────────────────────

def event_stream():
    """
    A Python *generator* that yields Server-Sent Events (SSE) forever.

    SSE is a simple protocol:
        - The server keeps an HTTP connection open.
        - It sends text lines that start with "data: ".
        - Each event ends with a blank line (\n\n).
        - The browser's built-in EventSource API listens and fires a
          callback every time a new event arrives.

    This is one of the core patterns in the MDAnalysis GSoC project —
    the simulation sends frames, and we push each frame to the browser.
    Here, the OS sends CPU/memory readings and we push each reading.
    """
    # Warm up psutil — the first call always returns 0.0
    psutil.cpu_percent(interval=None)
    time.sleep(0.1)

    while True:
        stats = get_system_stats()

        # SSE format: "data: <json payload>\n\n"
        # json.dumps turns our dict into a JSON string the browser can parse.
        payload = json.dumps(stats)
        yield f"data: {payload}\n\n"

        time.sleep(STREAM_INTERVAL)


# ── Routes ───────────────────────────────────────────────────

@app.route("/stream")
def stream():
    """
    The /stream endpoint keeps an HTTP connection open and
    pushes SSE data to the browser continuously.

    The Content-Type 'text/event-stream' tells the browser
    this is an SSE connection (not a regular page load).
    X-Accel-Buffering: no tells any reverse proxy (e.g. Nginx)
    not to buffer the response — we need it to flow in real time.
    """
    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@app.route("/")
def index():
    """
    Serves the main dashboard HTML page.
    We use render_template_string so everything lives in one file —
    easier for learning. In a bigger project you would put the HTML
    in a separate templates/ folder.
    """
    return render_template_string(DASHBOARD_HTML)


# ── HTML dashboard ───────────────────────────────────────────
# This is the browser side of the project.
# It uses the browser's built-in EventSource API to listen to /stream
# and Chart.js (loaded from a CDN) to draw live charts.

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Live System Monitor</title>

  <!-- Chart.js — a JavaScript charting library, loaded from CDN -->
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>

  <style>
    /* ── Basic reset & layout ── */
    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: Arial, sans-serif;
      background: #0f172a;   /* dark navy background */
      color: #e2e8f0;
      min-height: 100vh;
      padding: 2rem;
    }

    h1 {
      font-size: 1.5rem;
      font-weight: 600;
      margin-bottom: 1.5rem;
      color: #f8fafc;
    }

    /* ── Stat cards at the top ── */
    .cards {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 1rem;
      margin-bottom: 2rem;
    }

    .card {
      background: #1e293b;
      border-radius: 12px;
      padding: 1.25rem 1.5rem;
      border: 1px solid #334155;
    }

    .card-label {
      font-size: 0.75rem;
      color: #94a3b8;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 0.5rem;
    }

    .card-value {
      font-size: 2rem;
      font-weight: 700;
      color: #f8fafc;
    }

    .card-sub {
      font-size: 0.75rem;
      color: #64748b;
      margin-top: 0.25rem;
    }

    /* Colour the CPU and memory values */
    #cpu-value  { color: #38bdf8; } /* sky blue  */
    #mem-value  { color: #a78bfa; } /* purple    */

    /* ── Chart containers ── */
    .charts {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 1.5rem;
    }

    .chart-box {
      background: #1e293b;
      border-radius: 12px;
      padding: 1.25rem;
      border: 1px solid #334155;
    }

    .chart-box h2 {
      font-size: 0.875rem;
      color: #94a3b8;
      margin-bottom: 1rem;
      font-weight: 500;
    }

    /* Connection status badge */
    #status {
      display: inline-block;
      padding: 0.25rem 0.75rem;
      border-radius: 999px;
      font-size: 0.75rem;
      background: #166534;
      color: #86efac;
      margin-left: 0.75rem;
      vertical-align: middle;
    }

    #status.disconnected {
      background: #7f1d1d;
      color: #fca5a5;
    }
  </style>
</head>
<body>

  <h1>
    Live System Monitor
    <span id="status">● Connected</span>
  </h1>

  <!-- ── Stat cards ── -->
  <div class="cards">
    <div class="card">
      <div class="card-label">CPU Usage</div>
      <div class="card-value"><span id="cpu-value">--</span><span style="font-size:1rem;color:#64748b">%</span></div>
      <div class="card-sub">All cores combined</div>
    </div>
    <div class="card">
      <div class="card-label">Memory Usage</div>
      <div class="card-value"><span id="mem-value">--</span><span style="font-size:1rem;color:#64748b">%</span></div>
      <div class="card-sub" id="mem-sub">-- GB used of -- GB</div>
    </div>
  </div>

  <!-- ── Live charts ── -->
  <div class="charts">
    <div class="chart-box">
      <h2>CPU % over time</h2>
      <canvas id="cpu-chart"></canvas>
    </div>
    <div class="chart-box">
      <h2>Memory % over time</h2>
      <canvas id="mem-chart"></canvas>
    </div>
  </div>

  <script>
    /*
     * ── How many data points to show on the chart at once ──
     * When we have more than MAX_POINTS readings, we drop the oldest one.
     * This creates the "scrolling" effect.
     */
    const MAX_POINTS = 60;

    // Store the last MAX_POINTS labels (timestamps) and values
    const labels  = [];
    const cpuData = [];
    const memData = [];

    /*
     * ── Chart.js setup ──
     * We create two line charts. The configuration is very similar —
     * only the colour and the dataset differ.
     */
    function makeChart(canvasId, label, color) {
      const ctx = document.getElementById(canvasId).getContext("2d");
      return new Chart(ctx, {
        type: "line",
        data: {
          labels: labels,
          datasets: [{
            label: label,
            data: color === "#38bdf8" ? cpuData : memData,
            borderColor: color,
            backgroundColor: color + "22",  // same colour but very transparent fill
            borderWidth: 2,
            pointRadius: 0,       // no dots on the line
            tension: 0.4,         // smooth curve
            fill: true,
          }]
        },
        options: {
          animation: false,       // disable animation so updates feel instant
          responsive: true,
          scales: {
            x: {
              display: false      // hide x-axis labels (timestamps are cluttered)
            },
            y: {
              min: 0,
              max: 100,
              grid:  { color: "#1e3a5f" },
              ticks: { color: "#64748b", callback: v => v + "%" }
            }
          },
          plugins: {
            legend: { display: false }
          }
        }
      });
    }

    const cpuChart = makeChart("cpu-chart", "CPU %",    "#38bdf8");
    const memChart = makeChart("mem-chart", "Memory %", "#a78bfa");

    /*
     * ── EventSource — the SSE connection ──
     *
     * EventSource is built into every modern browser.
     * It opens a connection to /stream and fires the onmessage
     * callback every time the server sends a new event.
     *
     * This is the browser equivalent of the imdclient connection
     * in the MDAnalysis GSoC project.
     */
    const source = new EventSource("/stream");

    source.onmessage = function(event) {
      // Parse the JSON payload the server sent
      const data = JSON.parse(event.data);

      // Format the timestamp as HH:MM:SS
      const t = new Date(data.timestamp * 1000);
      const label = t.toTimeString().slice(0, 8);

      // Add new data point
      labels.push(label);
      cpuData.push(data.cpu);
      memData.push(data.memory);

      // Drop the oldest point if we have too many
      if (labels.length  > MAX_POINTS) labels.shift();
      if (cpuData.length > MAX_POINTS) cpuData.shift();
      if (memData.length > MAX_POINTS) memData.shift();

      // Update stat cards
      document.getElementById("cpu-value").textContent = data.cpu.toFixed(1);
      document.getElementById("mem-value").textContent = data.memory.toFixed(1);
      document.getElementById("mem-sub").textContent =
        data.mem_used_gb + " GB used of " + data.mem_total_gb + " GB";

      // Redraw the charts
      cpuChart.update();
      memChart.update();
    };

    source.onerror = function() {
      // If the connection drops, show the disconnected badge
      const s = document.getElementById("status");
      s.textContent = "● Disconnected";
      s.classList.add("disconnected");
    };

    source.onopen = function() {
      const s = document.getElementById("status");
      s.textContent = "● Connected";
      s.classList.remove("disconnected");
    };
  </script>
</body>
</html>
"""


# ── Entry point ──────────────────────────────────────────────

if __name__ == "__main__":
    """
    debug=True means Flask will auto-restart when you save changes to app.py.
    use_reloader=False prevents psutil from being initialised twice on startup
    (Flask's reloader forks the process, which confuses psutil).
    """
    print("Starting Live CPU & Memory Monitor...")
    print("Open your browser at: http://127.0.0.1:5000")
    app.run(debug=True, use_reloader=False)
