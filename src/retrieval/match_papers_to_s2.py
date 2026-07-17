import json
import logging
import re
import time
import os
import argparse
from dataclasses import dataclass, field
from rapidfuzz import fuzz
from typing import List, Optional, Dict, Any
from pathlib import Path
import requests
import numpy as np
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# Configure logging
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
    citations: List[str] = field(
        default_factory=list
    )  # List of paper IDs that this paper cites
    embedding: Optional[np.ndarray] = None
    publication_date: Optional[str] = None
    venue: Optional[str] = None
    year: Optional[str] = None  # Changed to string for consistency
    citation_count: int = 0
    novel: Optional[str] = None
    authors: str = ""  # Changed to string for consistency with retrieval.py
    cited_paper: bool = False
    # Persist S2 external identifiers so downstream PDF fetch (Step 4) knows the arXiv id /
    # DOI WITHOUT a fresh per-paper S2 call (which gets 429-throttled) -> robust downloads.
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
    """S2 was unavailable (429 / 5xx / network) after exhausting retries.

    Distinct from a genuine 'no match' (404 / empty result): a transient error means
    the reference is likely matchable, we just couldn't reach S2 right now -> it must
    NOT be treated as 'not found' and dropped, or the cited set becomes non-deterministic.
    """


class SemanticScholarAPI:
    """Class to handle Semantic Scholar API interactions with rate limiting and error handling."""

    def __init__(self, api_key: str = None, rate_limit_delay: float = 1.1):
        if not api_key:
            api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        
        if not api_key:
            logger.warning("No Semantic Scholar API key provided. Using unauthenticated requests (lower rate limits).")
            
        self.api_key = api_key
        # Adaptive spacing: starts at rate_limit_delay, grows on 429, eases on success.
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
        """Seconds S2 asks us to wait (Retry-After header), capped; else `default`."""
        ra = response.headers.get("Retry-After")
        if ra:
            try:
                return min(30.0, float(ra))
            except ValueError:
                pass
        return default

    def _make_request(self, params: Dict[str, Any], max_attempts: int = 8) -> requests.Response:
        """Make an S2 request with adaptive, Retry-After-aware rate limiting.

        On 429 we honor the server's Retry-After and *increase* the spacing for
        subsequent requests (so we converge on S2's current allowance instead of
        hammering it); on success we ease the spacing back down. This both avoids
        the long blind-backoff storms and stops dropping papers to rate limits.
        """
        backoff = 2.0
        last_reason = "unknown"
        for attempt in range(1, max_attempts + 1):
            self._rate_limit()  # honors the current (adaptive) self.rate_limit_delay
            try:
                response = requests.get(
                    self.base_url, params=params, headers=self.headers, timeout=30
                )
            except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
                last_reason = f"network error ({e})"
                if attempt == max_attempts:
                    break
                logger.warning(f"Request error ({e}); retry {attempt}/{max_attempts} in {backoff:.0f}s")
                time.sleep(backoff)
                backoff = min(20.0, backoff * 2)
                continue

            if response.status_code == 429:
                # Slow down future requests, and wait exactly as long as S2 asks.
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

            # Transient S2 server errors (5xx) are NOT a real answer -> retry instead
            # of dropping the paper. (404 'no match' is definitive and falls through.)
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

            # Definitive response (200 match / 404 no-match): ease spacing back down.
            self.rate_limit_delay = max(self.min_delay, self.rate_limit_delay * 0.8)
            return response

        # Exhausted all attempts on a transient condition (429 / 5xx / network). Signal
        # this distinctly so the caller can RETRY the reference later instead of
        # mistaking it for a genuine 'not found' and silently dropping it.
        raise TransientS2Error(f"S2 unavailable after {max_attempts} attempts: {last_reason}")

    _S2_FIELDS = "title,abstract,paperId,publicationDate,venue,year,citationCount,authors,externalIds"

    @staticmethod
    def _title_variants(title: str) -> List[str]:
        """Progressively cleaned title queries to try against S2, most specific first.

        GROBID frequently concatenates the venue/journal/notes onto the title field as
        "Title. Venue ..." (or "Title. In Proceedings ..."). When the full string fails
        to match, retrying with just the LEADING title segment recovers many references.
        This is a generic heuristic (split on sentence boundaries) -- NOT tuned to any
        specific paper; titles without such a boundary just yield the original (= old
        behaviour, no extra request).
        """
        title = (title or "").strip()
        variants = [title]
        # The real title is almost always the first sentence-like segment; trailing
        # segments are venue/journal/editor notes appended by GROBID.
        parts = re.split(r"\.\s+", title)
        if len(parts) > 1:
            first = parts[0].strip().rstrip(".")
            if 15 <= len(first) < len(title):  # substantially shorter & still meaningful
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
        paper_data = data["data"][0]  # best match
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
        """
        Fetch a paper from Semantic Scholar by title and return a Paper object.

        Tries the full title first (unchanged behaviour); only if that finds nothing
        does it retry with a cleaned, shorter title variant (stripping a GROBID-appended
        venue), guarded by a title-similarity check so a looser query can't attach the
        wrong paper.

        Returns None only for a genuine 'no match'; raises TransientS2Error if S2 was
        unreachable so the caller can retry the reference later.
        """
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
                transient = e  # try a cleaner variant; if all are transient, raise below
                continue

            try:
                paper = self._parse_match_response(response)
            except Exception as e:
                logger.error(f"Error parsing S2 response for '{q[:60]}': {e}")
                paper = None

            if paper is None:
                logger.info(f"No S2 match for: '{q[:70]}'")
                continue

            # Full title (i==0): trust S2's match endpoint as before.
            if i == 0:
                logger.info(f"✅ Found paper: '{paper.title}' ({paper.year})")
                return paper

            # Cleaned variant (i>0): accept only if the searched text is a TITLE PREFIX
            # of the returned paper. Real titles lead the field; a GROBID-appended
            # metadata segment (publisher/location/year) does not -- so a prefix check
            # rejects false matches that merely share a few stray tokens (e.g. a
            # "London: Routledge, 2000" fragment matching an unrelated book) while
            # accepting genuine "Title. Venue" recoveries. token_set_ratio was too
            # lenient here (short fragments score high), so we use a leading-edge ratio.
            qn = re.sub(r"[^a-z0-9]", "", q.lower())
            tn = re.sub(r"[^a-z0-9]", "", (paper.title or "").lower())
            if qn and tn and fuzz.ratio(tn[: len(qn)], qn) >= 85:
                logger.info(f"✅ matched via cleaned title '{q[:50]}…' -> '{paper.title[:55]}' ({paper.year})")
                return paper
            logger.info(
                f"rejected non-prefix match for cleaned '{q[:50]}' -> '{paper.title[:50]}'"
            )

        # No clean match from any variant. If S2 was unreachable on the full title,
        # surface that as transient so the reference is retried, not silently dropped.
        if transient is not None:
            raise transient
        return None


