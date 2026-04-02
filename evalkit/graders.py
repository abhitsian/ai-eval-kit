"""Generic code-based graders — reusable assertions for any AI product.

These graders check structural properties of responses. Product-specific
graders can be added by registering custom functions.
"""

import re
from typing import Any, Callable, Dict

from evalkit.models import GraderResult, GraderType, Verdict


def grade(check_name: str, response: Dict[str, Any], expected: Dict[str, Any]) -> GraderResult:
    """Dispatch to the appropriate code-based grader."""
    grader_fn = GRADERS.get(check_name)
    if not grader_fn:
        return GraderResult(
            grader_type=GraderType.CODE,
            dimension=check_name,
            verdict=Verdict.UNKNOWN,
            reasoning=f"No grader registered for: {check_name}. Register with register_grader().",
        )
    return grader_fn(response, expected)


def register_grader(name: str, fn: Callable):
    """Register a custom grader function."""
    GRADERS[name] = fn


# ============================================================
# Generic Graders — usable by any product
# ============================================================

def exact_match(response: Dict, expected: Dict) -> GraderResult:
    """Response field matches expected value exactly."""
    field = expected.get("field", "text")
    expected_val = expected.get("value", "")
    actual = response.get(field, "")
    passed = str(actual).strip() == str(expected_val).strip()
    return GraderResult(
        grader_type=GraderType.CODE, dimension="exact_match",
        verdict=Verdict.PASS if passed else Verdict.FAIL,
        reasoning=f"Field '{field}': expected '{expected_val}', got '{actual}'",
    )


def contains_keywords(response: Dict, expected: Dict) -> GraderResult:
    """Response text contains all specified keywords."""
    text = str(response.get("text", "")).lower()
    keywords = [k.lower() for k in expected.get("contains_keywords", [])]
    missing = [k for k in keywords if k not in text]
    passed = len(missing) == 0
    return GraderResult(
        grader_type=GraderType.CODE, dimension="contains_keywords",
        verdict=Verdict.PASS if passed else Verdict.FAIL,
        reasoning=f"Missing keywords: {missing}" if missing else "All keywords found",
    )


def excludes_keywords(response: Dict, expected: Dict) -> GraderResult:
    """Response text does NOT contain any of the specified keywords."""
    text = str(response.get("text", "")).lower()
    banned = [k.lower() for k in expected.get("excludes_keywords", [])]
    found = [k for k in banned if k in text]
    passed = len(found) == 0
    return GraderResult(
        grader_type=GraderType.CODE, dimension="excludes_keywords",
        verdict=Verdict.PASS if passed else Verdict.FAIL,
        reasoning=f"Found banned keywords: {found}" if found else "No banned keywords found",
    )


def routes_to(response: Dict, expected: Dict) -> GraderResult:
    """Response was routed to the expected surface/intent."""
    expected_route = expected.get("routes_to", "").lower()
    actual = response.get("intent", response.get("routes_to", response.get("surface", ""))).lower()
    passed = actual == expected_route
    return GraderResult(
        grader_type=GraderType.CODE, dimension="routes_to",
        verdict=Verdict.PASS if passed else Verdict.FAIL,
        reasoning=f"Expected route '{expected_route}', got '{actual}'",
    )


def has_citations(response: Dict, expected: Dict) -> GraderResult:
    """Response includes source citations."""
    citations = response.get("citations", response.get("sources", []))
    passed = len(citations) > 0
    return GraderResult(
        grader_type=GraderType.CODE, dimension="has_citations",
        verdict=Verdict.PASS if passed else Verdict.FAIL,
        reasoning=f"Citations found: {len(citations)}",
    )


def no_citations(response: Dict, expected: Dict) -> GraderResult:
    """Response should NOT cite sources (negative test)."""
    citations = response.get("citations", response.get("sources", []))
    passed = len(citations) == 0
    return GraderResult(
        grader_type=GraderType.CODE, dimension="no_citations",
        verdict=Verdict.PASS if passed else Verdict.FAIL,
        reasoning=f"Expected no citations, found {len(citations)}",
    )


def response_is_list(response: Dict, expected: Dict) -> GraderResult:
    """Response data is a list with multiple items."""
    data = response.get("data", response.get("results", []))
    passed = isinstance(data, list) and len(data) > 0
    return GraderResult(
        grader_type=GraderType.CODE, dimension="response_is_list",
        verdict=Verdict.PASS if passed else Verdict.FAIL,
        reasoning=f"Data is list with {len(data) if isinstance(data, list) else 0} items",
    )


def response_is_single(response: Dict, expected: Dict) -> GraderResult:
    """Response data is a single item (not a list, or list of 1)."""
    data = response.get("data", response.get("results", None))
    if isinstance(data, list):
        passed = len(data) == 1
    elif isinstance(data, dict):
        passed = True
    else:
        passed = False
    return GraderResult(
        grader_type=GraderType.CODE, dimension="response_is_single",
        verdict=Verdict.PASS if passed else Verdict.FAIL,
        reasoning="Single item response" if passed else "Expected single item",
    )


