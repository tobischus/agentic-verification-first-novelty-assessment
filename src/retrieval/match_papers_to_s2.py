import json
import logging
import re
import time
import os
from dataclasses import dataclass, field
from rapidfuzz import fuzz
from typing import List, Optional, Dict, Any
from pathlib import Path
import requests
import numpy as np
from dotenv import load_dotenv

load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("paper_fetcher.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


@dataclass
class Paper:
    paper_id: str
    title: str = ""
    abstract: str = ""
    citations: List[str] = field(default_factory=list)
    embedding: Optional[np.ndarray] = None
    publication_date: Optional[str] = None
    venue: Optional[str] = None
    year: Optional[str] = None
    citation_count: int = 0
    novel: Optional[str] = None
    authors: str = ""
    cited_paper: bool = False
    externalIds: Optional[Dict] = None
    doi: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert Paper object to dictionary, handling numpy arrays."""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, np.ndarray):
                result[key] = value.tolist() if value is not None else None
            else:
                result[key] = value
        return result


class TransientS2Error(Exception):
    """S2 was unavailable (429 / 5xx / network) after exhausting retries."""


class SemanticScholarAPI:
    """Class to handle Semantic Scholar API interactions with rate limiting and error handling."""

    def __init__(self, api_key: str = None, rate_limit_delay: float = 1.1):
        if not api_key:
            api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")

        if not api_key:
            logger.warning(
                "No Semantic Scholar API key provided. Using unauthenticated requests (lower rate limits)."
            )

        self.api_key = api_key
        self.rate_limit_delay = rate_limit_delay
        self.min_delay = rate_limit_delay
        self.max_delay = 8.0
        self.base_url = "https://api.semanticscholar.org/graph/v1/paper/search/match"
        self.headers = {"X-API-KEY": api_key} if api_key and api_key != "---" else {}
        self.last_request_time = 0

        logger.info(
            f"Initialized Semantic Scholar API client with rate limit: {rate_limit_delay}s "
            f"(adaptive up to {self.max_delay}s)"
        )

    def _rate_limit(self):
        """Ensure we don't exceed rate limits."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    @staticmethod
    def _retry_after(response, default: float) -> float:
        """Retry-After seconds, capped, else `default`."""
        ra = response.headers.get("Retry-After")
        if ra:
            try:
                return min(30.0, float(ra))
            except ValueError:
                pass
        return default

    def _make_request(self, params: Dict[str, Any], max_attempts: int = 8) -> requests.Response:
        """Make an S2 request with adaptive, Retry-After-aware rate limiting."""
        backoff = 2.0
        last_reason = "unknown"
        for attempt in range(1, max_attempts + 1):
            self._rate_limit()
            try:
                response = requests.get(
                    self.base_url, params=params, headers=self.headers, timeout=30
                )
            except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
                last_reason = f"network error ({e})"
                if attempt == max_attempts:
                    break
                logger.warning(
                    f"Request error ({e}); retry {attempt}/{max_attempts} in {backoff:.0f}s"
                )
                time.sleep(backoff)
                backoff = min(20.0, backoff * 2)
                continue

            if response.status_code == 429:
                self.rate_limit_delay = min(self.max_delay, self.rate_limit_delay * 1.5)
                wait = self._retry_after(response, default=backoff)
                logger.warning(
                    f"S2 rate limited (429); waiting {wait:.1f}s, spacing now "
                    f"{self.rate_limit_delay:.1f}s (attempt {attempt}/{max_attempts})"
                )
                last_reason = "429 rate limited"
                if attempt == max_attempts:
                    break
                time.sleep(wait)
                backoff = min(20.0, backoff * 2)
                continue

            if response.status_code >= 500:
                last_reason = f"server error {response.status_code}"
                if attempt == max_attempts:
                    break
                logger.warning(
                    f"S2 server error {response.status_code}; retry "
                    f"{attempt}/{max_attempts} in {backoff:.0f}s"
                )
                time.sleep(backoff)
                backoff = min(20.0, backoff * 2)
                continue

            self.rate_limit_delay = max(self.min_delay, self.rate_limit_delay * 0.8)
            return response

        raise TransientS2Error(f"S2 unavailable after {max_attempts} attempts: {last_reason}")

    _S2_FIELDS = (
        "title,abstract,paperId,publicationDate,venue,year,citationCount,authors,externalIds"
    )

    @staticmethod
    def _title_variants(title: str) -> List[str]:
        """Progressively cleaned title queries to try against S2, most specific first."""
        title = (title or "").strip()
        variants = [title]
        parts = re.split(r"\.\s+", title)
        if len(parts) > 1:
            first = parts[0].strip().rstrip(".")
            if 15 <= len(first) < len(title):
                variants.append(first)
        seen, out = set(), []
        for v in variants:
            k = v.lower()
            if v and k not in seen:
                seen.add(k)
                out.append(v)
        return out

    @staticmethod
    def _parse_match_response(response) -> Optional[Paper]:
        """Build a Paper from an S2 match response, or None for a genuine no-match."""
        if response.status_code != 200:
            return None
        data = response.json()
        if "data" not in data or not data["data"]:
            return None
        paper_data = data["data"][0]
        authors = ""
        if paper_data.get("authors"):
            authors = ", ".join(a.get("name", "") for a in paper_data["authors"])
        ext_ids = paper_data.get("externalIds") or {}
        return Paper(
            paper_id=paper_data.get("paperId", "Unknown ID"),
            title=paper_data.get("title", "Unknown Title"),
            abstract=paper_data.get("abstract", "No abstract available"),
            publication_date=paper_data.get("publicationDate"),
            venue=paper_data.get("venue"),
            year=str(paper_data.get("year")) if paper_data.get("year") is not None else None,
            citation_count=paper_data.get("citationCount", 0),
            authors=authors,
            externalIds=ext_ids,
            doi=ext_ids.get("DOI"),
        )

    def get_paper_by_title(self, title: str, max_attempts: int = 8) -> Optional[Paper]:
        """Fetch a paper from Semantic Scholar by title and return a Paper object."""
        if not title or not title.strip():
            logger.warning("Empty title provided")
            return None
        title = title.strip()
        variants = self._title_variants(title)
        transient = None

        for i, q in enumerate(variants):
            try:
                response = self._make_request(
                    {"query": q, "fields": self._S2_FIELDS}, max_attempts=max_attempts
                )
            except TransientS2Error as e:
                transient = e
                continue

            try:
                paper = self._parse_match_response(response)
            except Exception as e:
                logger.error(f"Error parsing S2 response for '{q[:60]}': {e}")
                paper = None

            if paper is None:
                logger.info(f"No S2 match for: '{q[:70]}'")
                continue

            if i == 0:
                logger.info(f"✅ Found paper: '{paper.title}' ({paper.year})")
                return paper

            qn = re.sub(r"[^a-z0-9]", "", q.lower())
            tn = re.sub(r"[^a-z0-9]", "", (paper.title or "").lower())
            if qn and tn and fuzz.ratio(tn[: len(qn)], qn) >= 85:
                logger.info(
                    f"✅ matched via cleaned title '{q[:50]}…' -> '{paper.title[:55]}' ({paper.year})"
                )
                return paper
            logger.info(f"rejected non-prefix match for cleaned '{q[:50]}' -> '{paper.title[:50]}'")

        if transient is not None:
            raise transient
        return None


def process_for_pipeline(
    data_dir: str, submission_id: str, api_key: str = None, rate_limit_delay: float = 1.1
):
    """Process a single submission for pipeline integration."""
    input_file = Path(data_dir) / submission_id / f"{submission_id}.json"

    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    with open(input_file, "r", encoding="utf-8") as f:
        submission_data = json.load(f)

    api_client = SemanticScholarAPI(api_key, rate_limit_delay)

    cited_papers = submission_data.get("cited_papers", [])
    n_cited = len(cited_papers)
    logger.info(f"Processing {n_cited} cited papers")

    try:
        import progress as _progress
    except Exception:
        _progress = None
    if _progress:
        _progress.start_phase("Enriching references", n_cited)

    try:
        transient_failures = []
        for paper_idx, paper in enumerate(cited_papers):
            title = paper.get("title", "").strip()

            if not title:
                logger.debug(f"Skipping paper {paper_idx + 1}: no title")
                paper["ss_paper_obj"] = None
                if _progress:
                    _progress.report(paper_idx + 1, n_cited)
                continue

            logger.debug(f"Processing paper {paper_idx + 1}: '{title}'")
            try:
                ss_paper_obj = api_client.get_paper_by_title(title)
                paper["ss_paper_obj"] = ss_paper_obj.to_dict() if ss_paper_obj else None
            except TransientS2Error as e:
                logger.warning(f"Transient S2 failure for '{title[:60]}', will retry: {e}")
                paper["ss_paper_obj"] = None
                transient_failures.append(paper)

            if _progress:
                _progress.report(paper_idx + 1, n_cited)

        if transient_failures:
            logger.info(
                f"Retry pass for {len(transient_failures)} references that hit transient S2 errors"
            )
            if _progress:
                _progress.start_phase("Re-fetching rate-limited refs", len(transient_failures))
            for i, paper in enumerate(transient_failures):
                try:
                    ss_paper_obj = api_client.get_paper_by_title(paper.get("title", "").strip())
                    paper["ss_paper_obj"] = ss_paper_obj.to_dict() if ss_paper_obj else None
                except TransientS2Error:
                    paper["ss_paper_obj"] = None
                if _progress:
                    _progress.report(i + 1, len(transient_failures))

        with open(input_file, "w", encoding="utf-8") as f:
            json.dump(submission_data, f, indent=2, ensure_ascii=False)

        found_papers = sum(1 for c in cited_papers if c.get("ss_paper_obj"))
        unresolved = sum(1 for p in transient_failures if not p.get("ss_paper_obj"))
        failed_papers = len(cited_papers) - found_papers
        logger.info(
            f"✅ Processed {len(cited_papers)} cited papers: {found_papers} found, "
            f"{failed_papers} not enriched ({unresolved} still rate-limited after retry, "
            f"rest are genuine no-match)"
        )
        return True

    except Exception as e:
        logger.error(f"Error processing submission {submission_id}: {e}")
        return False
