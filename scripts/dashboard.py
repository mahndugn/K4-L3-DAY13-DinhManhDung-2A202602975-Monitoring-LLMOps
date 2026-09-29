from __future__ import annotations

import json
import math
import sys
import argparse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
CONFIG_PATH = REPO_ROOT / "config" / "dashboard.yaml"
WINDOW_MINUTES = 60
BUCKET_MINUTES = 5
BUCKET_COUNT = WINDOW_MINUTES // BUCKET_MINUTES


def _read_records(now: datetime) -> list[dict[str, Any]]:
    if not LOG_PATH.exists():
        return []
    since = now - timedelta(minutes=WINDOW_MINUTES)
    records: list[dict[str, Any]] = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
            timestamp = datetime.fromisoformat(record["ts"].replace("Z", "+00:00"))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        if since <= timestamp <= now:
            record["_timestamp"] = timestamp
            records.append(record)
    return records


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = (len(ordered) - 1) * percentile / 100
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower)


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _number(value: float | None, places: int = 1) -> str:
    return "n/a" if value is None else f"{value:,.{places}f}"


def _series(name: str, values: list[float | None], color: str) -> dict[str, Any]:
    return {"name": name, "values": values, "color": color}


def build_dashboard_payload(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["dashboard"]
    records = _read_records(now)
    requests = [record for record in records if record.get("event") == "request_received"]
    responses = [record for record in records if record.get("event") == "response_sent"]
    failures = [record for record in records if record.get("event") == "request_failed"]
    retrieval_records = [
        record for record in records if record.get("tool_success") in (True, False)
    ]
    successful_retrievals = sum(record.get("tool_success") is True for record in retrieval_records)

    latency = [float(record["latency_ms"]) for record in responses if record.get("latency_ms") is not None]
    ttft = [float(record["ttft_ms"]) for record in responses if record.get("ttft_ms") is not None]
    costs = [float(record["cost_usd"]) for record in responses if record.get("cost_usd") is not None]
    input_tokens = [float(record["tokens_in"]) for record in responses if record.get("tokens_in") is not None]
    output_tokens = [float(record["tokens_out"]) for record in responses if record.get("tokens_out") is not None]
    quality = [float(record["quality_score"]) for record in responses if record.get("quality_score") is not None]

    bucket_start = now - timedelta(minutes=WINDOW_MINUTES)
    buckets = [
        bucket_start + timedelta(minutes=BUCKET_MINUTES * index)
        for index in range(BUCKET_COUNT)
    ]

    def in_bucket(record: dict[str, Any], index: int) -> bool:
        timestamp = record["_timestamp"]
        lower = buckets[index]
        upper = lower + timedelta(minutes=BUCKET_MINUTES)
        return lower <= timestamp < upper or (index == BUCKET_COUNT - 1 and timestamp <= now)

    traffic_rate: list[float | None] = []
    latency_p95: list[float | None] = []
    ttft_p95: list[float | None] = []
    error_rates: list[float | None] = []
    retrieval_rates: list[float | None] = []
    cost_by_bucket: list[float | None] = []
    input_by_bucket: list[float | None] = []
    output_by_bucket: list[float | None] = []
    quality_by_bucket: list[float | None] = []
    for index in range(BUCKET_COUNT):
        bucket_requests = [record for record in requests if in_bucket(record, index)]
        bucket_failures = [record for record in failures if in_bucket(record, index)]
        bucket_responses = [record for record in responses if in_bucket(record, index)]
        bucket_retrievals = [record for record in retrieval_records if in_bucket(record, index)]
        bucket_latency = [float(record["latency_ms"]) for record in bucket_responses if record.get("latency_ms") is not None]
        bucket_ttft = [float(record["ttft_ms"]) for record in bucket_responses if record.get("ttft_ms") is not None]
        traffic_rate.append(len(bucket_requests) / BUCKET_MINUTES)
        latency_p95.append(_percentile(bucket_latency, 95))
        ttft_p95.append(_percentile(bucket_ttft, 95))
        error_rates.append(100 * len(bucket_failures) / len(bucket_requests) if bucket_requests else None)
        retrieval_rates.append(
            100 * sum(record.get("tool_success") is True for record in bucket_retrievals) / len(bucket_retrievals)
            if bucket_retrievals else None
        )
        cost_by_bucket.append(sum(float(record.get("cost_usd", 0)) for record in bucket_responses))
        input_by_bucket.append(sum(float(record.get("tokens_in", 0)) for record in bucket_responses))
        output_by_bucket.append(sum(float(record.get("tokens_out", 0)) for record in bucket_responses))
        quality_values = [float(record["quality_score"]) for record in bucket_responses if record.get("quality_score") is not None]
        quality_by_bucket.append(_mean(quality_values))

    panel_config = {panel["id"]: panel for panel in config["panels"]}

    def panel(panel_id: str, metrics: list[dict[str, str]], series: list[dict[str, Any]], status: bool | None,
              chart_threshold: float | None = None) -> dict[str, Any]:
        contract = panel_config[panel_id]
        threshold = contract["threshold"]
        return {
            "id": panel_id,
            "title": contract["title"],
            "unit": contract["unit"],
            "threshold": f"{threshold['aggregation']} {threshold['operator']} {threshold['value']} {contract['unit']}",
            "status": status,
            "metrics": metrics,
            "series": series,
            "chart_threshold": chart_threshold,
        }

    p95 = _percentile(latency, 95)
    ttft95 = _percentile(ttft, 95)
    request_count = len(requests)
    error_rate = 100 * len(failures) / request_count if request_count else None
    retrieval_rate = 100 * successful_retrievals / len(retrieval_records) if retrieval_records else None
    cost_total = sum(costs)
    tokens_in_total = sum(input_tokens)
    tokens_out_total = sum(output_tokens)
    quality_mean = _mean(quality)

    panels = [
        panel("latency", [
            {"label": "P50", "value": f"{_number(_percentile(latency, 50))} ms"},
            {"label": "P95", "value": f"{_number(p95)} ms"},
            {"label": "P99", "value": f"{_number(_percentile(latency, 99))} ms"},
            {"label": "TTFT P95", "value": f"{_number(ttft95)} ms"},
        ], [_series("Request P95", latency_p95, "#4f8cff"), _series("TTFT P95", ttft_p95, "#23b7a4")],
            p95 is not None and p95 <= 3000, 3000),
        panel("traffic", [
            {"label": "Requests", "value": f"{request_count:,}"},
            {"label": "Average rate", "value": f"{_number(request_count / WINDOW_MINUTES, 2)} req/min"},
        ], [_series("Requests/min", traffic_rate, "#4f8cff")],
            request_count / WINDOW_MINUTES >= 1, 1),
        panel("errors", [
            {"label": "Error rate", "value": f"{_number(error_rate)}%"},
            {"label": "Retrieval success", "value": f"{_number(retrieval_rate)}%"},
            {"label": "Failed requests", "value": f"{len(failures):,}"},
        ], [_series("Error rate", error_rates, "#f06b6b"), _series("Retrieval success", retrieval_rates, "#23b7a4")],
            error_rate is not None and error_rate <= 2, 2),
        panel("cost", [
            {"label": "Total cost", "value": f"${cost_total:.6f}"},
            {"label": "Cost / request", "value": f"${cost_total / len(costs):.6f}" if costs else "n/a"},
        ], [_series("Cost / 5 min", cost_by_bucket, "#a879ff")], cost_total <= 2.5),
        panel("tokens", [
            {"label": "Input tokens", "value": f"{int(tokens_in_total):,}"},
            {"label": "Output tokens", "value": f"{int(tokens_out_total):,}"},
            {"label": "Total tokens", "value": f"{int(tokens_in_total + tokens_out_total):,}"},
        ], [_series("Input", input_by_bucket, "#4f8cff"), _series("Output", output_by_bucket, "#23b7a4")],
            max(tokens_in_total, tokens_out_total) <= 50000),
        panel("quality", [
            {"label": "Mean score", "value": _number(quality_mean, 2)},
            {"label": "Responses", "value": f"{len(quality):,}"},
        ], [_series("Quality", quality_by_bucket, "#f0b44c")],
            quality_mean is not None and quality_mean >= 0.75, 0.75),
    ]
    return {
        "title": config["title"],
        "time_range_minutes": config["time_range_minutes"],
        "refresh_seconds": config["refresh_seconds"],
        "generated_at": now.isoformat(timespec="seconds"),
        "log_records": len(records),
        "bucket_labels": [bucket.strftime("%H:%M") for bucket in buckets],
        "panels": panels,
    }


HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Day 13 Monitoring Dashboard</title><style>
:root{color-scheme:dark;--bg:#0b1020;--card:#131b2e;--line:#27324a;--muted:#9cabc4;--text:#edf3ff;--blue:#4f8cff;--green:#23b7a4;--red:#f06b6b;--amber:#f0b44c}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 15% 0,#172647 0,transparent 38%),var(--bg);color:var(--text);font:14px/1.45 Segoe UI,Arial,sans-serif}
main{max-width:1440px;margin:auto;padding:30px 26px 44px}.head{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;margin-bottom:22px}.eyebrow{color:#85a8ec;text-transform:uppercase;letter-spacing:.14em;font-size:11px;font-weight:700}.head h1{font-size:28px;margin:5px 0}.meta{color:var(--muted);text-align:right}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.card{background:linear-gradient(145deg,rgba(24,34,56,.98),rgba(17,24,41,.98));border:1px solid var(--line);border-radius:14px;padding:18px 19px;box-shadow:0 12px 36px #0003;min-width:0}.card-top{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.card h2{font-size:16px;margin:0 0 4px}.unit{color:var(--muted);font-size:12px}.badge{font-size:11px;border-radius:20px;padding:4px 9px;white-space:nowrap}.ok{background:#103a36;color:#70e0c8}.bad{background:#48252a;color:#ffaaaa}.unknown{background:#33394a;color:#c2c9d8}.stats{display:flex;flex-wrap:wrap;gap:8px 22px;margin:17px 0 8px}.stat{display:flex;flex-direction:column;gap:2px}.stat label{font-size:11px;color:var(--muted)}.stat strong{font-size:16px;font-variant-numeric:tabular-nums}.chart{height:132px;width:100%;margin-top:5px}.chart svg{width:100%;height:100%;overflow:visible}.legend{display:flex;gap:16px;flex-wrap:wrap;color:var(--muted);font-size:11px;margin-top:3px}.legend i{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px}.threshold{font-size:11px;color:#c4cee1;margin-top:7px}.footer{display:flex;justify-content:space-between;gap:12px;color:var(--muted);font-size:11px;margin-top:16px}.error{padding:20px;border:1px solid #8e4343;background:#361d25;border-radius:10px;color:#ffb7b7}@media(max-width:800px){.grid{grid-template-columns:1fr}.head{align-items:flex-start;flex-direction:column}.meta{text-align:left}}
</style></head><body><main><header class="head"><div><div class="eyebrow">Observability · structured logs</div><h1 id="title">Day 13 Monitoring Dashboard</h1><div class="unit">Metrics → Logs → Traces · six operational panels</div></div><div class="meta"><div id="range">Last 60 minutes</div><div id="updated">Loading data…</div></div></header><section id="grid" class="grid"></section><footer class="footer"><span>Source: data/logs.jsonl · refresh interval follows dashboard.yaml</span><span id="records"></span></footer></main>
<script>
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function drawChart(node,series,labels,threshold){const w=640,h=130,p=12,all=series.flatMap(s=>s.values.filter(v=>v!==null));if(!all.length){node.innerHTML='<div class="unit">No samples in the selected time range</div>';return}let max=Math.max(...all,threshold||0,0.001),min=Math.min(...all,0);if(max===min)max=min+1;const x=i=>p+(w-2*p)*(i/Math.max(1,labels.length-1)),y=v=>h-p-(h-2*p)*(v-min)/(max-min);let svg=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Metric trend chart">`;for(let i=0;i<4;i++){const gy=p+(h-2*p)*i/3;svg+=`<line x1="${p}" y1="${gy}" x2="${w-p}" y2="${gy}" stroke="#27324a" stroke-width="1"/>`}if(threshold!==null&&threshold!==undefined){svg+=`<line x1="${p}" y1="${y(threshold)}" x2="${w-p}" y2="${y(threshold)}" stroke="#f0b44c" stroke-dasharray="5 5" stroke-width="1.5"/>`}for(const s of series){let pts=s.values.map((v,i)=>v===null?null:`${x(i)},${y(v)}`).filter(Boolean).join(' ');if(pts)svg+=`<polyline points="${pts}" fill="none" stroke="${s.color}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>`;s.values.forEach((v,i)=>{if(v!==null)svg+=`<circle cx="${x(i)}" cy="${y(v)}" r="2.7" fill="${s.color}"/>`})}svg+='</svg>';node.innerHTML=svg}
function render(data){document.getElementById('title').textContent=data.title;document.getElementById('range').textContent=`Last ${data.time_range_minutes} minutes`;document.getElementById('updated').textContent=`Updated ${new Date(data.generated_at).toLocaleTimeString()}`;document.getElementById('records').textContent=`${data.log_records} log records in window`;const grid=document.getElementById('grid');grid.innerHTML='';for(const p of data.panels){const state=p.status===null?'unknown':p.status?'ok':'bad';const badge=p.status===null?'NO DATA':p.status?'WITHIN THRESHOLD':'OUTSIDE THRESHOLD';const card=document.createElement('article');card.className='card';card.innerHTML=`<div class="card-top"><div><h2>${esc(p.title)}</h2><div class="unit">Unit: ${esc(p.unit)}</div></div><span class="badge ${state}">${badge}</span></div><div class="stats">${p.metrics.map(m=>`<div class="stat"><label>${esc(m.label)}</label><strong>${esc(m.value)}</strong></div>`).join('')}</div><div class="chart"></div><div class="legend">${p.series.map(s=>`<span><i style="background:${s.color}"></i>${esc(s.name)}</span>`).join('')}<span><i style="background:#f0b44c"></i>Threshold</span></div><div class="threshold">Threshold: ${esc(p.threshold)}</div>`;grid.appendChild(card);drawChart(card.querySelector('.chart'),p.series,data.bucket_labels,p.chart_threshold)} }
async function refresh(){try{const response=await fetch('/api/data',{cache:'no-store'});if(!response.ok)throw new Error(`HTTP ${response.status}`);render(await response.json())}catch(error){document.getElementById('grid').innerHTML=`<div class="error">Dashboard data unavailable: ${esc(error.message)}. Check that data/logs.jsonl exists and contains valid JSON records.</div>`}}refresh();setInterval(refresh,30000);
</script></body></html>'''


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/data":
            body = json.dumps(build_dashboard_payload(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
        elif self.path in ("/", "/index.html"):
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
        else:
            body = b"Not found"
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[dashboard] {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Day 13 local monitoring dashboard")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Build a one-time dashboard snapshot and report panel values without starting the server.",
    )
    args = parser.parse_args()
    if args.check:
        payload = build_dashboard_payload()
        print(f"Dashboard snapshot: {len(payload['panels'])}/6 panels; {payload['log_records']} log records")
        for item in payload["panels"]:
            values = ", ".join(f"{metric['label']}={metric['value']}" for metric in item["metrics"])
            print(f"- {item['title']}: {values}")
        return

    host = "127.0.0.1"
    port = 8050
    print(f"Dashboard available at http://{host}:{port} (Ctrl+C to stop)")
    try:
        ThreadingHTTPServer((host, port), DashboardHandler).serve_forever()
    except KeyboardInterrupt:
        print("Dashboard stopped.")


if __name__ == "__main__":
    main()