def has_actions(response: Dict, expected: Dict) -> GraderResult:
    """Response includes actionable buttons/options."""
    actions = response.get("actions", response.get("buttons", response.get("options", [])))
    passed = len(actions) > 0
    return GraderResult(
        grader_type=GraderType.CODE, dimension="has_actions",
        verdict=Verdict.PASS if passed else Verdict.FAIL,
        reasoning=f"Actions: {actions}" if actions else "No actions found",
    )


def field_equals(response: Dict, expected: Dict) -> GraderResult:
    """A specific response field equals the expected value."""
    field = expected.get("check_field", "")
    expected_val = expected.get("check_value", "")
    actual = response.get(field, None)
    passed = str(actual).lower() == str(expected_val).lower()
    return GraderResult(
        grader_type=GraderType.CODE, dimension=f"field_{field}_equals",
        verdict=Verdict.PASS if passed else Verdict.FAIL,
        reasoning=f"Field '{field}': expected '{expected_val}', got '{actual}'",
    )


def response_length_between(response: Dict, expected: Dict) -> GraderResult:
    """Response text length is within expected range."""
    text = str(response.get("text", ""))
    min_len = expected.get("min_length", 0)
    max_len = expected.get("max_length", 10000)
    passed = min_len <= len(text) <= max_len
    return GraderResult(
        grader_type=GraderType.CODE, dimension="response_length",
        verdict=Verdict.PASS if passed else Verdict.FAIL,
        reasoning=f"Length {len(text)}, expected {min_len}-{max_len}",
    )


def regex_match(response: Dict, expected: Dict) -> GraderResult:
    """Response text matches a regex pattern."""
    text = str(response.get("text", ""))
    pattern = expected.get("regex_pattern", "")
    passed = bool(re.search(pattern, text, re.IGNORECASE))
    return GraderResult(
        grader_type=GraderType.CODE, dimension="regex_match",
        verdict=Verdict.PASS if passed else Verdict.FAIL,
        reasoning=f"Pattern '{pattern}' {'matched' if passed else 'not found'}",
    )


def no_pii_leaked(response: Dict, expected: Dict) -> GraderResult:
    """Response does not contain common PII patterns."""
    text = str(response.get("text", ""))
    pii_patterns = [
        (r"\b\d{3}-\d{2}-\d{4}\b", "SSN"),
        (r"\b\d{16}\b", "credit card"),
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "email"),
    ]
    # Only flag emails if expected says to check for them
    check_email = expected.get("check_email_pii", False)
    found = []
    for pattern, label in pii_patterns:
        if label == "email" and not check_email:
            continue
        if re.search(pattern, text):
            found.append(label)
    passed = len(found) == 0
    return GraderResult(
        grader_type=GraderType.CODE, dimension="no_pii_leaked",
        verdict=Verdict.PASS if passed else Verdict.FAIL,
        reasoning=f"PII detected: {found}" if found else "No PII found",
    )


def latency_under(response: Dict, expected: Dict) -> GraderResult:
    """Response latency is under threshold."""
    latency = response.get("latency_ms", 0)
    max_ms = expected.get("max_latency_ms", 5000)
    passed = latency <= max_ms
    return GraderResult(
        grader_type=GraderType.CODE, dimension="latency_under",
        verdict=Verdict.PASS if passed else Verdict.FAIL,
        reasoning=f"Latency {latency}ms, max {max_ms}ms",
    )


def tool_called(response: Dict, expected: Dict) -> GraderResult:
    """The expected tool/function was called."""
    tools_used = response.get("tools_called", response.get("tool_calls", []))
    expected_tool = expected.get("expected_tool", "")
    tool_names = [t.get("name", t) if isinstance(t, dict) else str(t) for t in tools_used]
    passed = expected_tool in tool_names
    return GraderResult(
        grader_type=GraderType.CODE, dimension="tool_called",
        verdict=Verdict.PASS if passed else Verdict.FAIL,
        reasoning=f"Expected tool '{expected_tool}', called: {tool_names}",
    )


def tool_not_called(response: Dict, expected: Dict) -> GraderResult:
    """A specific tool should NOT have been called."""
    tools_used = response.get("tools_called", response.get("tool_calls", []))
    banned_tool = expected.get("banned_tool", "")
    tool_names = [t.get("name", t) if isinstance(t, dict) else str(t) for t in tools_used]
    passed = banned_tool not in tool_names
    return GraderResult(
        grader_type=GraderType.CODE, dimension="tool_not_called",
        verdict=Verdict.PASS if passed else Verdict.FAIL,
        reasoning=f"Banned tool '{banned_tool}' {'not called' if passed else 'WAS called'}",
    )


# ============================================================
# Grader Registry
# ============================================================

GRADERS: Dict[str, Callable] = {
    "exact_match": exact_match,
    "contains_keywords": contains_keywords,
    "excludes_keywords": excludes_keywords,
    "routes_to": routes_to,
    "has_citations": has_citations,
    "no_citations": no_citations,
    "response_is_list": response_is_list,
    "response_is_single": response_is_single,
    "has_actions": has_actions,
    "field_equals": field_equals,
    "response_length_between": response_length_between,
    "regex_match": regex_match,
    "no_pii_leaked": no_pii_leaked,
    "latency_under": latency_under,
    "tool_called": tool_called,
    "tool_not_called": tool_not_called,
}
