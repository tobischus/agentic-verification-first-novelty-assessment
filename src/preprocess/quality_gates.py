"""Quality gates for the document-processing stage (Step 1)."""
from typing import Dict, List

MIN_FULLTEXT_CHARS = 1000


def compute_quality_gates(metadata: Dict, sections: List[Dict]) -> Dict:
    """Compute Step-1 quality gates from parsed metadata + body sections."""
    cited_papers = metadata.get("cited_papers") or []
    citation_contexts = metadata.get("citation_contexts") or []
    full_text_chars = sum(len(s.get("text", "")) for s in sections)

    gates = {
        "title_found": bool((metadata.get("title") or "").strip()),
        "abstract_found": bool((metadata.get("abstract") or "").strip()),
        "references_found": len(cited_papers) > 0,
        "citation_contexts_found": len(citation_contexts) > 0,
        "full_text_found": full_text_chars >= MIN_FULLTEXT_CHARS,
    }

    return {
        "gates": gates,
        "all_passed": all(gates.values()),
        "failed_gates": [name for name, ok in gates.items() if not ok],
        "counts": {
            "cited_papers": len(cited_papers),
            "citation_contexts": len(citation_contexts),
            "sections": len(sections),
            "full_text_chars": full_text_chars,
        },
        "title_source": metadata.get("title_source"),
        "title_needs_review": metadata.get("title_needs_review", False),
    }
