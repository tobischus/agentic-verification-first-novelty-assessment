"""Passage and section index over one document.

Documents are split into paragraph chunks with their section names. The index serves
section menus and section text, and a hybrid BM25 and embedding search.
"""
import re
import threading
from typing import List

import numpy as np

_WORD = re.compile(r"[a-z0-9]+")

# The embedding model is shared across threads, so calls into it are serialized.
_EMB_LOCK = threading.Lock()


def _tok(text: str) -> List[str]:
    return _WORD.findall((text or "").lower())


def paragraphs(text: str, max_chars: int = 1200) -> List[str]:
    """Split on blank lines and wrap paragraphs longer than `max_chars`."""
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
    """Chunks from a list of {'section', 'text'}."""
    chunks = []
    for s in sections or []:
        sec = (s.get("section") or "").strip()
        for para in paragraphs(s.get("text", "")):
            chunks.append({"passage_id": f"{doc_id}:{len(chunks)}", "section": sec, "text": para})
    return chunks


def chunks_from_grobid_text(text: str, doc_id: str) -> List[dict]:
    """Chunks from sectioned text of the form '## Section\\n...'."""
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
    """Chunks from unstructured text such as an abstract."""
    return [
        {"passage_id": f"{doc_id}:{i}", "section": section, "text": para}
        for i, para in enumerate(paragraphs(text))
    ]


class PassageIndex:
    """Sections and hybrid search over one document's chunks."""

    def __init__(self, chunks: List[dict], embedder=None):
        self.chunks = chunks or []
        self._bm25 = None
        self._emb = None
        self._emb_built = False
        self._embedder = embedder
        if self.chunks:
            try:
                from rank_bm25 import BM25Okapi

                self._bm25 = BM25Okapi([_tok(c["text"]) for c in self.chunks])
            except Exception:
                self._bm25 = None

    def _ensure_emb(self):
        """Embed the chunks on the first search."""
        if self._emb_built:
            return
        self._emb_built = True
        if self._embedder is None or not self.chunks:
            return
        try:
            with _EMB_LOCK:
                e = self._embedder.encode([c["text"] for c in self.chunks], convert_to_numpy=True)
            self._emb = e / (np.linalg.norm(e, axis=1, keepdims=True) + 1e-9)
        except Exception:
            self._emb = None

    def __bool__(self) -> bool:
        return bool(self.chunks)

    def search(self, query: str, k: int = 5, max_chars: int = 700) -> List[dict]:
        """Top-k passages by the mean of normalized BM25 and cosine scores."""
        if not self.chunks:
            return []
        self._ensure_emb()
        n = len(self.chunks)
        bm = None
        if self._bm25 is not None:
            bm = np.asarray(self._bm25.get_scores(_tok(query)), dtype=float)
            if bm.max() > 0:
                bm = bm / bm.max()
        cos = None
        if self._emb is not None and self._embedder is not None:
            try:
                with _EMB_LOCK:
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
        """Section names with a text preview and size, in document order."""
        agg = {}
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

    @staticmethod
    def _norm_name(t: str) -> str:
        return " ".join((t or "").split()).casefold()

    def _matches(self, want: str, section: str, exact: bool = False) -> bool:
        """Name match ignoring case and whitespace; substring match unless `exact`."""
        w, s = self._norm_name(want), self._norm_name(section)
        if not w:
            return False
        return w == s if exact else (w == s or w in s or s in w)


    def get_sections(self, names: List[str], max_total: int = 40000,
                     exact: bool = False) -> List[dict]:
        """Complete text of the requested sections in document order, up to `max_total`.

        A section that does not fit is skipped rather than truncated.
        """
        wanted = [n for n in (names or []) if n and n.strip()]
        out, used, seen = [], 0, set()
        for name in self.section_names():
            if name in seen:
                continue
            if not any(self._matches(w, name, exact) for w in wanted):
                continue
            seen.add(name)
            text = "\n\n".join(c["text"] for c in self.chunks if c["section"] == name).strip()
            if not text:
                continue
            if used + len(text) > max_total:
                continue
            out.append({"name": name, "text": text, "complete": True})
            used += len(text)
            if used >= max_total:
                break
        return out
