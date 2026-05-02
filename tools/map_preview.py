"""
Hero's Initiative — Live Traffic Map Preview
============================================
Fetches live traffic for all 16 segments, decodes road polylines,
and generates a self-contained HTML file you can open in a browser.

Usage:
    python tools/map_preview.py
    # opens map_preview.html
"""

import asyncio
import os
import json
import httpx
from datetime import datetime, timezone

GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")

ROAD_SEGMENTS = {
    "road_01a": {"name": "Shahrae Faisal", "segment": "Airport to Drigh Road", "origin": "24.900800,67.168100", "destination": "24.887019,67.125427", "distance_meters": 5800, "via": None},
    "road_01b": {"name": "Shahrae Faisal", "segment": "Drigh Road to Karsaz", "origin": "24.886820,67.124261", "destination": "24.874779,67.095790", "distance_meters": 3400, "via": None},
    "road_01c": {"name": "Shahrae Faisal", "segment": "Karsaz to Shaheed-e-Millat Bridge", "origin": "24.874779,67.095790", "destination": "24.867330,67.083804", "distance_meters": 1500, "via": None},
    "road_01d": {"name": "Shaheed-e-Millat Rd", "segment": "Shaheed-e-Millat Bridge to City School PAF", "origin": "24.867330,67.083804", "destination": "24.861271,67.088200", "distance_meters": 850, "via": None},
    "road_01e": {"name": "Shaheed-e-Millat Rd", "segment": "City School PAF to Manzoor Colony Parallel Rd", "origin": "24.861232,67.088067", "destination": "24.845614,67.087526", "distance_meters": 1800, "via": None},
    "road_01f": {"name": "Shahrae Faisal", "segment": "Shahrah-e-Qaideen Flyover to Metropole", "origin": "24.859613,67.058741", "destination": "24.849675,67.030451", "distance_meters": 3300, "via": None},
    "road_02a": {"name": "Shaheed-e-Millat Rd", "segment": "Defence/Korangi to Manzoor Colony", "origin": "24.830991,67.079535", "destination": "24.852834,67.089831", "distance_meters": 2700, "via": None},
    "road_02b": {"name": "Shaheed-e-Millat Rd", "segment": "Manzoor Colony to Shaheed-e-Millat Bridge", "origin": "24.852834,67.089831", "destination": "24.866864,67.083022", "distance_meters": 1800, "via": None},
    "road_04a": {"name": "Khayaban-e-Iqbal", "segment": "Metropole to Teen Talwar", "origin": "24.849679,67.030558", "destination": "24.833776,67.033724", "distance_meters": 1800, "via": None},
    "road_04b": {"name": "Khayaban-e-Iqbal", "segment": "Teen Talwar to Do Talwar", "origin": "24.833776,67.033724", "destination": "24.821175,67.034203", "distance_meters": 1500, "via": None},
    "road_05a": {"name": "Allama Shabbir Ahmed Usmani Rd", "segment": "Disco Bakery to Gulshan Chowrangi", "origin": "24.928994,67.097579", "destination": "24.924415,67.091974", "distance_meters": 800, "via": "24.927191,67.095309"},
    "road_05b": {"name": "Rashid Minhas Road", "segment": "Nipa Chowrangi to Gulshan Chowrangi", "origin": "24.917749,67.096957", "destination": "24.924293,67.091536", "distance_meters": 900, "via": "24.921277,67.094047"},
    "road_05c": {"name": "Allama Shabbir Ahmed Usmani Rd", "segment": "Maskan Chowrangi to Disco Bakery", "origin": "24.935079,67.105263", "destination": "24.929126,67.097527", "distance_meters": 1000, "via": "24.932000,67.101400"},
    "road_06a": {"name": "Rashid Minhas Road", "segment": "Gulshan Chowrangi to Nipa Chowrangi", "origin": "24.924578,67.091605", "destination": "24.917845,67.097369", "distance_meters": 900, "via": "24.921200,67.094400"},
    "road_06b": {"name": "Rashid Minhas Road", "segment": "Nipa Chowrangi to Johar Mor", "origin": "24.917845,67.097369", "destination": "24.903882,67.114075", "distance_meters": 2300, "via": None},
    "road_06c": {"name": "Rashid Minhas Road", "segment": "Johar Mor to Askari 4", "origin": "24.903882,67.114075", "destination": "24.900911,67.116371", "distance_meters": 500, "via": "24.902139,67.115517"},
    "road_06d": {"name": "Rashid Minhas Road", "segment": "Askari 4 to Drigh Road", "origin": "24.900911,67.116371", "destination": "24.886764,67.124087", "distance_meters": 1900, "via": None},
}

