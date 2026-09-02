# Release-Gate Telemetry Dashboard

## Overview

The MammothOS telemetry engine provides real-time tracking of trust metrics for LLM provider responses. It enables operators to make informed release-gate decisions by monitoring:

- **Confidence levels** across providers
- **Contradiction rates** (disagreement between providers)
- **Citation coverage** (evidence-based responses)
- **Response latency** and provider health
- **Trend analysis** using rolling windows
- **Release readiness score** (0-100) with go/no-go recommendations

## Architecture

### Backend Components

#### 1. **TelemetryEngine** (`src/mammoth_os/telemetry_engine.py`)

A lightweight, thread-safe metrics tracker with:
- In-memory ring buffer (last 500 responses)
- Optional SQLite persistence
- Atomic recording without external dependencies
- Moving average and trend computation

Key classes:
- `TelemetryRecord`: Single provider response metric
- `TelemetryEngine`: Main engine with buffer, DB operations, analytics

Key methods:
- `record_response(provider, confidence, contradiction_count, citation_count, response_latency_ms)`
- `get_metrics_for_window(hours)` → aggregated metrics
- `get_trend(metric, hours, window_minutes)` → trend vector with direction
- `get_release_readiness()` → score 0-100 with recommendations
- `get_summary()` → complete dashboard snapshot

#### 2. **API Endpoints** (`api_server.py`)

Four RESTful endpoints for telemetry:

```
GET  /api/telemetry/trust-metrics
     Returns: { metrics, window_hours, timestamp }
     Query params: ?hours=2 (default)

GET  /api/telemetry/release-readiness
     Returns: { release_readiness: { ready, score, factors, recommendations } }

POST /api/telemetry/record
     Body: { provider, confidence, contradiction_count, citation_count, response_latency_ms }
     Returns: { status, recorded, timestamp }

GET  /api/telemetry/summary
     Returns: { data: { metrics, trends, release_readiness } }
     (Complete dashboard data)
```

### Frontend Components

#### **TelemetryPage.jsx** (`ui/.../pages/TelemetryPage.jsx`)

A React dashboard displaying:

1. **Release Readiness Gauge** (0-100)
   - Color-coded status: green (≥70), yellow (50-70), red (<50)
   - Scrollable recommendations when not ready

2. **Score Factors**
   - Confidence (must be ≥72%)
   - Contradiction rate (must be <8%)
   - Citation coverage (must be ≥2.5 per response)
   - Provider health (no critical provider errors)

3. **Metrics Cards**
   - Average confidence
   - Contradiction rate
   - Average citations
   - Response count

4. **Trend Charts**
   - Confidence over time
   - Contradiction rate over time
   - Visual trend direction (up/down/flat)

5. **Provider Health**
   - Per-provider confidence, contradictions, citations, latency
   - Expandable details for each provider

Auto-refreshes every 5 seconds for live monitoring.

## Usage Guide

### Recording Telemetry

Integration point: After an agent/provider generates a response, record its trust metrics:

```python
from mammoth_os.telemetry_engine import TelemetryEngine

engine = TelemetryEngine()

# After receiving a response from an LLM provider
engine.record_response(
    provider="gpt-4o-mini",
    confidence=0.87,
    contradiction_count=0,
    citation_count=3,
    response_latency_ms=245
)
```

Or via HTTP POST:

```bash
curl -X POST http://localhost:8000/api/telemetry/record \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "gpt-4o-mini",
    "confidence": 0.87,
    "contradiction_count": 0,
    "citation_count": 3,
    "response_latency_ms": 245
  }'
```

### Querying Metrics

Via HTTP GET:

```bash
# Get metrics for last 2 hours
curl http://localhost:8000/api/telemetry/trust-metrics?hours=2

# Check release readiness
curl http://localhost:8000/api/telemetry/release-readiness

# Get complete dashboard data
curl http://localhost:8000/api/telemetry/summary
```

In Python:

```python
from mammoth_os.telemetry_engine import TelemetryEngine

engine = TelemetryEngine()
metrics = engine.get_metrics_for_window(hours=2)
readiness = engine.get_release_readiness()
trend = engine.get_trend("confidence", hours=2)
```

### Dashboard Navigation

1. Click **Telemetry** in the sidebar (icon: bar chart)
2. View the release-readiness gauge at the top
3. Review factor scores and recommendations
4. Drill down into provider details
5. Observe trend patterns over time
6. Use "Refresh" button to force update

## Release Readiness Scoring

The engine computes a **release readiness score** (0-100) based on:

