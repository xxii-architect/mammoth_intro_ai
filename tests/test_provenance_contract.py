"""
Tests for server-side provenance contract enforcement.
"""

import os
import pytest
from mammoth_os.provenance_contract import (
    ProvenanceContract,
    validate_response,
    enforce_on_release,
    add_trust_metadata,
    get_contract,
)


class TestProvenanceContractBasics:
    """Basic validation tests."""
    
    def test_valid_response_passes(self):
        """A properly structured response should pass validation."""
        response = {
            "provider": "gpt-4o",
            "confidence": 0.85,
            "citations": ["source1", "source2"],
            "contradictions": [],
            "content": "The answer is 42",
        }
        is_valid, issues = validate_response(response)
        assert is_valid
        assert len([i for i in issues if "must" in i or "missing" in i]) == 0
    
    def test_missing_provider_warning(self):
        """Missing provider should trigger warning in non-strict mode."""
        response = {
            "confidence": 0.85,
            "citations": [],
            "content": "Response without provider",
        }
        is_valid, issues = validate_response(response)
        # Non-strict mode allows but warns
        assert any("provider" in i.lower() for i in issues)
    
    def test_missing_confidence_warning(self):
        """Missing confidence should trigger warning."""
        response = {
            "provider": "gpt-4o",
            "content": "Response without confidence",
        }
        is_valid, issues = validate_response(response)
        assert any("confidence" in i.lower() for i in issues)
    
    def test_confidence_out_of_range(self):
        """Confidence outside 0.0-1.0 should fail."""
        response = {
            "provider": "gpt-4o",
            "confidence": 1.5,  # Invalid
            "content": "Invalid confidence",
        }
        is_valid, issues = validate_response(response)
        assert any("out of range" in i.lower() for i in issues)
    
    def test_low_confidence_flagged(self):
        """Confidence below threshold should be flagged."""
        response = {
            "provider": "gpt-4o",
            "confidence": 0.3,  # Below default 0.5
            "content": "Low confidence response",
        }
        is_valid, issues = validate_response(response)
        # Low confidence is a warning, not a hard fail in non-strict mode
        assert any("low confidence" in i.lower() for i in issues)


class TestResearchResponseValidation:
    """Tests for research-specific validation."""
    
    def test_research_without_citations_fails(self):
        """Research output without citations should warn."""
        response = {
            "provider": "research-agent",
            "confidence": 0.9,
            "content": "Research finding without citations",
        }
        is_valid, issues = validate_response(response, response_type="research")
        assert any("citations" in i.lower() for i in issues)
    
    def test_research_with_insufficient_citations_warns(self):
        """Research with fewer than 2 citations should warn."""
        response = {
            "provider": "research-agent",
            "confidence": 0.9,
            "citations": ["only-one-source"],
            "content": "Research with single citation",
        }
        is_valid, issues = validate_response(response, response_type="research")
        assert any("insufficient" in i.lower() for i in issues)
    
    def test_research_with_sufficient_citations_passes(self):
        """Research with 2+ citations should pass."""
        response = {
            "provider": "research-agent",
            "confidence": 0.9,
            "citations": ["source1", "source2", "source3"],
            "contradictions": [],
            "content": "Well-sourced research",
        }
        is_valid, issues = validate_response(response, response_type="research")
        # Should have no citation-related issues
        assert not any("insufficient" in i.lower() and "citation" in i.lower() for i in issues)
    
    def test_research_missing_contradictions_noted(self):
        """Research should ideally include contradiction field."""
        response = {
            "provider": "research-agent",
            "confidence": 0.9,
            "citations": ["source1", "source2"],
            "content": "Research without contradictions field",
        }
        is_valid, issues = validate_response(response, response_type="research")
        # Missing contradictions field is noted but doesn't block in non-strict
        assert any("contradictions" in i.lower() for i in issues)


class TestTrustMetadata:
    """Tests for trust metadata handling."""
    
    def test_enforce_on_release_allows_valid_response(self):
        """Valid response should be released."""
        response = {
            "provider": "gpt-4o",
            "confidence": 0.85,
            "citations": [],
            "content": "Valid response",
        }
        should_release, block_reason, metadata = enforce_on_release(response)
        assert should_release is True
        assert block_reason is None
        assert metadata["validation_passed"] is True
    
    def test_enforce_on_release_metadata_includes_fields(self):
        """Enforcement should return complete metadata."""
        response = {
            "provider": "gpt-4o",
            "confidence": 0.85,
            "citations": ["s1", "s2"],
            "contradictions": ["caveat1"],
            "content": "Response with metadata",
        }
        should_release, block_reason, metadata = enforce_on_release(response)
        assert "validated_at" in metadata
        assert "response_type" in metadata
        assert "validation_issues" in metadata
        assert "provider" in metadata
        assert metadata["confidence"] == 0.85
        assert metadata["citation_count"] == 2
        assert metadata["has_contradictions"] is True
    
    def test_low_confidence_adds_warning_flag(self):
        """Low confidence should add trust_warning flag."""
        response = {
            "provider": "gpt-4o",
            "confidence": 0.2,
            "content": "Low confidence",
        }
        should_release, block_reason, metadata = enforce_on_release(response)
        # In non-strict mode, still released but marked
        assert should_release is True
        assert metadata.get("trust_warning") is True