CONGESTION_COLOURS = {
    "free_flow": "#27ae60",
    "light":     "#f39c12",
    "moderate":  "#e67e22",
    "heavy":     "#e74c3c",
}


def decode_polyline(encoded: str) -> list[list[float]]:
    """Decode a Google encoded polyline string into [[lat, lng], ...] pairs."""
    coords, index, lat, lng = [], 0, 0, 0
    while index < len(encoded):
        for is_lng in (False, True):
            shift, result = 0, 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if is_lng:
                lng += delta
            else:
                lat += delta
        coords.append([lat / 1e5, lng / 1e5])
    return coords


def classify_congestion(ratio: float) -> str:
    if ratio < 1.10:
        return "free_flow"
    elif ratio < 1.30:
        return "light"
    elif ratio < 1.60:
        return "moderate"
    return "heavy"


def parse_latlng(coord_str: str) -> dict:
    lat, lng = coord_str.split(",")
    return {"latitude": float(lat), "longitude": float(lng)}


async def fetch_segment(road_id: str, seg: dict, client: httpx.AsyncClient) -> dict | None:
    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    headers = {
        "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": "routes.duration,routes.staticDuration,routes.polyline.encodedPolyline",
    }
    body = {
        "origin":      {"location": {"latLng": parse_latlng(seg["origin"])}},
        "destination": {"location": {"latLng": parse_latlng(seg["destination"])}},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
    }
    if seg.get("via"):
        body["intermediates"] = [{"via": True, "location": {"latLng": parse_latlng(seg["via"])}}]

    resp = await client.post(url, headers=headers, json=body)
    data = resp.json()
    routes = data.get("routes", [])
    if not routes:
        print(f"  [{road_id}] No route returned: {data}")
        return None

    route = routes[0]
    duration_secs = int(route.get("duration", "0s").rstrip("s"))
    static_secs   = int(route.get("staticDuration", "0s").rstrip("s"))
    encoded       = route.get("polyline", {}).get("encodedPolyline", "")

    if not encoded or not static_secs:
        print(f"  [{road_id}] Missing polyline or staticDuration")
        return None

    ratio  = round(duration_secs / static_secs, 3)
    level  = classify_congestion(ratio)
    colour = CONGESTION_COLOURS[level]
    coords = decode_polyline(encoded)
    speed  = round((seg["distance_meters"] / duration_secs) * 3.6, 1) if duration_secs else 0

    print(f"  [{road_id}] {level:10s}  ratio={ratio}  {speed} km/h  {seg['segment']}")
    return {
        "road_id":   road_id,
        "name":      seg["name"],
        "segment":   seg["segment"],
        "coords":    coords,
        "colour":    colour,
        "level":     level,
        "ratio":     ratio,
        "speed_kmh": speed,
        "via":       seg.get("via"),
        "origin":    seg["origin"],
        "destination": seg["destination"],
    }


async def fetch_all() -> list[dict]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        results = await asyncio.gather(*[
            fetch_segment(k, v, client) for k, v in ROAD_SEGMENTS.items()
        ])
    return [r for r in results if r]


