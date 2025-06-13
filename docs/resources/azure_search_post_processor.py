import json
from typing import Any, Dict

def _as_json(value: Any) -> str:
    """Safe JSON serialiser for arbitrary objects."""
    try:
        return json.dumps(value, default=str, ensure_ascii=False)
    except Exception:                                    # pragma: no cover
        return str(value)

def _get_request(arguments: Dict) -> Any:
    """Return the SearchRequest object (if present)."""
    return arguments.get("kwargs", {}).get("search_request")

def _get_result(arguments: Dict):
    """Return the SearchDocumentsResult object (if present)."""
    return arguments.get("result")

def capture_input(arguments: Dict) -> str:
    req = _get_request(arguments)
    return str(getattr(req, "search_text", ""))          # a simple string

def capture_output(arguments: Dict) -> str:
    res = _get_result(arguments)
    if not res or not getattr(res, "results", None):
        return "[]"                                      # no results yet
    filtered = []
    for item in res.results:                             # type: ignore[attr-defined]
        doc = item.additional_properties or {}
        filtered.append(
            {
                "docTitle": doc.get("docTitle"),
                "description": doc.get("description"),
                "@search.score":  item.score,
                "@search.reranker_score": item.reranker_score,
            }
        )
    return _as_json(filtered)                            # JSON string

def capture_meta(arguments: Dict) -> str:
    req = _get_request(arguments)
    if not req:
        return "{}"
    wanted = [
        "select", "include_total_result_count", "facets", "filter",
        "highlight_fields", "highlight_post_tag", "highlight_pre_tag",
        "minimum_coverage", "order_by", "query_type", "scoring_parameters",
        "scoring_profile", "semantic_query",
    ]
    meta = {k: getattr(req, k, None) for k in wanted}
    meta["latency_ms"] = arguments.get("latency_ms")
    return _as_json(meta)

SEARCH_POST_PROCESSOR = {
    "type": "search",
    "events": [
        {
            "name": "data.input",
            "attributes": [
                { "attribute": "search_text", "accessor": capture_input }
            ]
        },
        {
            "name": "data.output",
            "attributes": [
                { "attribute": "results", "accessor": capture_output }
            ]
        },
        {
            "name": "metadata",
            "attributes": [
                { "attribute": "options", "accessor": capture_meta }
            ]
        }
    ]
}