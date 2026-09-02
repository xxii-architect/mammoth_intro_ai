"""
Server-side provenance contract enforcement for MammothOS.

Validates response contracts before shipping to clients to prevent "trust-blind" outputs.
Ensures every response includes provider, confidence, citations, and contradiction metadata.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class ProvenanceContract:
    """
    Defines and validates the provenance contract for agent/tutor/research outputs.
    
    Required fields:
    - provider: Which LLM/service provided the content
    - confidence: Float 0.0-1.0 indicating certainty level
    - citations: List of sources/evidence supporting the claim
    - contradictions: Any internal contradictions or caveats
    """
    
    def __init__(self):
        """Initialize with default thresholds from environment or defaults."""
        self.min_confidence_threshold = float(
            os.environ.get("TRUST_MIN_CONFIDENCE", "0.5")
        )
        self.min_citation_count_for_research = int(
            os.environ.get("TRUST_MIN_CITATIONS_RESEARCH", "2")
        )
        self.strict_mode = os.environ.get("TRUST_STRICT_MODE", "").lower() in {"1", "true", "yes"}
        self.log_all_validations = os.environ.get("TRUST_LOG_ALL", "").lower() in {"1", "true", "yes"}
        
    def validate_response(
        self,
        response: Dict[str, Any],
        strict: bool = False,
        response_type: str = "general"
    ) -> Tuple[bool, List[str]]:
        """
        Validate a response against the provenance contract.
        
        Args:
            response: The response object to validate
            strict: If True, fail on any missing field; if False, warn only
            response_type: Type of response ("general", "research", "tutor", "coding")
            
        Returns:
            Tuple of (is_valid, list_of_issues)
            - is_valid: True if response passes validation
            - list_of_issues: List of validation issues (warnings if not strict)
        """
        issues = []
        strict_mode = strict or self.strict_mode
        
        # Check for required provenance fields
        if "provider" not in response:
            msg = "Response missing 'provider' field (which LLM/service generated this)"
            issues.append(msg)
            if strict_mode:
                return False, issues
        
        if "confidence" not in response:
            msg = "Response missing 'confidence' field (0.0-1.0 certainty)"
            issues.append(msg)
            if strict_mode:
                return False, issues
        else:
            confidence = response.get("confidence")
            try:
                conf_float = float(confidence)
                if not (0.0 <= conf_float <= 1.0):
                    issues.append(f"Confidence out of range: {confidence} (must be 0.0-1.0)")
                elif conf_float < self.min_confidence_threshold:
                    issues.append(
                        f"Low confidence: {conf_float} below threshold {self.min_confidence_threshold}"
                    )
            except (TypeError, ValueError):
                issues.append(f"Confidence not numeric: {confidence}")
        
        # Research outputs require citations
        if response_type == "research":
            citations = response.get("citations", [])
            if not citations:
                issues.append("Research output missing 'citations' field")
            elif len(citations) < self.min_citation_count_for_research:
                issues.append(
                    f"Insufficient citations: {len(citations)} < {self.min_citation_count_for_research} "
                    f"required for research outputs"
                )
        elif "citations" not in response and response_type in {"tutor", "research"}:
            # Tutors and research should cite sources
            issues.append(f"Response type '{response_type}' should include 'citations'")
        
        # Check for contradiction metadata
        if "contradictions" not in response:
            if response_type in {"research", "analysis"}:
                issues.append(
                    "Response missing 'contradictions' field "
                    "(should list any internal contradictions or caveats)"
                )
        else:
            contradictions = response.get("contradictions")
            if isinstance(contradictions, list) and contradictions:
                # Presence of contradictions may reduce confidence
                if "confidence" in response:
                    try:
                        conf = float(response["confidence"])
                        if conf > 0.8:
                            issues.append(
                                f"High confidence ({conf}) claimed but contradictions present; "
                                f"consider lowering confidence"
                            )
                    except (TypeError, ValueError):
                        pass
        
        # Optional fields that improve trust
        if "citation_count" not in response and "citations" in response:
            # Not a hard fail, but good practice
            if response_type == "research":
                issues.append("Consider adding 'citation_count' for easy tracking")
        
        if "evidence_breadth" not in response and response_type == "research":
            issues.append("Consider adding 'evidence_breadth' field for research outputs")
        
        # Check for content field
        if "content" not in response and "result" not in response and "response" not in response:
            issues.append("Response missing content field ('content', 'result', or 'response')")
            if strict_mode:
                return False, issues
        
        # If we have issues in strict mode, return early
        if strict_mode and issues:
            return False, issues
        
        # In non-strict mode, return True with warnings
        return len([i for i in issues if "must be" in i or "missing" in i and strict_mode]) == 0, issues

    def enforce_on_release(
        self,
        response: Dict[str, Any],
        response_type: str = "general"
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Enforce contract before releasing response to client.
        
        In conservative mode: allows response but marks warnings
        In strict mode: blocks response if trust metrics fall below threshold
        
        Args:
            response: The response to validate
            response_type: Type of response ("general", "research", "tutor", "coding")
            
        Returns:
            Tuple of:
            - should_release: Whether to release this response
            - block_reason: If blocked, why (None if allowed)
            - trust_metadata: Metadata to attach to response
        """
        is_valid, issues = self.validate_response(
            response,
            strict=self.strict_mode,
            response_type=response_type
        )
        
        trust_metadata = {
            "validated_at": datetime.now(timezone.utc).isoformat(),
            "response_type": response_type,
            "validation_issues": issues,
            "validation_passed": is_valid,
            "provider": response.get("provider", "unknown"),
            "confidence": response.get("confidence", 0.0),
            "citation_count": len(response.get("citations", [])),
            "has_contradictions": bool(response.get("contradictions")),
        }
        
        # Conservative mode (default): warn but allow
        if not self.strict_mode:
            if issues:
                trust_metadata["trust_warning"] = True
                trust_metadata["warning_reason"] = "; ".join(issues[:3])  # Top 3 issues
            return True, None, trust_metadata
        
        # Strict mode: block on low confidence or missing required fields
        critical_issues = [
            i for i in issues
            if any(x in i for x in ["must be", "missing", "required", "block"])
        ]
        
        if critical_issues:
            reason = "; ".join(critical_issues[:2])
            return False, reason, trust_metadata
        
        return True, None, trust_metadata

    def add_trust_metadata(
        self,
        response: Dict[str, Any],
        response_type: str = "general"
    ) -> Dict[str, Any]:
        """
        Add trust metadata to a response object for client rendering.
        
        Args:
            response: Response to enrich
            response_type: Type of response
            
        Returns:
            Enhanced response with trust fields
        """
        enhanced = dict(response)
        
        # Ensure minimal trust fields exist
        if "provider" not in enhanced:
            enhanced["provider"] = "unknown"
        
        if "confidence" not in enhanced:
            enhanced["confidence"] = 0.5
        
        if "citations" not in enhanced:
            enhanced["citations"] = []
        
        if "contradictions" not in enhanced:
            enhanced["contradictions"] = []
        
        # Add convenience fields
        enhanced["citation_count"] = len(enhanced.get("citations", []))
        enhanced["has_contradictions"] = bool(enhanced.get("contradictions"))
        enhanced["evidence_breadth"] = enhanced.get(
            "evidence_breadth",
            "limited" if enhanced["citation_count"] < 2 else "moderate"
        )
        
        return enhanced


# Global contract instance
_contract = ProvenanceContract()


def validate_response(
    response: Dict[str, Any],
    strict: bool = False,
    response_type: str = "general"
) -> Tuple[bool, List[str]]:
    """Validate a response against the provenance contract."""
    return _contract.validate_response(response, strict=strict, response_type=response_type)


def enforce_on_release(
    response: Dict[str, Any],
    response_type: str = "general"
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Enforce contract before releasing response."""
    return _contract.enforce_on_release(response, response_type=response_type)


def add_trust_metadata(
    response: Dict[str, Any],
    response_type: str = "general"
) -> Dict[str, Any]:
    """Add trust metadata to response for client rendering."""
    return _contract.add_trust_metadata(response, response_type=response_type)


def get_contract() -> ProvenanceContract:
    """Get the global contract instance."""
    return _contract
