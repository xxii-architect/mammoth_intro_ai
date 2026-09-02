"""
Telemetry Engine — Release-gate trust metrics tracking and analysis.

Tracks provider confidence, contradiction rates, citation coverage, and response latency
over a rolling window. Computes moving averages and confidence intervals.
Supports in-memory ring buffer and optional SQLite persistence.
"""
from __future__ import annotations

import datetime
import json
import sqlite3
import statistics
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class TelemetryRecord:
    """Single telemetry record for a provider response."""

    def __init__(
        self,
        provider: str,
        confidence: float,
        contradiction_count: int,
        citation_count: int,
        response_latency_ms: float,
        timestamp: Optional[datetime.datetime] = None,
    ):
        self.provider = provider
        self.confidence = max(0.0, min(1.0, confidence))
        self.contradiction_count = max(0, contradiction_count)
        self.citation_count = max(0, citation_count)
        self.response_latency_ms = max(0.0, response_latency_ms)
        self.timestamp = timestamp or datetime.datetime.now(datetime.timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "confidence": self.confidence,
            "contradiction_count": self.contradiction_count,
            "citation_count": self.citation_count,
            "response_latency_ms": self.response_latency_ms,
            "timestamp": self.timestamp.isoformat(),
        }


class TelemetryEngine:
    """
    Track and analyze trust metrics for release-gate decisions.
    In-memory ring buffer + optional SQLite backend for persistence.
    """

    MAX_BUFFER_SIZE = 500

    def __init__(self, db_path: Optional[Path] = None, max_buffer_size: int = MAX_BUFFER_SIZE):
        self._buffer: deque = deque(maxlen=max_buffer_size)
        self._max_buffer_size = max_buffer_size
        self._db_path = db_path
        self._lock = threading.RLock()
        self._initialized = False

        if self._db_path:
            self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite table if DB path is provided."""
        if not self._db_path or self._initialized:
            return

        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS trust_telemetry (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        provider TEXT NOT NULL,
                        confidence REAL NOT NULL,
                        contradiction_count INTEGER NOT NULL,
                        citation_count INTEGER NOT NULL,
                        response_latency_ms REAL NOT NULL,
                        timestamp TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_timestamp 
                    ON trust_telemetry(timestamp)
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_provider 
                    ON trust_telemetry(provider)
                    """
                )
                conn.commit()
            self._initialized = True
        except Exception as e:
            print(f"Warning: Failed to initialize telemetry DB: {e}")

    def record_response(
        self,
        provider: str,
        confidence: float,
        contradiction_count: int,
        citation_count: int,
        response_latency_ms: float,
    ) -> None:
        """Record a response from a provider with trust metrics."""
        record = TelemetryRecord(
            provider=provider,
            confidence=confidence,
            contradiction_count=contradiction_count,
            citation_count=citation_count,
            response_latency_ms=response_latency_ms,
        )

        with self._lock:
            self._buffer.append(record)

            if self._db_path and self._initialized:
                try:
                    with sqlite3.connect(str(self._db_path)) as conn:
                        conn.execute(
                            """
                            INSERT INTO trust_telemetry
                            (provider, confidence, contradiction_count, citation_count, 
                             response_latency_ms, timestamp)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                record.provider,
                                record.confidence,
                                record.contradiction_count,
                                record.citation_count,
                                record.response_latency_ms,
                                record.timestamp.isoformat(),
                            ),
                        )
                        conn.commit()
                except Exception as e:
                    print(f"Warning: Failed to persist telemetry record: {e}")

    def get_metrics_for_window(self, hours: int = 2) -> Dict[str, Any]:
        """
        Get aggregated metrics for the last N hours.
        Returns confidence avg, contradiction rate, citation coverage, and provider breakdown.
        """
        cutoff_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)

        with self._lock:
            records = [r for r in self._buffer if r.timestamp >= cutoff_time]

        if not records:
            return {
                "window_hours": hours,
                "record_count": 0,
                "avg_confidence": 0.0,
                "contradiction_rate": 0.0,
                "avg_citation_count": 0.0,
                "avg_latency_ms": 0.0,
                "provider_breakdown": {},
                "providers_represented": [],
            }

        provider_metrics: Dict[str, Dict[str, Any]] = {}
        for record in records:
            if record.provider not in provider_metrics:
                provider_metrics[record.provider] = {
                    "confidences": [],
                    "contradictions": [],
                    "citations": [],
                    "latencies": [],
                    "count": 0,
                }
            pm = provider_metrics[record.provider]
            pm["confidences"].append(record.confidence)
            pm["contradictions"].append(record.contradiction_count)
            pm["citations"].append(record.citation_count)
            pm["latencies"].append(record.response_latency_ms)
            pm["count"] += 1

        confidences = [r.confidence for r in records]
        all_contradictions = [r.contradiction_count for r in records]
        all_citations = [r.citation_count for r in records]
        all_latencies = [r.response_latency_ms for r in records]

        total_contradictions = sum(all_contradictions)
        avg_confidence = statistics.mean(confidences) if confidences else 0.0
        contradiction_rate = total_contradictions / len(records) if records else 0.0
        avg_citation_count = statistics.mean(all_citations) if all_citations else 0.0
        avg_latency_ms = statistics.mean(all_latencies) if all_latencies else 0.0

        provider_breakdown = {}
        for provider, metrics in provider_metrics.items():
            provider_breakdown[provider] = {
                "count": metrics["count"],
                "avg_confidence": statistics.mean(metrics["confidences"]),
                "avg_contradictions": statistics.mean(metrics["contradictions"]),
                "avg_citations": statistics.mean(metrics["citations"]),
                "avg_latency_ms": statistics.mean(metrics["latencies"]),
            }

        return {
            "window_hours": hours,
            "record_count": len(records),
            "avg_confidence": round(avg_confidence, 4),
            "contradiction_rate": round(contradiction_rate, 4),
            "avg_citation_count": round(avg_citation_count, 2),
            "avg_latency_ms": round(avg_latency_ms, 2),
            "provider_breakdown": provider_breakdown,
            "providers_represented": sorted(provider_metrics.keys()),
        }

    def get_trend(self, metric: str, hours: int = 2, window_minutes: int = 15) -> Dict[str, Any]:
        """
        Compute trend vector for a metric over time using rolling windows.
        metric: 'confidence', 'contradiction_rate', 'citation_count', 'latency_ms'
        Returns a list of (timestamp, value) tuples and trend direction.
        """
        cutoff_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)

        with self._lock:
            records = [r for r in self._buffer if r.timestamp >= cutoff_time]

        if not records:
            return {
                "metric": metric,
                "trend": "flat",
                "trend_direction": 0.0,
                "data_points": [],
                "window_minutes": window_minutes,
            }

        records_sorted = sorted(records, key=lambda r: r.timestamp)

        buckets: Dict[datetime.datetime, List[TelemetryRecord]] = {}
        for record in records_sorted:
            bucket_key = record.timestamp.replace(
                minute=(record.timestamp.minute // window_minutes) * window_minutes,
                second=0,
                microsecond=0,
            )
            if bucket_key not in buckets:
                buckets[bucket_key] = []
            buckets[bucket_key].append(record)

        data_points = []
        for bucket_time in sorted(buckets.keys()):
            bucket_records = buckets[bucket_time]

            if metric == "confidence":
                confidences = [r.confidence for r in bucket_records]
                value = statistics.mean(confidences) if confidences else 0.0
            elif metric == "contradiction_rate":
                total_contradictions = sum(r.contradiction_count for r in bucket_records)
                value = total_contradictions / len(bucket_records) if bucket_records else 0.0
            elif metric == "citation_count":
                citations = [r.citation_count for r in bucket_records]
                value = statistics.mean(citations) if citations else 0.0
            elif metric == "latency_ms":
                latencies = [r.response_latency_ms for r in bucket_records]
                value = statistics.mean(latencies) if latencies else 0.0
            else:
                value = 0.0

            data_points.append(
                {
                    "timestamp": bucket_time.isoformat(),
                    "value": round(value, 4),
                }
            )

        trend_direction = self._compute_trend_direction(data_points)

        if trend_direction > 0.05:
            trend = "up"
        elif trend_direction < -0.05:
            trend = "down"
        else:
            trend = "flat"

        return {
            "metric": metric,
            "trend": trend,
            "trend_direction": round(trend_direction, 4),
            "data_points": data_points,
            "window_minutes": window_minutes,
        }

    @staticmethod
    def _compute_trend_direction(data_points: List[Dict[str, Any]]) -> float:
        """
        Compute trend direction using linear regression on (index, value).
        Returns slope normalized to [-1, 1] range.
        """
        if len(data_points) < 2:
            return 0.0

        values = [p["value"] for p in data_points]
        indices = list(range(len(values)))

        n = len(indices)
        sum_x = sum(indices)
        sum_y = sum(values)
        sum_xy = sum(i * v for i, v in zip(indices, values))
        sum_x2 = sum(i * i for i in indices)

        denominator = n * sum_x2 - sum_x * sum_x
        if denominator == 0:
            return 0.0

        slope = (n * sum_xy - sum_x * sum_y) / denominator
        max_value = max(values) if max(values) != 0 else 1.0
        normalized_slope = slope / max_value
        return max(-1.0, min(1.0, normalized_slope))

    def get_release_readiness(self) -> Dict[str, Any]:
        """
        Compute release-readiness score (0-100) based on trust metrics.
        Factors:
          - Confidence trend (must be >= 0.72 avg)
          - Contradiction rate (must be < 8%)
          - Citation coverage (avg >= 2.5 citations per response)
          - No critical provider errors in last 2 hours
        """
        metrics = self.get_metrics_for_window(hours=2)

        score = 100.0
        factors = {}
        recommendations = []

        avg_confidence = metrics.get("avg_confidence", 0.0)
        if avg_confidence >= 0.72:
            factors["confidence"] = {"value": avg_confidence, "status": "pass", "weight": 0.3}
        else:
            score -= 30
            factors["confidence"] = {
                "value": avg_confidence,
                "status": "fail",
                "weight": 0.3,
            }
            recommendations.append(
                f"Confidence {avg_confidence:.2%} is below minimum 72%. "
                "Wait for more stable provider responses."
            )

        contradiction_rate = metrics.get("contradiction_rate", 0.0)
        if contradiction_rate < 0.08:
            factors["contradiction_rate"] = {
                "value": contradiction_rate,
                "status": "pass",
                "weight": 0.25,
            }
        else:
            score -= 25
            factors["contradiction_rate"] = {
                "value": contradiction_rate,
                "status": "fail",
                "weight": 0.25,
            }
            recommendations.append(
                f"Contradiction rate {contradiction_rate:.2%} exceeds threshold (8%). "
                "Investigate provider disagreement patterns."
            )

        avg_citation_count = metrics.get("avg_citation_count", 0.0)
        if avg_citation_count >= 2.5:
            factors["citation_coverage"] = {
                "value": avg_citation_count,
                "status": "pass",
                "weight": 0.25,
            }
        else:
            score -= 25
            factors["citation_coverage"] = {
                "value": avg_citation_count,
                "status": "fail",
                "weight": 0.25,
            }
            recommendations.append(
                f"Average citations ({avg_citation_count:.1f}) below minimum (2.5). "
                "Verify source attribution."
            )

        provider_breakdown = metrics.get("provider_breakdown", {})
        critical_errors = []
        for provider, pmetrics in provider_breakdown.items():
            avg_provider_confidence = pmetrics.get("avg_confidence", 0.0)
            if avg_provider_confidence < 0.5:
                critical_errors.append(f"{provider}: low confidence ({avg_provider_confidence:.2%})")

        if not critical_errors:
            factors["provider_health"] = {
                "value": "healthy",
                "status": "pass",
                "weight": 0.2,
            }
        else:
            score -= 20
            factors["provider_health"] = {
                "value": critical_errors,
                "status": "fail",
                "weight": 0.2,
            }
            for error in critical_errors:
                recommendations.append(f"Provider health issue: {error}")

        score = max(0.0, min(100.0, score))

        return {
            "ready": score >= 70.0,
            "score": round(score, 1),
            "factors": factors,
            "recommendations": recommendations,
            "record_count": metrics.get("record_count", 0),
            "window_hours": 2,
        }

    def get_summary(self) -> Dict[str, Any]:
        """Return a complete telemetry summary for the dashboard."""
        metrics = self.get_metrics_for_window(hours=2)
        trend_confidence = self.get_trend("confidence", hours=2)
        trend_contradictions = self.get_trend("contradiction_rate", hours=2)
        readiness = self.get_release_readiness()

        return {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "metrics": metrics,
            "trends": {
                "confidence": trend_confidence,
                "contradiction_rate": trend_contradictions,
            },
            "release_readiness": readiness,
        }

    def clear(self) -> None:
        """Clear all in-memory records."""
        with self._lock:
            self._buffer.clear()

    def export_records(self, hours: int = 2) -> List[Dict[str, Any]]:
        """Export raw records from the last N hours as JSON-serializable dicts."""
        cutoff_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)

        with self._lock:
            records = [
                r.to_dict()
                for r in self._buffer
                if r.timestamp >= cutoff_time
            ]

        return sorted(records, key=lambda r: r["timestamp"], reverse=True)
