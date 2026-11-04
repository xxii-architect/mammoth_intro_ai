"""Structural evidence guards, not authorization or factual verification."""

import re
from typing import Any, Dict, Optional

MAX_SAFE_INTEGER = 9_007_199_254_740_991


def validate_document_review(value: Any, *, review_id: Optional[str] = None,
                             file_id: Optional[str] = None, scope: Optional[str] = None) -> Dict[str, Any]:
    def require(condition: bool) -> None:
        if not condition:
            raise ValueError("Invalid saved document review; reload authoritative state before further work")

    def integer(number: Any, minimum: int = 0) -> bool:
        return type(number) is int and minimum <= number <= MAX_SAFE_INTEGER

    if not isinstance(value, dict):
        raise ValueError("Invalid saved document review")
    require(value.get("contract") == "mammoth.document-review.v1")
    require(isinstance(value.get("id"), str) and re.fullmatch(r"review-[a-f0-9]{24}", value["id"]) is not None)
    require(isinstance(value.get("file_id"), str) and bool(value["file_id"]))
    require(value.get("scope") in ("chat", "atlas"))
    require(review_id is None or value["id"] == review_id)
    require(file_id is None or value["file_id"] == file_id)
    require(scope is None or value["scope"] == scope)
    require(value.get("status") in ("ready", "partial", "active", "completed", "blocked"))
    for key in ("goal", "name", "stop_reason", "created_at", "updated_at"):
        require(isinstance(value.get(key), str))
    digest = value.get("source_sha256")
    require(isinstance(digest, str) and re.fullmatch(r"[a-f0-9]{64}", digest) is not None)
    require(integer(value.get("total_sections"), 1))
    total = value["total_sections"]
    require(type(value.get("review_complete")) is bool)
    require(integer(value.get("max_tokens")) and 64_000 <= value["max_tokens"] <= 128_000)
    require("max_extended_tokens" not in value or value["max_extended_tokens"] == 128_000
            and type(value["max_extended_tokens"]) is int)
    require(value.get("batch_sections") == 3 and type(value["batch_sections"]) is int)
    usage = value.get("usage")
    if not isinstance(usage, dict):
        raise ValueError("Invalid saved document review usage")
    require(integer(usage.get("tokens")) and isinstance(usage.get("accounting_status"), str))
    require(isinstance(value.get("warnings"), list) and all(isinstance(item, str) for item in value["warnings"]))
    require(value.get("coverage_basis") == "indexed_sections_not_original_file_or_factual_verification")
    assessments = value.get("assessments")
    if not isinstance(assessments, list):
        raise ValueError("Invalid saved document review assessments")
    require(len(assessments) <= total)
    for index, item in enumerate(assessments):
        require(isinstance(item, dict) and type(item.get("chunk_index")) is int and item["chunk_index"] == index)
        require(item.get("source_sha256") == digest)
        for key in ("location", "summary", "quote", "model", "reasoning_trace"):
            require(isinstance(item.get(key), str))
        require(bool(item["summary"].strip()) and 1 <= len(item["quote"]) <= 300)
        require(integer(item.get("reported_tokens"), 1))
        require(isinstance(item.get("quality"), dict) and item["quality"].get("fact_verification") == "not_performed")
    require(not value["review_complete"] or len(assessments) == total)
    require(value["status"] != "completed" or value["review_complete"])
    require(value["status"] != "ready" or not assessments and not value["review_complete"])
    marker = value.get("inflight_section")
    require(marker is None or marker == "synthesis" or integer(marker) and marker == len(assessments) and marker < total)
    require(marker is None or value["status"] in ("active", "blocked")
            or marker == "synthesis" and value["status"] == "completed")
    previous = 64_000
    retained = 0
    history = value.get("budget_extensions", [])
    require(isinstance(history, list))
    for extension in history:
        require(isinstance(extension, dict))
        require(type(extension.get("previous_max_tokens")) is int and extension["previous_max_tokens"] == previous)
        require(integer(extension.get("max_tokens")) and previous < extension["max_tokens"] <= 128_000)
        require(integer(extension.get("reported_tokens"))
                and retained <= extension["reported_tokens"] <= usage["tokens"]
                and extension["reported_tokens"] < extension["max_tokens"])
        require(isinstance(extension.get("confirmed_at"), str))
        previous, retained = extension["max_tokens"], extension["reported_tokens"]
    require(previous == value["max_tokens"])

    synthesis = value.get("synthesis")
    if synthesis is not None:
        require(value["review_complete"] and isinstance(synthesis, dict))
        require(synthesis.get("status") in ("active", "partial", "completed", "blocked"))
        require(isinstance(synthesis.get("stop_reason"), str))
        require(synthesis.get("basis") == "saved_assessments_not_full_source"
                and synthesis.get("fact_verification") == "not_performed")
        require(integer(synthesis.get("level")) and isinstance(synthesis.get("levels"), list)
                and synthesis["level"] == len(synthesis["levels"]))

        def nodes(items: Any, inputs: Any, leaf: bool, complete: bool) -> None:
            require(isinstance(items, list))
            require(len(items) <= (len(inputs) + 7) // 8)
            require(not complete or len(items) == (len(inputs) + 7) // 8)
            for index, node in enumerate(items):
                group = inputs[index * 8:(index + 1) * 8]
                expected = sorted({section for item in group for section in (
                    [item["chunk_index"]] if leaf else item["section_indices"])})
                allowed = set(expected) if leaf else {section for item in group for section in item["citations"]}
                require(isinstance(node, dict) and node.get("source_sha256") == digest)
                require(isinstance(node.get("section_indices"), list)
                        and all(integer(section) for section in node["section_indices"])
                        and node["section_indices"] == expected)
                citations = node.get("citations")
                require(isinstance(citations, list) and bool(citations)
                        and all(integer(section) and section in allowed for section in citations)
                        and citations == sorted(set(citations)))
                require(isinstance(node.get("summary"), str) and bool(node["summary"].strip()))
                require(isinstance(node.get("model"), str) and isinstance(node.get("reasoning_trace"), str))
                require(integer(node.get("reported_tokens"), 1))
                require(isinstance(node.get("quality"), dict) and node["quality"].get("fact_verification") == "not_performed")

        inputs = assessments
        for level, items in enumerate(synthesis["levels"]):
            nodes(items, inputs, level == 0, True)
            require(len(items) > 1)
            inputs = items
        nodes(synthesis.get("nodes"), inputs, synthesis["level"] == 0, False)
        result = synthesis.get("result")
        if result is not None:
            require(isinstance(result, dict) and len(synthesis["nodes"]) == 1)
            nodes([result], inputs, synthesis["level"] == 0, False)
            for key in ("summary", "citations", "section_indices", "source_sha256", "model",
                        "reported_tokens", "reasoning_trace"):
                require(result.get(key) == synthesis["nodes"][0][key])
            require(len(result["section_indices"]) == total
                    and all(index == section for index, section in enumerate(result["section_indices"])))
        require(synthesis["status"] != "completed" or result is not None)
    require(marker != "synthesis" or synthesis is not None)
    return value