class TestContradicationHandling:
    """Tests for contradiction flagging."""
    
    def test_high_confidence_with_contradictions_flagged(self):
        """High confidence with contradictions should be flagged."""
        response = {
            "provider": "gpt-4o",
            "confidence": 0.95,  # Very high
            "contradictions": ["Some internal conflict noted"],
            "content": "Confident response with contradictions",
        }
        is_valid, issues = validate_response(response, response_type="research")
        assert any("contradiction" in i.lower() and "confidence" in i.lower() for i in issues)
    
    def test_contradictions_list_tracked(self):
        """Contradictions should be properly tracked."""
        response = {
            "provider": "gpt-4o",
            "confidence": 0.7,
            "contradictions": ["Caveat 1", "Caveat 2"],
            "content": "Response with tracked contradictions",
        }
        should_release, block_reason, metadata = enforce_on_release(response)
        assert metadata["has_contradictions"] is True


class TestAddTrustMetadata:
    """Tests for adding trust metadata to responses."""
    
    def test_add_trust_metadata_fills_defaults(self):
        """add_trust_metadata should add missing fields with defaults."""
        response = {
            "content": "Bare response",
        }
        enhanced = add_trust_metadata(response)
        assert enhanced["provider"] == "unknown"
        assert enhanced["confidence"] == 0.5
        assert enhanced["citations"] == []
        assert enhanced["contradictions"] == []
        assert enhanced["citation_count"] == 0
        assert enhanced["has_contradictions"] is False
    
    def test_add_trust_metadata_preserves_existing(self):
        """add_trust_metadata should preserve existing values."""
        response = {
            "provider": "custom-agent",
            "confidence": 0.8,
            "citations": ["s1", "s2"],
            "content": "Already enhanced",
        }
        enhanced = add_trust_metadata(response)
        assert enhanced["provider"] == "custom-agent"
        assert enhanced["confidence"] == 0.8
        assert enhanced["citations"] == ["s1", "s2"]
        assert enhanced["citation_count"] == 2
    
    def test_evidence_breadth_calculation(self):
        """Evidence breadth should reflect citation count."""
        response_few = {
            "provider": "gpt-4o",
            "citations": ["only-one"],
            "content": "Few sources",
        }
        enhanced_few = add_trust_metadata(response_few)
        assert enhanced_few["evidence_breadth"] == "limited"
        
        response_many = {
            "provider": "gpt-4o",
            "citations": ["s1", "s2", "s3"],
            "content": "Many sources",
        }
        enhanced_many = add_trust_metadata(response_many)
        assert enhanced_many["evidence_breadth"] == "moderate"


class TestStrictMode:
    """Tests for strict mode enforcement."""
    
    def test_strict_mode_blocks_missing_fields(self):
        """In strict mode, missing required fields should fail."""
        response = {
            "content": "Missing provider and confidence",
        }
        is_valid, issues = validate_response(response, strict=True)
        assert is_valid is False
        assert len(issues) > 0
    
    def test_non_strict_mode_allows_warnings(self):
        """In non-strict mode, warnings don't block release."""
        response = {
            "content": "Missing provider and confidence",
        }
        is_valid, issues = validate_response(response, strict=False)
        # May have issues but is_valid is based on critical ones
        assert any("provider" in i.lower() or "confidence" in i.lower() for i in issues)


class TestResponseTypes:
    """Tests for different response type handling."""
    
    def test_tutor_response_should_cite(self):
        """Tutor responses should ideally include citations."""
        response = {
            "provider": "tutor-agent",
            "confidence": 0.9,
            "content": "Here's how to solve this...",
        }
        is_valid, issues = validate_response(response, response_type="tutor")
        assert any("citations" in i.lower() for i in issues)
    
    def test_general_response_allows_no_citations(self):
        """General responses don't require citations."""
        response = {
            "provider": "gpt-4o",
            "confidence": 0.7,
            "content": "Hello world",
        }
        is_valid, issues = validate_response(response, response_type="general")
        # General type shouldn't warn about missing citations
        citation_issues = [i for i in issues if "citation" in i.lower()]
        assert len(citation_issues) == 0


