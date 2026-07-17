"""Agentic, DFS-based per-claim novelty assessment.

Replaces the one-shot ArtifactABuilder comparison with a tool-using agent loop
that deepens its understanding of a claim against prior work until the evidence
is sufficient to decide. Verification of quotes is a hard infrastructure
invariant (see evidence.py), not an agent action.
"""
