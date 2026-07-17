#!/usr/bin/env python3
"""
Step 2: Claim & Paper Understanding Extraction.

Reads the Step-1 outputs ({id}.json metadata + {id}_fulltext.json sections) and
produces {id}_claims.json:
  - summary: a concise summary of the submission
  - claims: the claimed novelty contributions as first-class, individually
    addressable objects (stable id, verbatim claim_text for provenance,
    normalized description for downstream retrieval/comparison, source hint)

Each claim carries human-in-the-loop state (origin, status) so the reviewer can
accept / edit / delete / add claims. Claims that proceed to later stages are
those returned by validated_claims() (everything not 'rejected').
"""
import argparse
import json
import os
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()


EXTRACTION_PROMPT = """You are extracting the CLAIMED NOVELTY CONTRIBUTIONS of a scientific paper, for peer-review novelty assessment.

A novelty claim is anything the authors explicitly present as their OWN new contribution: a method, model, architecture, algorithm, framework, task, benchmark, dataset, theoretical result, or problem formulation -- OR an empirical finding, analysis, or practical guideline they frame as a contribution. Cues: "we propose", "we introduce", "our contribution", "we are the first", "we show that", "we find that", "we provide guidelines".

Do NOT include background, motivation, related work, or isolated performance numbers.

Capture the DISTINCT SUBSTANTIVE contributions the authors present. A claim must be a contribution whose NOVELTY is worth assessing on its own: a new method, artifact, task, benchmark, dataset, theoretical result, or a key empirical finding/analysis the authors highlight.

STRICT exclusions -- these are NOT standalone claims, even when the authors' contributions statement mentions them:
- auxiliary evaluation steps or extra measurements that merely support another contribution (e.g. "we also measure transferability", "we conduct ablations", "we report additional metrics"): fold them into the claim they support, or drop them.
- releasing code or trained models ("we release our code and models") -- standard practice, not a novelty contribution. Exception: a released dataset/benchmark that the paper presents as a contribution in itself.
- restatements of another claim at a different level of detail, and sub-parts of a single artifact (a benchmark and its corpora / tasks / metrics, or a method and its components, is ONE claim).
- descriptions of HOW a proposed method/artifact works (its objectives, optimization targets, components, design choices) -- that detail belongs inside the method claim, never a separate claim.

Keep genuinely different substantive contributions as SEPARATE claims (e.g. the proposed method vs. a key empirical finding it enables) -- do not collapse them into one. Stay faithful: use the authors' own terminology and do not invent contributions. A paper typically has 2-4 real novelty claims.

FIRST look for the paper's EXPLICIT contribution statement in the introduction: a paragraph or list beginning "Our contributions", "We make the following contributions", "In summary, our contributions are", "In this paper we (1) ... (2) ...", or similar -- usually near the END of the introduction. If such a statement exists, base the claims on the contributions enumerated THERE (each evidence quote copied verbatim from that statement; do not replace them with sentences from elsewhere) -- but keep only the SUBSTANTIVE ones, applying the strict exclusions above.
Only if NO such explicit statement exists, extract the claims from the authors' individual "we propose / we introduce / we show / we find" statements instead.

For each distinct claim provide exactly two fields:
- claim: one concise sentence stating the contribution, in the authors' terminology.
- evidence: ONE exact, CONTIGUOUS verbatim passage from the paper text below that states this contribution -- copied character-for-character (a single sentence, or a few consecutive sentences from the SAME place in the text). Do NOT stitch together sentences from different parts of the paper, and do not paraphrase or alter wording.

Paper title: {title}

{content}
"""


class NoveltyClaim(BaseModel):
    """A single claimed novelty contribution and its verbatim evidence."""

    claim: str = Field(description="One concise sentence stating the claimed novel contribution")
    evidence: str = Field(
        description="EXACT verbatim passage from the paper stating this contribution (the provenance/proof)"
    )


class PaperUnderstanding(BaseModel):
    """The claimed novelty contributions of a submission."""

    claims: List[NoveltyClaim] = Field(description="The claimed novelty contributions")


