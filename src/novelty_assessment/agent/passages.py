#!/usr/bin/env python3
"""
Passage indexing for the read tools -- keeps agent context small.

The agent never reads a whole PDF: search_submission / read_paper return only the
top-k passages (or a single section) that match a query, sliced VERBATIM from the
document's source text. A lightweight BM25 index over paragraph/section chunks
backs this; it is built once per document and reused across queries and claims.

Chunking supports the two source shapes in this repo:
  * submission full text -> {id}_fulltext.json  = {"sections": [{"section","text"}]}
  * candidate full text  -> grobid_fulltext/{pid}.txt  = "## Section\n...\n\n## ..."
with an abstract/intro fallback for papers that have no full text.
"""
import re
from typing import List, Optional

import numpy as np

_WORD = re.compile(r"[a-z0-9]+")


def _tok(text: str) -> List[str]:
    return _WORD.findall((text or "").lower())


def paragraphs(text: str, max_chars: int = 1200) -> List[str]:
    """Split on blank lines; hard-wrap over-long paragraphs so chunks stay small."""
    out = []
    for para in re.split(r"\n\s*\n", text or ""):
        para = para.strip()
        if not para:
            continue
        while len(para) > max_chars:
            cut = para.rfind(". ", 0, max_chars)
            cut = cut + 1 if cut > max_chars // 2 else max_chars
            out.append(para[:cut].strip())
            para = para[cut:].strip()
        if para:
            out.append(para)
    return out


def chunks_from_sections(sections: List[dict], doc_id: str) -> List[dict]:
    """Chunks from a list of {'section','text'} (submission fulltext json shape)."""
    chunks = []
    for s in sections or []:
        sec = (s.get("section") or "").strip()
        for para in paragraphs(s.get("text", "")):
            chunks.append({"passage_id": f"{doc_id}:{len(chunks)}", "section": sec, "text": para})
    return chunks


def chunks_from_grobid_text(text: str, doc_id: str) -> List[dict]:
    """Chunks from a '## Section\\n...' grobid_fulltext dump (candidate papers)."""
    chunks: List[dict] = []
    current = ""
    buf: List[str] = []

    def flush():
        if buf:
            for para in paragraphs("\n\n".join(buf)):
                chunks.append({"passage_id": f"{doc_id}:{len(chunks)}", "section": current, "text": para})
            buf.clear()

    for line in (text or "").splitlines():
        if line.startswith("## "):
            flush()
            current = line[3:].strip()
        else:
            buf.append(line)
    flush()
    return chunks


def chunks_from_plain(text: str, doc_id: str, section: str = "") -> List[dict]:
    """Chunks from an unstructured blob (abstract+intro fallback)."""
    return [
        {"passage_id": f"{doc_id}:{i}", "section": section, "text": para}
        for i, para in enumerate(paragraphs(text))
    ]