| Factor | Criteria | Weight | Status |
|--------|----------|--------|--------|
| Confidence | Avg ≥ 72% | 30% | Pass if ≥72%, else -30 pts |
| Contradiction Rate | < 8% | 25% | Pass if <8%, else -25 pts |
| Citation Coverage | Avg ≥ 2.5 | 25% | Pass if ≥2.5, else -25 pts |
| Provider Health | No critical errors | 20% | Pass if all providers ≥50% conf, else -20 pts |

**Recommendation:**
- ≥ 70 points: **READY FOR RELEASE** (green gauge)
- 50-70 points: **CAUTION** (yellow gauge)
- < 50 points: **NOT READY** (red gauge)

## Data Retention

- **In-memory buffer**: Last 500 responses (default)
- **SQLite persistence** (optional): All records with indexed timestamp/provider lookups
- **Retention window**: Queries typically use last 2 hours of data
- **Export**: Use `engine.export_records(hours=2)` for JSON export

## Configuration

### In api_server.py

```python
_telemetry = TelemetryEngine(
    db_path=None,           # None = in-memory only; set to Path for SQLite
    max_buffer_size=500     # Ring buffer size
)
```

### SQLite Setup

```python
from pathlib import Path

engine = TelemetryEngine(
    db_path=Path(".mammoth/telemetry.db"),
    max_buffer_size=500
)
```

Creates tables:
- `trust_telemetry` (provider, confidence, contradictions, citations, latency, timestamp)
- Indexed by timestamp and provider for fast queries

## Integration Examples

### Example 1: Agent Response Handler

```python
async def handle_provider_response(provider_name, response_data):
    """Record metrics after agent response."""
    engine.record_response(
        provider=provider_name,
        confidence=response_data.get("confidence_score", 0.5),
        contradiction_count=response_data.get("contradictions", 0),
        citation_count=len(response_data.get("citations", [])),
        response_latency_ms=response_data.get("latency_ms", 0)
    )
    return response_data
```

### Example 2: Release Gate Decision

```python
def check_release_gate():
    """Determine if system is ready for release."""
    readiness = engine.get_release_readiness()
    
    if readiness['ready']:
        print("✓ System ready for release")
        print(f"  Score: {readiness['score']:.1f}/100")
        return True
    else:
        print("✗ System not ready")
        for rec in readiness['recommendations']:
            print(f"  - {rec}")
        return False
```

### Example 3: Provider Performance Dashboard

```python
def get_provider_report():
    """Generate provider comparison report."""
    metrics = engine.get_metrics_for_window(hours=2)
    
    for provider, stats in metrics['provider_breakdown'].items():
        print(f"{provider}:")
        print(f"  Responses: {stats['count']}")
        print(f"  Confidence: {stats['avg_confidence']:.2%}")
        print(f"  Citations: {stats['avg_citations']:.1f}")
        print(f"  Latency: {stats['avg_latency_ms']:.0f}ms")
```

## Performance Characteristics

- **Recording**: O(1) — instant append to ring buffer
- **Metrics query**: O(n) — single pass over buffer
- **Trend computation**: O(n log n) — bucketing + linear regression
- **Release readiness**: O(n) — aggregates all factors
- **Memory footprint**: ~500 records × ~150 bytes ≈ 75 KB

Thread-safe with RLock for concurrent access.

## Observability

Monitor telemetry engine health via dashboard:
- Record count (total metrics accumulated)
- Provider distribution (pie chart)
- Trend direction (up/down/flat)
- Factor status (pass/fail)
- Live recommendations

## Testing

Run included tests:

```bash
python test_telemetry.py    # Unit tests for engine
python verify_api_setup.py  # Verify backend endpoints
python verify_ui_setup.py   # Verify frontend integration
```

## Future Enhancements

1. **Advanced Analytics**
   - Anomaly detection (sudden confidence drops)
   - Correlation analysis (latency vs. citations)
   - Provider clustering by performance

2. **Alerting**
   - Email/Slack notifications on readiness changes
   - Critical threshold alerts (confidence < 60%)

3. **Historical Reports**
   - Weekly summaries
   - Release-to-release comparison
   - Provider SLA tracking

4. **Integrations**
   - Webhook callbacks for release gates
   - Datadog/Prometheus metrics export
   - GitHub Actions gating (API query before merge)

## Support

For questions or issues:
1. Check the API documentation at `GET /api/status`
2. Review telemetry logs in `.mammoth/telemetry.db` (if SQLite enabled)
3. Run diagnostic checks: `python verify_api_setup.py && python verify_ui_setup.py`
