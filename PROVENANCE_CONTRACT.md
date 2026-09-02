# Provenance Contract Enforcement

## Overview

The Provenance Contract system enforces server-side validation on every agent/tutor/research output before shipping responses to clients. This prevents "trust-blind" outputs by ensuring providers, confidence levels, citations, and contradictions are present and meet minimum quality thresholds.

## Architecture

### Components

1. **ProvenanceContract** (`src/mammoth_os/provenance_contract.py`)
   - Core validation engine
   - Configurable thresholds via environment variables
   - Conservative (warn) and strict (block) enforcement modes

2. **Response Validation**
   - Checks for required fields: `provider`, `confidence`, `citations`, `contradictions`
   - Type-specific rules: research outputs require citations, tutors should cite sources
   - Confidence scoring and threshold enforcement

3. **Trust Metadata**
   - Attached to every response before release
   - Includes validation status, provider info, citation count, contradiction flags
   - Client-renderable trust badges

4. **Telemetry Collection**
   - Tracks all validation results to JSON file: `.mammoth/trust_metrics.json`
   - Provides `/api/telemetry/provenance-metrics` endpoint for operator review
   - Aggregates trends across providers and response types

## Integration Points

### API Endpoints Enhanced

1. **`/api/atlas/submit`** (Tutor responses)
   - Provider: `atlas-tutor`
   - Confidence: 0.85 (high for structured exercises)
   - Citations: Exercise library, Curriculum standards
   - Response type: `tutor`

2. **`/api/run`** (Agent execution)
   - Provider: Runtime agent name (e.g., `coding`, `research`)
   - Confidence: Inverse of temperature (1.0 - temperature)
   - Citations: Added by agent if applicable
   - Response type: `coding`, `research`, or `general`

3. **`/api/plan-execute`** (Orchestrated workflows)
   - Provider: `orchestrator`
   - Confidence: 0.9 if completed, 0.6 if pending/failed
   - Citations: Plan step execution, Task tracking
   - Response type: `general`

### New Telemetry Endpoint

**`GET /api/telemetry/provenance-metrics`**
- Query params:
  - `limit` (int, default 100): Max metrics to return
  - `hours` (int, default 24): Time window in hours
- Returns: List of validation records + aggregate stats
- Access: Admin only

## Configuration

### Environment Variables

```bash
# Minimum confidence threshold (0.0-1.0, default 0.5)
TRUST_MIN_CONFIDENCE=0.5

# Minimum citations required for research outputs (default 2)
TRUST_MIN_CITATIONS_RESEARCH=2

# Enable strict mode (block low-trust responses)
# Default: false (conservative mode - warn only)
TRUST_STRICT_MODE=false

# Log all validations for debugging
TRUST_LOG_ALL=false
```

### Thresholds

- **Confidence**: Responses below 0.5 are flagged as low-confidence
- **Citations (research)**: < 2 citations triggers warning
- **Contradictions**: Presence of contradictions with high confidence triggers warning
- **Release gate**: In strict mode, responses missing critical fields are blocked

## Response Structure

### Input Response (Before Validation)

```python
{
    "status": "ok",
    "result": {...},
    # Trust fields (required)
    "provider": "atlas-tutor",      # Which service provided this
    "confidence": 0.85,              # 0.0-1.0 certainty level
    "citations": [...],              # Evidence/sources
    "contradictions": []             # Internal conflicts/caveats
}
```

### Output Response (After Wrapping)

```python
{
    "status": "ok",
    "result": {...},
    "provider": "atlas-tutor",
    "confidence": 0.85,
    "citations": [...],
    "contradictions": [],
    
    # Added trust metadata
    "trust_metadata": {
        "validated_at": "2026-09-02T07:51:42.157529+00:00",
        "response_type": "tutor",
        "validation_issues": [...],     # Any warnings/issues
        "validation_passed": true,      # Overall validation result
        "provider": "atlas-tutor",
        "confidence": 0.85,
        "citation_count": 2,
        "has_contradictions": false,
        "evidence_breadth": "moderate"  # limited/moderate/broad
    },
    
    # Optional warning flag (conservative mode)
    "trust_warning": false,
    "trust_warning_reason": null
}
```

## Usage Examples

### Basic Validation

```python
from mammoth_os.provenance_contract import validate_response, enforce_on_release

response = {
    "provider": "research-agent",
    "confidence": 0.92,
    "citations": ["arxiv.org/1234", "scholar.google.com/xyz"],
    "contradictions": [],
    "content": "Research finding"
}

# Validate without enforcement
is_valid, issues = validate_response(response, response_type="research")
print(f"Valid: {is_valid}, Issues: {issues}")

# Enforce before release
should_release, block_reason, metadata = enforce_on_release(response, response_type="research")
if should_release:
    print("Response approved for release")
else:
    print(f"Response blocked: {block_reason}")
```

### Adding Trust Metadata

```python
from mammoth_os.provenance_contract import add_trust_metadata

response = {
    "content": "Bare response without trust fields"
}

# Add minimal trust metadata with defaults
enhanced = add_trust_metadata(response)
# Now has: provider, confidence, citations, contradictions, etc.
```

### Using in API Endpoints

