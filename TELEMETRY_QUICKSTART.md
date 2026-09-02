# Quick Start: Release-Gate Telemetry Dashboard

## 🚀 Launch the Dashboard

1. **Start the backend:**
   ```bash
   uvicorn api_server:app --reload
   ```

2. **Start the UI (in another terminal):**
   ```bash
   cd ui/mad-architecht-command-center
   npm run dev
   ```

3. **Open the dashboard:**
   - Navigate to http://localhost:5173 (or 5174)
   - Click "Telemetry" in the sidebar (bar chart icon)

## 📊 Record Your First Metrics

### Option 1: Python API
```python
from mammoth_os.telemetry_engine import TelemetryEngine

engine = TelemetryEngine()

# Record a response from GPT
engine.record_response(
    provider="gpt-4o-mini",
    confidence=0.92,
    contradiction_count=0,
    citation_count=4,
    response_latency_ms=156
)

# Record a response from Claude
engine.record_response(
    provider="claude-3.5-sonnet",
    confidence=0.88,
    contradiction_count=0,
    citation_count=3,
    response_latency_ms=189
)

# Check if system is ready for release
readiness = engine.get_release_readiness()
print(f"Ready: {readiness['ready']}")
print(f"Score: {readiness['score']}/100")
```

### Option 2: HTTP API
```bash
# Record metric
curl -X POST http://localhost:8000/api/telemetry/record \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "gpt-4o-mini",
    "confidence": 0.92,
    "contradiction_count": 0,
    "citation_count": 4,
    "response_latency_ms": 156
  }'

# Check release readiness
curl http://localhost:8000/api/telemetry/release-readiness

# Get full summary
curl http://localhost:8000/api/telemetry/summary
```

## 📈 Understanding the Dashboard

### Release Readiness Gauge
- **GREEN (≥70)**: Ready for release ✅
- **YELLOW (50-70)**: Caution, review issues ⚠️
- **RED (<50)**: Not ready, fix issues ❌

### Score Factors
| Factor | Minimum | Your Status |
|--------|---------|-------------|
| Confidence | 72% | Shows if pass/fail |
| Contradiction Rate | <8% | Shows if pass/fail |
| Citation Coverage | ≥2.5 avg | Shows if pass/fail |
| Provider Health | No critical errors | Shows if pass/fail |

### Trends
- **UP** (green ↑): Metric improving
- **DOWN** (red ↓): Metric degrading  
- **FLAT** (gray →): Metric stable

## 🔧 Integration with Your Code

### In Your Agent Handler
```python
# After getting a response from an LLM provider
async def handle_provider_response(provider, response):
    # Calculate metrics from response
    confidence = response.get('confidence_score', 0.5)
    contradictions = detect_contradictions(response)
    citations = extract_citations(response)
    latency = response.get('latency_ms', 0)
    
    # Record telemetry
    from api_server import _telemetry
    _telemetry.record_response(
        provider=provider,
        confidence=confidence,
        contradiction_count=contradictions,
        citation_count=citations,
        response_latency_ms=latency
    )
    
    return response
```

### Release Gate Decision
```python
def should_release():
    """Determine if system is ready for production release."""
    from api_server import _telemetry
    
    readiness = _telemetry.get_release_readiness()
    
    if readiness['ready']:
        print("✓ System ready for release")
        return True
    else:
        print("✗ Issues found:")
        for rec in readiness['recommendations']:
            print(f"  - {rec}")
        return False
```

## 📊 Monitoring Best Practices

1. **Warm up with data** (5-10 minutes of responses) before making release decisions
2. **Review trends** — is confidence improving or degrading?
3. **Check provider breakdown** — are all providers performing well?
4. **Watch for contradictions** — if rate jumps, investigate
5. **Monitor latency** — can indicate provider issues

## 🔍 Troubleshooting

**Dashboard shows no data?**
- Wait 2-3 seconds for initial API call
- Check browser console for errors
- Verify backend is running on :8000

**Endpoint returns 403 Forbidden?**
- Add your email to MAMMOTH_ADMIN_EMAILS in .env
- Or set MAMMOTH_REQUIRE_AUTH=false for dev

**Metrics not updating?**
- Click "Refresh" button in dashboard
- Check that record_response() is being called
- Verify no exceptions in backend logs

## 📚 More Documentation

- **Full Guide:** See `TELEMETRY_GUIDE.md`
- **Implementation Details:** See `TELEMETRY_IMPLEMENTATION.md`
- **Completion Summary:** See `TELEMETRY_COMPLETE.md`

---

**Ready to monitor trust metrics and gate releases!** 🎯