class TestContract:
    """Tests for ProvenanceContract class directly."""
    
    def test_get_contract_returns_singleton(self):
        """get_contract should return the global instance."""
        contract = get_contract()
        assert isinstance(contract, ProvenanceContract)
    
    def test_contract_uses_env_thresholds(self, monkeypatch):
        """ProvenanceContract should read thresholds from environment."""
        monkeypatch.setenv("TRUST_MIN_CONFIDENCE", "0.7")
        monkeypatch.setenv("TRUST_MIN_CITATIONS_RESEARCH", "3")
        
        contract = ProvenanceContract()
        assert contract.min_confidence_threshold == 0.7
        assert contract.min_citation_count_for_research == 3
    
    def test_contract_strict_mode_from_env(self, monkeypatch):
        """ProvenanceContract should read strict_mode from environment."""
        monkeypatch.setenv("TRUST_STRICT_MODE", "true")
        
        contract = ProvenanceContract()
        assert contract.strict_mode is True
    
    def test_custom_confidence_threshold(self, monkeypatch):
        """Custom confidence threshold should affect validation."""
        monkeypatch.setenv("TRUST_MIN_CONFIDENCE", "0.8")
        
        contract = ProvenanceContract()
        response = {
            "provider": "gpt-4o",
            "confidence": 0.7,  # Between default 0.5 and custom 0.8
            "content": "Medium confidence",
        }
        
        is_valid, issues = contract.validate_response(response)
        # With threshold at 0.8, 0.7 should be flagged
        assert any("low confidence" in i.lower() for i in issues)


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_empty_response_dict(self):
        """Empty response should trigger multiple warnings."""
        response = {}
        is_valid, issues = validate_response(response)
        assert len(issues) > 0
        assert any("provider" in i.lower() for i in issues)
    
    def test_none_response_fields(self):
        """None values should be handled gracefully."""
        response = {
            "provider": None,
            "confidence": None,
            "content": "Response with None fields",
        }
        is_valid, issues = validate_response(response)
        # Should handle None without crashing
        assert len(issues) > 0
    
    def test_string_confidence_coerced(self):
        """String confidence should be coerced to float."""
        response = {
            "provider": "gpt-4o",
            "confidence": "0.85",  # String
            "content": "String confidence",
        }
        is_valid, issues = validate_response(response)
        # Should not crash; might flag as non-numeric
        assert not any("crash" in i.lower() for i in issues)
    
    def test_citations_with_urls(self):
        """Citations can be URL strings."""
        response = {
            "provider": "research-agent",
            "confidence": 0.9,
            "citations": [
                "https://example.com/paper1",
                "https://example.com/paper2",
                {"title": "Paper 3", "url": "https://example.com/paper3"}
            ],
            "content": "Research with mixed citation formats",
        }
        is_valid, issues = validate_response(response, response_type="research")
        # Should accept mixed citation formats
        assert not any("citations" in i.lower() and "insufficient" in i.lower() for i in issues)
    
    def test_large_contradiction_list(self):
        """Large contradiction lists should be handled."""
        response = {
            "provider": "analysis-agent",
            "confidence": 0.6,
            "contradictions": [f"Contradiction {i}" for i in range(100)],
            "content": "Response with many contradictions",
        }
        is_valid, issues = validate_response(response, response_type="research")
        # Should handle without crashing
        should_release, block_reason, metadata = enforce_on_release(response)
        assert metadata is not None
        assert metadata["has_contradictions"] is True


class TestIntegrationWithResponses:
    """Integration tests simulating real API responses."""
    
    def test_atlas_submit_response_structure(self):
        """Validate a realistic atlas/submit response."""
        response = {
            "status": "ok",
            "provider": "tutor-atlas",
            "confidence": 0.85,
            "citations": ["Exercise library", "Curriculum standards"],
            "result": {"passed": True, "score": 95},
            "adaptive_feedback": {"next_lesson": "lessons/advanced/001"},
        }
        should_release, block_reason, metadata = enforce_on_release(
            response,
            response_type="tutor"
        )
        assert should_release is True
        assert metadata["citation_count"] == 2
    
    def test_research_agent_response_structure(self):
        """Validate a realistic research agent response."""
        response = {
            "status": "ok",
            "provider": "research-agent",
            "confidence": 0.92,
            "citations": [
                "arxiv.org/abs/2024.00001",
                "scholar.google.com/citation/xyz",
                "github.com/repository/docs",
            ],
            "contradictions": ["Different definitions in field"],
            "content": "Research finding goes here",
            "evidence_breadth": "broad",
        }
        should_release, block_reason, metadata = enforce_on_release(
            response,
            response_type="research"
        )
        assert should_release is True
        assert metadata["citation_count"] == 3
        assert metadata["has_contradictions"] is True
    
    def test_coding_agent_minimal_response(self):
        """Coding agent responses can be minimal on provenance."""
        response = {
            "status": "ok",
            "provider": "coding-agent",
            "confidence": 0.88,
            "result": {"code": "def hello(): return 'world'"},
        }
        should_release, block_reason, metadata = enforce_on_release(
            response,
            response_type="coding"
        )
        assert should_release is True
        assert metadata["provider"] == "coding-agent"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
