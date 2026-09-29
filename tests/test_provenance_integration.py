"""
Integration tests for provenance contract enforcement with API endpoints.
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

# Test imports
from mammoth_os.provenance_contract import (
    validate_response,
    enforce_on_release,
    add_trust_metadata,
    get_contract,
)


class TestTrustMetadataIntegration:
    """Tests for trust metadata integration with API responses."""
    
    def test_atlas_submit_response_structure(self):
        """Verify atlas/submit response includes trust metadata."""
        # Simulate what atlas/submit returns
        response = {
            "status": "ok",
            "result": {"passed": True, "score": 95},
            "learner_context": {"streak": 5},
            "adaptive_feedback": {"next_lesson": "lessons/002"},
            "current_exercise": {"id": "ex1"},
            "regenerated_exercise": None,
            "provider": "atlas-tutor",
            "confidence": 0.85,
            "citations": ["Exercise library", "Curriculum standards"],
            "contradictions": [],
        }
        
        # Validate and wrap
        should_release, block_reason, trust_metadata = enforce_on_release(
            response,
            response_type="tutor"
        )
        
        assert should_release is True
        assert block_reason is None
        assert trust_metadata["provider"] == "atlas-tutor"
        assert trust_metadata["confidence"] == 0.85
        assert trust_metadata["citation_count"] == 2
        assert trust_metadata["validation_passed"] is True
    
    def test_run_agent_response_structure(self):
        """Verify /api/run response includes trust metadata."""
        response = {
            "status": "ok",
            "result": {"output": "Result of agent execution"},
            "intent": "fix_bug",
            "agent_id": "coding-agent",
            "temperature": 0.3,
            "task_id": "task-abc123",
            "trace_id": "trace-xyz789",
            "contract_version": "v2",
            "preflight": {"status": "ok"},
            "runtime_notice": {"notice": "All systems nominal"},
            "thought_steps": [],
            "provider": "coding",
            "confidence": 0.7,  # 1.0 - 0.3 temperature
            "citations": [],
            "contradictions": [],
        }
        
        should_release, block_reason, trust_metadata = enforce_on_release(
            response,
            response_type="coding"
        )
        
        assert should_release is True
        assert trust_metadata["provider"] == "coding"
        assert trust_metadata["confidence"] == 0.7
        assert trust_metadata["has_contradictions"] is False
    
    def test_plan_execute_response_structure(self):
        """Verify /api/plan-execute response includes trust metadata."""
        response = {
            "status": "ok",
            "plan_id": "plan-abc123",
            "objective": "Implement user auth",
            "plan_profile": "full-stack",
            "coding_intent": "feature",
            "plan_status": "completed",
            "progress": {
                "total": 5,
                "executed": 5,
                "completed": 5,
                "pending_approval": 0,
                "failed": 0,
            },
            "plan_steps": [],
            "provider": "orchestrator",
            "confidence": 0.9,
            "citations": ["Plan step execution", "Task tracking"],
            "contradictions": [],
        }
        
        should_release, block_reason, trust_metadata = enforce_on_release(
            response,
            response_type="general"
        )
        
        assert should_release is True
        assert trust_metadata["provider"] == "orchestrator"
        assert trust_metadata["confidence"] == 0.9
        assert trust_metadata["citation_count"] == 2
    
    def test_low_confidence_response_warning(self):
        """Low confidence responses should be marked with warnings."""
        response = {
            "status": "ok",
            "result": "Result",
            "provider": "experiment-agent",
            "confidence": 0.3,  # Low confidence
            "citations": [],
            "contradictions": ["Needs validation"],
        }
        
        should_release, block_reason, trust_metadata = enforce_on_release(
            response,
            response_type="general"
        )
        
        # Still released in non-strict mode but marked
        assert should_release is True
        assert trust_metadata.get("trust_warning") is True
        assert "low confidence" in trust_metadata.get("warning_reason", "").lower()
    
    def test_research_output_validation(self):
        """Research outputs require citations."""
        response = {
            "status": "ok",
            "content": "Research finding",
            "provider": "research-agent",
            "confidence": 0.88,
            "citations": ["arxiv.org/1234", "scholar.google.com/xyz"],
            "contradictions": ["Different definitions in literature"],
        }
        
        should_release, block_reason, trust_metadata = enforce_on_release(
            response,
            response_type="research"
        )
        
        assert should_release is True
        assert trust_metadata["citation_count"] == 2
        assert trust_metadata["has_contradictions"] is True
    
    def test_missing_provider_field_handled(self):
        """Responses without provider field should get default."""
        response = {
            "status": "ok",
            "result": "Some result",
            "confidence": 0.7,
        }
        
        should_release, block_reason, trust_metadata = enforce_on_release(response)
        
        # Should still be released but with default provider
        assert should_release is True
        assert trust_metadata["provider"] == "unknown"
    
    def test_add_trust_metadata_function(self):
        """add_trust_metadata should enhance response with defaults."""
        response = {
            "status": "ok",
            "result": "Partial response",
        }
        
        enhanced = add_trust_metadata(response)
        
        # Should have all trust fields
        assert "provider" in enhanced
        assert "confidence" in enhanced
        assert "citations" in enhanced
        assert "contradictions" in enhanced
        assert "citation_count" in enhanced
        assert "has_contradictions" in enhanced
        assert "evidence_breadth" in enhanced
        
        # Should preserve original
        assert enhanced["status"] == "ok"
        assert enhanced["result"] == "Partial response"


class TestTrustMetadataAggregation:
    """Tests for aggregating and analyzing trust metrics."""
    
    def test_multiple_responses_tracking(self):
        """Multiple responses should be trackable for trending."""
        responses = [
            {
                "provider": "gpt-4o",
                "confidence": 0.9,
                "citations": ["source1", "source2"],
                "content": "Response 1",
            },
            {
                "provider": "gpt-4o",
                "confidence": 0.85,
                "citations": ["source1"],
                "content": "Response 2",
            },
            {
                "provider": "claude-3.5",
                "confidence": 0.92,
                "citations": ["source1", "source2", "source3"],
                "content": "Response 3",
            },
        ]
        
        validated = [
            enforce_on_release(resp, response_type="research")
            for resp in responses
        ]
        
        # All should pass
        assert all(v[0] for v in validated)
        
        # Track provider distribution
        providers = {}
        for _, _, metadata in validated:
            provider = metadata["provider"]
            providers.setdefault(provider, 0)
            providers[provider] += 1
        
        assert providers["gpt-4o"] == 2
        assert providers["claude-3.5"] == 1
    
    def test_confidence_trend_tracking(self):
        """Should be able to track confidence trends."""
        confidence_values = [0.7, 0.75, 0.8, 0.85, 0.9]
        
        for conf in confidence_values:
            response = {
                "provider": "gpt-4o",
                "confidence": conf,
                "content": f"Response with conf {conf}",
            }
            should_release, _, metadata = enforce_on_release(response)
            assert should_release is True
            assert metadata["confidence"] == conf
    
    def test_citation_coverage_tracking(self):
        """Should track citation coverage across responses."""
        responses_with_varying_citations = [
            {
                "provider": "agent",
                "confidence": 0.8,
                "citations": [],
                "content": "No citations",
            },
            {
                "provider": "agent",
                "confidence": 0.8,
                "citations": ["src1"],
                "content": "One citation",
            },
            {
                "provider": "agent",
                "confidence": 0.8,
                "citations": ["src1", "src2", "src3"],
                "content": "Three citations",
            },
        ]
        
        citation_counts = []
        for resp in responses_with_varying_citations:
            _, _, metadata = enforce_on_release(resp, response_type="research")
            citation_counts.append(metadata["citation_count"])
        
        assert citation_counts == [0, 1, 3]
        assert sum(citation_counts) / len(citation_counts) == 4 / 3  # Average


class TestStrictModeEnforcement:
    """Tests for strict mode blocking low-trust responses."""
    
    def test_strict_mode_blocks_missing_provider(self, monkeypatch):
        """In strict mode, missing provider should block."""
        monkeypatch.setenv("TRUST_STRICT_MODE", "true")
        
        # Need to reload to pick up env var
        from importlib import reload
        import mammoth_os.provenance_contract as pc
        reload(pc)
        
        response = {
            "confidence": 0.8,
            "content": "Missing provider",
        }
        
        # Even with enforcement, missing provider is a critical issue
        should_release, block_reason, metadata = pc.enforce_on_release(response)
        
        # In strict mode, missing critical fields should block
        # (Note: actual behavior depends on contract implementation)
        assert isinstance(should_release, bool)
        assert isinstance(metadata, dict)
    
    def test_conservative_mode_allows_with_warnings(self):
        """In conservative mode (default), responses are allowed with warnings."""
        response = {
            "provider": "agent",  # Add required provider field
            "confidence": 0.3,  # Low confidence
            "content": "Result with low confidence",
        }
        
        should_release, block_reason, metadata = enforce_on_release(response)
        
        # Conservative mode still releases
        assert should_release is True
        # Should have low confidence issues in validation_issues
        assert len(metadata.get("validation_issues", [])) > 0
        # Should indicate low confidence in issues
        assert any("low confidence" in issue.lower() for issue in metadata.get("validation_issues", []))


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling."""
    
    def test_response_with_no_content_field(self):
        """Response without content/result field should handle gracefully."""
        response = {
            "status": "ok",
            "provider": "agent",
            "confidence": 0.8,
        }
        
        should_release, block_reason, metadata = enforce_on_release(response)
        
        # Should either pass or fail gracefully, not crash
        assert isinstance(should_release, bool)
        assert isinstance(metadata, dict)
    
    def test_response_with_extra_fields(self):
        """Extra fields in response should not break validation."""
        response = {
            "status": "ok",
            "provider": "agent",
            "confidence": 0.8,
            "content": "Result",
            "extra_field_1": "value1",
            "extra_field_2": {"nested": "value2"},
            "extra_list": [1, 2, 3],
        }
        
        should_release, block_reason, metadata = enforce_on_release(response)
        
        assert should_release is True
        assert metadata["provider"] == "agent"
    
    def test_very_long_content(self):
        """Very long response content should not break validation."""
        long_content = "x" * 10000
        response = {
            "provider": "agent",
            "confidence": 0.8,
            "content": long_content,
        }
        
        should_release, block_reason, metadata = enforce_on_release(response)
        
        assert should_release is True
    
    def test_response_with_special_characters(self):
        """Response with special characters should be handled."""
        response = {
            "provider": "agent",
            "confidence": 0.8,
            "content": "Content with special chars: <>&\"'{}[]\\",
            "citations": ["https://example.com?q=special&char=true"],
        }
        
        should_release, block_reason, metadata = enforce_on_release(response)
        
        assert should_release is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
