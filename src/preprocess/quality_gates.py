#!/usr/bin/env python3
"""
Quality gates for the document-processing stage (Step 1).

After GROBID extraction, verify that the pieces the downstream pipeline depends
on are actually present: title, abstract, references, citation contexts, and
full text. Each gate is a verifiable boolean; the orchestrator can decide to
proceed, flag for the reviewer, or abort. This keeps Step 1 deterministic and
auditable.
"""
from typing import Dict, List

# Minimum body length (chars) to consider full-text extraction successful.
MIN_FULLTEXT_CHARS = 1000


def compute_quality_gates(metadata: Dict, sections: List[Dict]) -> Dict:
    """Compute Step-1 quality gates from parsed metadata + body sections.

    Args:
        metadata: parsed {id}.json dict (title, abstract, cited_papers, citation_contexts, ...)
        sections: list of {"section", "text"} from extract_full_text_sections

    Returns:
        A report dict with per-gate booleans, an overall flag, and counts.
    """
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
        # Metadata that the reviewer should confirm in the human-in-the-loop step.
        "title_source": metadata.get("title_source"),
        "title_needs_review": metadata.get("title_needs_review", False),
    }