def process_for_pipeline(data_dir: str, submission_id: str, api_key: str = None, rate_limit_delay: float = 1.1):
    """
    Process a single submission for pipeline integration.
    
    Args:
        data_dir: Base data directory for pipeline
        submission_id: ID of the submission
        api_key: Semantic Scholar API key (optional)
        rate_limit_delay: Delay between API requests in seconds
    
    Returns:
        Processing statistics
    """
    # Input file path 
    input_file = Path(data_dir) / submission_id / f"{submission_id}.json"
    
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")
    
    # Load single submission data
    with open(input_file, "r", encoding="utf-8") as f:
        submission_data = json.load(f)
    
    # Initialize API client
    api_client = SemanticScholarAPI(api_key, rate_limit_delay)
    
    # Process cited papers
    cited_papers = submission_data.get("cited_papers", [])
    n_cited = len(cited_papers)
    logger.info(f"Processing {n_cited} cited papers")

    try:
        import progress as _progress  # optional sub-progress for the frontend
    except Exception:
        _progress = None
    if _progress:
        _progress.start_phase("Enriching references", n_cited)

    try:
        # References that hit a transient S2 error (429/5xx/network) -> retried in a
        # second pass rather than silently dropped, so the enriched cited set does not
        # depend on which references happened to hit a rate-limit window this run.
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

        # Second pass over the transient failures (the rate-limit window has usually
        # passed by now). This is what makes the cited set reproducible across runs.
        if transient_failures:
            logger.info(f"Retry pass for {len(transient_failures)} references that hit transient S2 errors")
            if _progress:
                _progress.start_phase("Re-fetching rate-limited refs", len(transient_failures))
            for i, paper in enumerate(transient_failures):
                try:
                    ss_paper_obj = api_client.get_paper_by_title(paper.get("title", "").strip())
                    paper["ss_paper_obj"] = ss_paper_obj.to_dict() if ss_paper_obj else None
                except TransientS2Error:
                    paper["ss_paper_obj"] = None  # still unreachable -> leave unresolved
                if _progress:
                    _progress.report(i + 1, len(transient_failures))

        # Save enriched data back to original file
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Enrich cited papers with Semantic Scholar data - single submission mode only"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        required=True,
        help="Data directory containing submission data"
    )
    parser.add_argument(
        "--submission-id",
        type=str,
        required=True,
        help="Submission ID to process"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="Semantic Scholar API key (or set SEMANTIC_SCHOLAR_API_KEY env var)"
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=1.1,
        help="Rate limit delay in seconds between requests (S2 limit is 1 req/sec; stay above 1.0)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose logging"
    )
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Process single submission
    logger.info(f"Processing submission {args.submission_id}")
    logger.info(f"API key: {args.api_key}")
    success = process_for_pipeline(
        data_dir=args.data_dir,
        submission_id=args.submission_id,
        api_key=args.api_key,
        rate_limit_delay=args.rate_limit
    )
    
    if success:
        logger.info(f"✅ Successfully enriched submission {args.submission_id}")
        print(f"✅ Successfully processed submission {args.submission_id}")
    else:
        logger.error(f"❌ Failed to enrich submission {args.submission_id}")
        print(f"❌ Failed to process submission {args.submission_id}")
