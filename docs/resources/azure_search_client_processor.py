import json
import traceback
from typing import Any, Dict

def _json(value: Any) -> str:
    """Return a JSON-safe string for any object."""
    try:
        return json.dumps(value, default=str, ensure_ascii=False)
    except Exception:                        
        return str(value)

def capture_search_input(arguments: Dict) -> str:
    """Return all search() kwargs as a JSON string."""
    kwargs = arguments.get("kwargs", {})
    print(f"[capture_search_input] started")
    
    try:
        import copy
        kwargs_copy = copy.deepcopy(kwargs)
        
        # This code is to remove the `vector` array from vector_queries to avoid logging large data
        if "vector_queries" in kwargs_copy and kwargs_copy["vector_queries"]:
            print(f"[capture_search_input] Processing vector_queries")
            processed_queries = []
            for i, query in enumerate(kwargs_copy["vector_queries"]):
                print(f"[capture_search_input] Processing vector query {i}: type={type(query)}")
                
                if isinstance(query, dict):
                    if 'vector' in query:
                        print(f"[capture_search_input] Removing vector array from dict query {i}")
                        del query['vector']
                    processed_queries.append(query)
                elif isinstance(query, str):
                    try:
                        query_dict = json.loads(query.replace("'", '"'))
                        if 'vector' in query_dict:
                            print(f"[capture_search_input] Removing vector array from string query {i}")
                            del query_dict['vector']
                        processed_queries.append(query_dict)
                    except json.JSONDecodeError:
                        print(f"[capture_search_input] Could not parse string query {i}, keeping as-is")
                        processed_queries.append(query)
                elif hasattr(query, 'vector'):
                    query_dict = query.__dict__.copy()
                    if 'vector' in query_dict:
                        print(f"[capture_search_input] Removing vector from __dict__ for query {i}")
                        del query_dict['vector']
                    processed_queries.append(query_dict)
                else:
                    print(f"[capture_search_input] Unknown query type {type(query)} for query {i}")
                    processed_queries.append(query)
            
            kwargs_copy["vector_queries"] = processed_queries
            print(f"[capture_search_input] Finished processing {len(processed_queries)} queries")
        
        return _json(kwargs_copy)
    except Exception as e:
        print(f"[capture_search_input] Error processing: {e}")
        return _json(kwargs)

def capture_search_output(arguments: Dict) -> str:
    pager = arguments.get("result")
    if pager is None:
        return "NO_RESULT"

    try:
        summary = {
            "count": pager.get_count(),               
            "coverage": pager.get_coverage(),
            "facets": pager.get_facets(),
            "result_type": type(pager).__name__,
        }
    except Exception as err:             
        summary = {"error": str(err), "trace": traceback.format_exc()}

    return _json(summary)    

def capture_metadata(arguments: Dict) -> str:
    """Light-weight metadata: endpoint, index & latency."""
    inst = arguments.get("instance", None)
    meta = {
        "endpoint": getattr(inst, "_endpoint", "unknown"),
        "index": getattr(inst, "_index_name", "unknown"),
        "latency_ms": arguments.get("latency_ms"),
    }
    return _json(meta)                     

SEARCH_CLIENT_PROCESSOR = {
    "type": "search",
    "attributes": [
        [
            { "attribute": "type",     "accessor": lambda _: "azure.search" },
            { "attribute": "version_remove_me",  "accessor": lambda _: "11" },
            { "attribute": "endpoint", "accessor": lambda args: args["instance"]._endpoint if hasattr(args["instance"], "_endpoint") else "unknown" },
            { "attribute": "index_name", "accessor": lambda args: args["instance"]._index_name if hasattr(args["instance"], "_index_name") else "unknown" }
        ]
    ],
    "events": [
        {
            "name": "data.input",
            "attributes": [
                { "attribute": "parameters", "accessor": capture_search_input }
            ]
        },
        {
            "name": "data.output",
            "attributes": [
                { "attribute": "summary", "accessor": capture_search_output }
            ]
        },
        {
            "name": "metadata",
            "attributes": [
                { "attribute": "info", "accessor": capture_metadata }
            ]
        }
    ]
}