class PassageIndex:
    """Hybrid lexical (BM25) + semantic (embedding) search over one document's chunks.

    Combining both finds the passage that is CONCEPTUALLY most relevant to a query,
    not just the one with matching keywords -- important for picking the right
    comparison passage. Built once per document, queried many times. If an embedder
    is given, chunk embeddings are precomputed once here."""

    def __init__(self, chunks: List[dict], embedder=None):
        self.chunks = chunks or []
        self._bm25 = None
        self._emb = None
        self._embedder = embedder
        if self.chunks:
            try:
                from rank_bm25 import BM25Okapi

                self._bm25 = BM25Okapi([_tok(c["text"]) for c in self.chunks])
            except Exception:
                self._bm25 = None
            if embedder is not None:
                try:
                    e = embedder.encode([c["text"] for c in self.chunks], convert_to_numpy=True)
                    self._emb = e / (np.linalg.norm(e, axis=1, keepdims=True) + 1e-9)
                except Exception:
                    self._emb = None

    def __bool__(self) -> bool:
        return bool(self.chunks)

    def search(self, query: str, k: int = 5, max_chars: int = 700) -> List[dict]:
        """Top-k passages for a query (trimmed for context economy)."""
        if not self.chunks:
            return []
        n = len(self.chunks)
        # lexical scores, normalized to [0, 1]
        bm = None
        if self._bm25 is not None:
            bm = np.asarray(self._bm25.get_scores(_tok(query)), dtype=float)
            if bm.max() > 0:
                bm = bm / bm.max()
        # semantic cosine scores mapped to [0, 1]
        cos = None
        if self._emb is not None and self._embedder is not None:
            try:
                q = self._embedder.encode([query], convert_to_numpy=True)[0]
                q = q / (np.linalg.norm(q) + 1e-9)
                cos = (self._emb @ q + 1.0) / 2.0
            except Exception:
                cos = None
        if bm is not None and cos is not None:
            final = 0.5 * bm + 0.5 * cos
        elif cos is not None:
            final = cos
        elif bm is not None:
            final = bm
        else:
            final = np.zeros(n)
        order = np.argsort(-final)[:k]
        picked = [int(i) for i in order if final[i] > 0] or [int(order[0])]
        return [
            {
                "passage_id": self.chunks[i]["passage_id"],
                "section": self.chunks[i]["section"],
                "text": self.chunks[i]["text"][:max_chars],
                "score": round(float(final[i]), 3),
            }
            for i in picked
        ]

    def section_names(self) -> List[str]:
        seen, out = set(), []
        for c in self.chunks:
            sec = c["section"]
            if sec and sec not in seen:
                seen.add(sec)
                out.append(sec)
        return out

    def section_previews(self, max_preview: int = 200) -> List[dict]:
        """Section titles with a short text preview + size, so the agent can pick which
        sections to load by what each one is about (titles alone can be terse)."""
        agg = {}          # name -> [first_text, total_chars]
        order = []
        for c in self.chunks:
            sec = c["section"]
            if not sec:
                continue
            if sec not in agg:
                agg[sec] = [c["text"], len(c["text"])]
                order.append(sec)
            else:
                if not agg[sec][0]:
                    agg[sec][0] = c["text"]
                agg[sec][1] += len(c["text"])
        return [
            {"name": name, "preview": " ".join(agg[name][0].split())[:max_preview],
             "chars": agg[name][1]}
            for name in order
        ]

    def _matches(self, want: str, section: str) -> bool:
        w, s = want.lower().strip(), section.lower().strip()
        return bool(w) and (w == s or w in s or s in w)

    def get_section(self, name: str, max_chars: int = 4000) -> Optional[str]:
        """Concatenated text of a named section (fuzzy, case-insensitive title match)."""
        want = (name or "").lower().strip()
        if not want:
            return None
        parts = [c["text"] for c in self.chunks if self._matches(want, c["section"])]
        if not parts:
            return None
        return "\n\n".join(parts)[:max_chars]

    def get_sections(self, names: List[str], max_total: int = 40000) -> List[dict]:
        """Full text of the requested sections (no per-section cap; only a generous
        total guard so a pathological paper can't blow up the prompt). Returns
        [{'name','text'}] in document order, each matched section once."""
        wanted = [n for n in (names or []) if n and n.strip()]
        out, used, seen = [], 0, set()
        for name in self.section_names():          # document order
            if name in seen:
                continue
            if not any(self._matches(w, name) for w in wanted):
                continue
            seen.add(name)
            text = "\n\n".join(c["text"] for c in self.chunks if c["section"] == name).strip()
            if not text:
                continue
            if used + len(text) > max_total:
                text = text[: max(0, max_total - used)]
            out.append({"name": name, "text": text})
            used += len(text)
            if used >= max_total:
                break
        return out

    def full_text(self) -> str:
        """The whole document text -- used to VERIFY quotes against the real source."""
        return "\n\n".join(c["text"] for c in self.chunks)