def build_html(segments: list[dict], timestamp: str) -> str:
    segments_json = json.dumps(segments)
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Hero's Initiative — Live Traffic Preview</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0a0c14; color: #e0e0e0; display: flex; flex-direction: column; height: 100vh; }}

    #header {{ padding: 0 20px; height: 52px; background: #0f1218; border-bottom: 1px solid #1e2433; display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; }}
    #header h1 {{ font-size: 13px; font-weight: 600; color: #f1f5f9; letter-spacing: 0.2px; }}
    #header .timestamp {{ font-size: 11px; color: #475569; background: #1a2030; padding: 3px 10px; border-radius: 20px; border: 1px solid #1e2a3a; }}

    #body {{ display: flex; flex: 1; overflow: hidden; }}

    #sidebar {{ width: 260px; background: #0d1017; border-right: 1px solid #1a2030; overflow-y: auto; flex-shrink: 0; display: flex; flex-direction: column; }}
    #sidebar::-webkit-scrollbar {{ width: 4px; }}
    #sidebar::-webkit-scrollbar-track {{ background: transparent; }}
    #sidebar::-webkit-scrollbar-thumb {{ background: #1e2a3a; border-radius: 2px; }}

    #all-btn {{ margin: 12px; padding: 9px 14px; background: #161c2a; border: 1px solid #1e2a3a; border-radius: 8px; color: #7c8db5; font-size: 12px; font-weight: 500; cursor: pointer; text-align: left; display: flex; align-items: center; gap: 8px; transition: all 0.15s; }}
    #all-btn:hover {{ background: #1a2436; border-color: #2d3f5e; color: #a0b0d0; }}
    #all-btn svg {{ opacity: 0.6; }}

    .group-header {{ padding: 16px 14px 6px; font-size: 10px; font-weight: 700; color: #334155; text-transform: uppercase; letter-spacing: 1px; }}

    .seg-card {{ margin: 2px 10px; border-radius: 8px; overflow: hidden; cursor: pointer; border: 1px solid transparent; transition: all 0.15s; }}
    .seg-card:hover {{ background: #131926; border-color: #1e2a3a; }}
    .seg-card.active {{ background: #111827; border-color: #3b4fd8; }}
    .seg-card-inner {{ padding: 9px 11px; display: flex; align-items: flex-start; gap: 10px; }}
    .seg-color-bar {{ width: 3px; border-radius: 2px; min-height: 32px; flex-shrink: 0; margin-top: 2px; }}
    .seg-info {{ flex: 1; min-width: 0; }}
    .seg-name {{ font-size: 12px; font-weight: 500; color: #94a3b8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1.3; }}
    .seg-card.active .seg-name {{ color: #e2e8f0; }}
    .seg-id-row {{ display: flex; align-items: center; gap: 6px; margin-top: 3px; }}
    .seg-id {{ font-size: 10px; color: #334155; font-family: "SF Mono", "Fira Code", monospace; }}
    .seg-card.active .seg-id {{ color: #4f6096; }}
    .seg-stat {{ font-size: 10px; color: #3d4f6e; }}
    .seg-card.active .seg-stat {{ color: #5a7299; }}
    .via-pill {{ font-size: 9px; background: #1e1530; color: #7c3aed; border: 1px solid #2d1f52; border-radius: 3px; padding: 0px 4px; font-weight: 600; }}

    #map {{ flex: 1; }}

    .legend {{ background: #0d1017ee; padding: 10px 13px; border-radius: 8px; border: 1px solid #1a2030; font-size: 11px; line-height: 2; backdrop-filter: blur(4px); }}
    .legend-title {{ font-weight: 600; color: #e2e8f0; font-size: 11px; margin-bottom: 2px; }}
    .dot {{ display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 7px; vertical-align: middle; }}
    .legend-divider {{ border-top: 1px solid #1a2030; margin: 6px 0; }}
  </style>
</head>
<body>
  <div id="header">
    <h1>Hero's Initiative — Karachi Traffic Intelligence</h1>
    <span class="timestamp">Live · {timestamp}</span>
  </div>
  <div id="body">
    <div id="sidebar">
      <button id="all-btn" onclick="showAll()">
        <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor"><rect x="1" y="1" width="6" height="6" rx="1"/><rect x="9" y="1" width="6" height="6" rx="1"/><rect x="1" y="9" width="6" height="6" rx="1"/><rect x="9" y="9" width="6" height="6" rx="1"/></svg>
        All segments
      </button>
    </div>
    <div id="map"></div>
  </div>
  <script>
    const segments = {segments_json};
    const COLOURS = {{ free_flow:'#27ae60', light:'#f39c12', moderate:'#e67e22', heavy:'#e74c3c' }};
    const LABELS  = {{ free_flow:'Free Flow', light:'Light', moderate:'Moderate', heavy:'Heavy' }};

    const map = L.map('map', {{ zoomControl: true }}).setView([24.880, 67.080], 13);
    L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
      attribution: '© OpenStreetMap © CARTO', maxZoom: 19
    }}).addTo(map);

    // Build segment layers
    const layers = {{}};
    let activeId = null;

    // Group sidebar by road name
    const groups = {{}};
    segments.forEach(seg => {{
      if (!groups[seg.name]) groups[seg.name] = [];
      groups[seg.name].push(seg);
    }});

    const sidebar = document.getElementById('sidebar');
    Object.entries(groups).forEach(([roadName, segs]) => {{
      const header = document.createElement('div');
      header.className = 'group-header';
      header.textContent = roadName;
      sidebar.appendChild(header);
      segs.forEach(seg => {{
        const card = document.createElement('div');
        card.className = 'seg-card';
        card.id = 'btn-' + seg.road_id;
        const viaPill = seg.via ? `<span class="via-pill">VIA</span>` : '';
        card.innerHTML = `
          <div class="seg-card-inner">
            <div class="seg-color-bar" style="background:${{seg.colour}}"></div>
            <div class="seg-info">
              <div class="seg-name">${{seg.segment}}</div>
              <div class="seg-id-row">
                <span class="seg-id">${{seg.road_id}}</span>
                <span class="seg-stat">${{seg.speed_kmh}} km/h · ${{seg.ratio}}</span>
                ${{viaPill}}
              </div>
            </div>
          </div>`;
        card.onclick = () => selectSegment(seg.road_id);
        sidebar.appendChild(card);
      }});
    }});

    function makeLayers(seg) {{
      const [oLat, oLng] = seg.origin.split(',').map(Number);
      const [dLat, dLng] = seg.destination.split(',').map(Number);

      const line = L.polyline(seg.coords, {{
        color: seg.colour, weight: 5, opacity: 0.85,
        lineJoin: 'round', lineCap: 'round',
      }});

      const badge = `<span style="display:inline-block;padding:1px 8px;border-radius:10px;font-size:11px;font-weight:600;color:#fff;background:${{seg.colour}}">${{LABELS[seg.level]}}</span>`;
      line.bindPopup(`
        <div style="font-weight:700;font-size:13px;margin-bottom:3px">${{seg.segment}}</div>
        <div style="color:#6b7280;font-size:11px;margin-bottom:7px">${{seg.name}}</div>
        <div style="font-size:12px;display:flex;justify-content:space-between;margin:2px 0"><span style="color:#9ca3af">Ratio</span><span>${{seg.ratio}}</span></div>
        <div style="font-size:12px;display:flex;justify-content:space-between;margin:2px 0"><span style="color:#9ca3af">Speed</span><span>${{seg.speed_kmh}} km/h</span></div>
        ${{badge}}
      `, {{ maxWidth: 200 }});

      // Start marker (green)
      const startDot = L.circleMarker([oLat, oLng], {{
        radius: 6, color: '#fff', weight: 1.5,
        fillColor: '#22c55e', fillOpacity: 1,
      }}).bindPopup(`<b>START</b><br>${{seg.road_id}}<br>${{seg.origin}}`);

      // End marker (red)
      const endDot = L.circleMarker([dLat, dLng], {{
        radius: 6, color: '#fff', weight: 1.5,
        fillColor: '#ef4444', fillOpacity: 1,
      }}).bindPopup(`<b>END</b><br>${{seg.road_id}}<br>${{seg.destination}}`);

      // Via marker (purple)
      let viaDot = null;
      if (seg.via) {{
        const [vLat, vLng] = seg.via.split(',').map(Number);
        viaDot = L.circleMarker([vLat, vLng], {{
          radius: 5, color: '#fff', weight: 1.5,
          fillColor: '#a855f7', fillOpacity: 1,
        }}).bindPopup(`<b>VIA waypoint</b><br>${{seg.road_id}}<br>${{seg.via}}`);
      }}

      return {{ line, startDot, endDot, viaDot }};
    }}

    // Create all layers
    segments.forEach(seg => {{
      layers[seg.road_id] = makeLayers(seg);
    }});

    function showAll() {{
      activeId = null;
      document.querySelectorAll('.seg-card').forEach(b => b.classList.remove('active'));
      // Remove all layers first
      map.eachLayer(l => {{ if (l !== map._layers[Object.keys(map._layers)[0]]) {{}} }});
      Object.values(layers).forEach(l => {{
        l.line.setStyle({{ weight: 5, opacity: 0.85 }});
        l.line.addTo(map);
        l.startDot.addTo(map);
        l.endDot.addTo(map);
        if (l.viaDot) l.viaDot.addTo(map);
      }});
      map.setView([24.880, 67.080], 13);
    }}

    function selectSegment(id) {{
      activeId = id;
      // Update sidebar
      document.querySelectorAll('.seg-card').forEach(b => b.classList.remove('active'));
      document.getElementById('btn-' + id).classList.add('active');

      // Remove all layers from map
      Object.values(layers).forEach(l => {{
        map.removeLayer(l.line);
        map.removeLayer(l.startDot);
        map.removeLayer(l.endDot);
        if (l.viaDot) map.removeLayer(l.viaDot);
      }});

      // Add only selected segment, full brightness
      const l = layers[id];
      l.line.setStyle({{ weight: 7, opacity: 1 }});
      l.line.addTo(map);
      l.startDot.addTo(map);
      l.endDot.addTo(map);
      if (l.viaDot) l.viaDot.addTo(map);

      // Zoom to segment
      map.fitBounds(l.line.getBounds(), {{ padding: [60, 60] }});
    }}

    // Start with all visible
    showAll();

    // Legend
    const legend = L.control({{ position: 'bottomright' }});
    legend.onAdd = () => {{
      const div = L.DomUtil.create('div', 'legend');
      div.innerHTML = `
        <div class="legend-title">Congestion</div>
        <div><span class="dot" style="background:#27ae60"></span>Free Flow</div>
        <div><span class="dot" style="background:#f39c12"></span>Light</div>
        <div><span class="dot" style="background:#e67e22"></span>Moderate</div>
        <div><span class="dot" style="background:#e74c3c"></span>Heavy</div>
        <div style="margin-top:6px;padding-top:6px;border-top:1px solid #2d3148">
          <span class="dot" style="background:#22c55e"></span>Start<br>
          <span class="dot" style="background:#ef4444"></span>End<br>
          <span class="dot" style="background:#a855f7"></span>Via waypoint
        </div>`;
      return div;
    }};
    legend.addTo(map);
  </script>
</body>
</html>"""


async def main():
    if not GOOGLE_MAPS_API_KEY:
        print("ERROR: GOOGLE_MAPS_API_KEY not set")
        return

    print(f"Fetching live traffic for {len(ROAD_SEGMENTS)} segments...")
    segments = await fetch_all()
    print(f"\n{len(segments)}/{len(ROAD_SEGMENTS)} segments fetched successfully")

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = build_html(segments, timestamp)

    out = "/home/runner/workspace/map_preview.html"
    with open(out, "w") as f:
        f.write(html)
    print(f"\nMap saved to: {out}")


asyncio.run(main())