```python
# In api_server.py endpoint handler
response = {
    "status": "ok",
    "result": result,
    "provider": "my-agent",
    "confidence": 0.8,
    "citations": ["source1", "source2"],
    "contradictions": [],
}

# Wrap with trust validation
return _wrap_response_with_trust(response, endpoint="/api/my-endpoint", response_type="general")
```

## Response Types

### `general` (default)
- No specific requirements beyond basic fields
- Used for command results, utility responses

### `tutor`
- Represents educational content
- Should include citations for learning sources
- Confidence indicates pedagogical certainty

### `research`
- Requires citations (minimum 2)
- Should list contradictions/caveats
- Broader evidence breadth preferred

### `coding`
- Code generation and technical solutions
- Confidence reflects solution certainty
- May have fewer citations

## Validation Rules by Type

| Field | General | Tutor | Research | Coding |
|-------|---------|-------|----------|--------|
| provider | Required | Required | Required | Required |
| confidence | Required | Required | Required | Required |
| citations | Optional | Recommended | Required (2+) | Optional |
| contradictions | Optional | Optional | Recommended | Optional |

## Telemetry & Monitoring

### Trust Metrics File

Location: `.mammoth/trust_metrics.json`

Each record contains:
```python
{
    "timestamp": "ISO-8601",
    "endpoint": "/api/endpoint",
    "response_type": "general|tutor|research|coding",
    "provider": "provider-name",
    "confidence": 0.0-1.0,
    "issue_count": int,
    "validation_passed": bool,
    "issues_sample": [str, ...]  # First 2 issues
}
```

### Querying Metrics

```bash
# Get last 100 validation records from past 24 hours
curl http://localhost:8000/api/telemetry/provenance-metrics?limit=100&hours=24

# Response includes:
# - metrics: List of validation records
# - aggregate.pass_rate: % of validations that passed
# - aggregate.avg_confidence: Average confidence across responses
# - aggregate.providers: Distribution of responses by provider
```

### Interpreting Results

```python
{
    "aggregate": {
        "total": 1250,
        "passed": 1200,
        "failed": 50,
        "pass_rate": 0.96,                      # 96% pass rate
        "avg_confidence": 0.847,                # Average confidence
        "providers": {
            "gpt-4o": 600,
            "atlas-tutor": 400,
            "research-agent": 250
        }
    }
}
```

- **Pass rate > 95%**: Healthy trust profile
- **Pass rate 85-95%**: Warning threshold
- **Pass rate < 85%**: Investigation needed
- **Avg confidence < 0.7**: Low confidence period
- **Provider distribution shifts**: Monitor for degradation

## Strict vs Conservative Mode

### Conservative Mode (Default)

- ✅ All responses released
- ⚠️ Issues flagged in `trust_metadata`
- 📊 Warnings visible to client via `trust_warning` field
- 🎯 Use for: Production with client-side rendering of trust badges

```
TRUST_STRICT_MODE=false
```

### Strict Mode

- 🚫 Responses blocked if critical issues detected
- 📋 List of blocking issues returned
- ⚠️ Original response preserved in error response
- 🎯 Use for: Approval gates, research publication, regulated outputs

```
TRUST_STRICT_MODE=true
```

## Testing

### Unit Tests

```bash
pytest tests/test_provenance_contract.py -v
```

Coverage:
- Response validation (valid, missing fields, out-of-range)
- Type-specific rules (research citations, confidence threshold)
- Contradiction handling
- Trust metadata generation
- Custom thresholds via environment

### Integration Tests

```bash
pytest tests/test_provenance_integration.py -v
```

Coverage:
- Real API response structures
- Endpoint-specific validation
- Telemetry recording
- Aggregation and analytics

### Running All Tests

```bash
pytest tests/test_provenance*.py -v
```

## Known Limitations

1. **Shallow citation validation**: System counts citations but doesn't verify validity
2. **No schema enforcement**: Responses can add extra fields without validation
3. **Provider trust not verified**: System trusts provider name claims
4. **No historical trending**: Aggregate stats are point-in-time, not trending over time
5. **Limited NLP analysis**: Contradiction detection is field-based, not semantic

## Future Enhancements

- [ ] Semantic contradiction detection via embeddings
- [ ] Provider reputation tracking (failure rates, response time)
- [ ] Citation validity checking (URL verification, metadata extraction)
- [ ] Confidence calibration via user feedback
- [ ] Machine learning-based anomaly detection
- [ ] Integration with approval workflows for low-confidence outputs
- [ ] Dashboard for trust metrics visualization
- [ ] Automatic alert system for trust degradation

## Debugging

### Enable All Logging

```bash
export TRUST_LOG_ALL=true
```

### Check Validation Details

```python
from mammoth_os.provenance_contract import validate_response

is_valid, issues = validate_response(response, response_type="research")
for issue in issues:
    print(f"  - {issue}")
```

### Review Telemetry Directly

```bash
# View last 50 metrics
curl 'http://localhost:8000/api/telemetry/provenance-metrics?limit=50'

# View last 7 days
curl 'http://localhost:8000/api/telemetry/provenance-metrics?hours=168'
```

## Related Documentation

- [Runtime Contracts](./AGENTS.md) - Contract versioning for agents
- [Telemetry Engine](./src/mammoth_os/telemetry_engine.py) - Broader observability system
- [Release Gates](./ATLAS_MANUAL.md) - Approval workflows and quality gates