class ClaimExtractor:
    """Extracts a paper summary and claimed novelty contributions (Step 2)."""

    def __init__(self, model_name: str = "gpt-4.1", temperature: float = 0.0):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        self.llm = ChatOpenAI(
            model_name=model_name, temperature=temperature, api_key=api_key
        )

    @staticmethod
    def _pick_sections(sections, keywords) -> str:
        """Join the text of sections whose head matches any keyword."""
        out = []
        for s in sections:
            head = (s.get("section") or "").lower()
            if any(k in head for k in keywords) and s.get("text", "").strip():
                out.append(s["text"].strip())
        return "\n".join(out)

    def load_inputs(self, data_dir: str, submission_id: str):
        """Load title/abstract + introduction/conclusion text from Step-1 outputs.

        The "introduction" is the LEADING region of the body in document order (first
        ~20k chars, section headings kept). Matching only the section TITLED
        "Introduction" is not enough: GROBID often mis-splits the intro into unnamed
        sections ('* *'), so the authors' contributions paragraph at the end of the
        intro can land OUTSIDE the titled section and the claims get missed."""
        sub = Path(data_dir) / submission_id
        meta = json.loads((sub / f"{submission_id}.json").read_text(encoding="utf-8"))

        sections = []
        ft_path = sub / f"{submission_id}_fulltext.json"
        if ft_path.exists():
            sections = json.loads(ft_path.read_text(encoding="utf-8")).get("sections", [])

        lead, used = [], 0
        for s in sections:
            text = (s.get("text") or "").strip()
            if not text:
                continue
            head = (s.get("section") or "").strip()
            block = f"[{head}]\n{text}" if head else text
            lead.append(block)
            used += len(block)
            if used >= 20000:
                break
        intro = "\n\n".join(lead)

        conclusion = self._pick_sections(sections, ["conclusion", "discussion"])
        if not conclusion and sections:
            conclusion = sections[-1].get("text", "")
        return meta, intro, conclusion

    @staticmethod
    def _normalize(text: str) -> str:
        """Whitespace-collapsed, lowercased text for verbatim-quote verification."""
        return " ".join((text or "").split()).lower()

    def extract(self, data_dir: str, submission_id: str) -> dict:
        """Run extraction and write {id}_claims.json.

        The INTRODUCTION is the primary source: authors state their contributions
        there (usually near its end), so the first attempt sees only the intro and
        the evidence quotes come from it. Only if the intro is missing or yields no
        claims do we widen to abstract + conclusion as a fallback."""
        meta, intro, conclusion = self.load_inputs(data_dir, submission_id)

        abstract = meta.get("abstract", "") or ""
        intro_text = (intro or "").strip()

        def _run(content: str):
            prompt = EXTRACTION_PROMPT.format(title=meta.get("title", ""), content=content)
            return self.llm.with_structured_output(PaperUnderstanding).invoke(prompt)

        result, scope = None, ""
        if intro_text:
            result = _run("Introduction (leading part of the paper):\n" + intro_text)
            scope = "introduction"
        if not (result and result.claims):
            # fallback: no intro, or the intro contained no claim statements
            content = "\n\n".join(part for part in (
                f"Abstract:\n{abstract}" if abstract else "",
                f"Introduction:\n{intro_text}" if intro_text else "",
                f"Conclusion / Discussion:\n{(conclusion or '')[:6000]}" if (conclusion or "").strip() else "",
            ) if part)
            result = _run(content)
            scope = "abstract+introduction+conclusion"

        # The text the evidence quote should be verbatim-traceable to.
        source_text = self._normalize("\n".join([abstract, intro or "", conclusion or ""]))

        claims = []
        for i, c in enumerate(result.claims if result else [], 1):
            claim_text = (c.claim or "").strip()
            quote = (c.evidence or "").strip()
            verified = bool(quote) and self._normalize(quote) in source_text
            claims.append(
                {
                    "id": f"claim_{i}",
                    # name/description are derived from the claim (the LLM only returns
                    # claim + evidence); downstream (Artifact A recall, report) uses them.
                    "name": " ".join(claim_text.split()[:12]),
                    "claim_text": claim_text,
                    "evidence_quote": quote,
                    "evidence_verified": verified,  # is the quote verbatim-present in the paper?
                    "description": claim_text,
                    "source": "",
                    "origin": "llm",
                    "status": "pending",  # HITL: pending -> accepted/edited/rejected
                }
            )

        doc = {
            "submission_id": submission_id,
            "title": meta.get("title", ""),
            "publication_date": meta.get("publication_date"),
            "year": meta.get("year"),
            "date_source": meta.get("date_source"),
            # which paper text the claims were extracted from (introduction-primary)
            "extraction_scope": scope,
            "claims": claims,
        }
        out_path = Path(data_dir) / submission_id / f"{submission_id}_claims.json"
        out_path.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return doc


# --------------------------------------------------------------------------- #
# Human-in-the-loop operations on the claims document.
# The orchestrator loads {id}_claims.json, applies these, and saves it back.
# Soft-delete (status='rejected') is used to keep a full audit trail.
# --------------------------------------------------------------------------- #


def _find(doc: dict, claim_id: str) -> dict:
    for c in doc["claims"]:
        if c["id"] == claim_id:
            return c
    raise KeyError(f"claim not found: {claim_id}")


def accept_claim(doc: dict, claim_id: str) -> dict:
    _find(doc, claim_id)["status"] = "accepted"
    return doc


def edit_claim(doc: dict, claim_id: str, **fields) -> dict:
    c = _find(doc, claim_id)
    for k, v in fields.items():
        if k in ("name", "claim_text", "description", "source"):
            c[k] = v
    c["status"] = "edited"
    return doc


def delete_claim(doc: dict, claim_id: str) -> dict:
    # Soft-delete: keep the entry for auditability (verification-first).
    _find(doc, claim_id)["status"] = "rejected"
    return doc


def add_claim(
    doc: dict, name: str, claim_text: str = "", description: str = "", source: str = "reviewer"
) -> dict:
    existing = {c["id"] for c in doc["claims"]}
    i = len(doc["claims"]) + 1
    while f"claim_{i}" in existing:
        i += 1
    doc["claims"].append(
        {
            "id": f"claim_{i}",
            "name": name,
            "claim_text": claim_text,
            "evidence_quote": "",
            "evidence_verified": False,
            "description": description,
            "source": source,
            "origin": "reviewer",
            "status": "accepted",
        }
    )
    return doc


def validated_claims(doc: dict) -> List[dict]:
    """Claims that proceed to later stages (everything the reviewer did not reject)."""
    return [c for c in doc["claims"] if c["status"] != "rejected"]


def main():
    ap = argparse.ArgumentParser(description="Step 2: claim & paper understanding extraction")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--submission-id", required=True)
    ap.add_argument("--model", default="gpt-4.1")
    args = ap.parse_args()

    doc = ClaimExtractor(model_name=args.model).extract(args.data_dir, args.submission_id)
    print(f"Title: {doc.get('title')}  |  date (cutoff): {doc.get('publication_date')}\n")
    print(f"Claimed novelty contributions ({len(doc['claims'])}):")
    for c in doc["claims"]:
        print(f"  [{c['id']}] {c['claim_text']}")
        v = "verified" if c.get("evidence_verified") else "UNVERIFIED"
        print(f"        evidence ({v}): {c.get('evidence_quote')}")


if __name__ == "__main__":
    main()
