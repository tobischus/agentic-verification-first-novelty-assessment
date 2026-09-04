#!/usr/bin/env python3
"""
Put every system's assessment into one neutral wrapper for blind rating.

What this does and does NOT do is the whole point. It normalises the CONTAINER: one title,
one preamble, one set of conventions, no system names, no logos, no URLs that give a system
away. It does not touch the CONTENT: nothing is summarised, shortened, reordered or
rewritten, and no section is dropped. A system that writes more still writes more. Editing
for length would hide a real property of the systems and would make the rating measure this
script instead of them.

Blinding is partial and has to be reported as such. Structure, voice and length still
identify a system to anyone familiar with them, and the two variants of the same pipeline
are recognisably related. What the wrapper removes is the trivial giveaways.

Length is a known confound -- the outputs for one paper span 748 to 17k words -- so the key
file records the word count of each. Report it beside the ratings rather than pretending it
away.

Usage
-----
  python eval/normalize_battle.py --paper transducing_language_models
  python eval/normalize_battle.py --paper ID --in-dir comparison/outputs \
      --out-dir comparison/normalized
"""
import argparse
import json
import random
import re
from pathlib import Path

# Suffix in comparison/outputs -> the system it came from. The label is written only to the
# key file, never into a rated document.
SYSTEMS = {
    "agentic": "own agentic pipeline",
    "linear": "own linear baseline",
    "afzal": "Afzal et al.",
    "opennovelty": "OpenNovelty",
    "deepreviewer": "DeepReviewer 2.0",
}

# Trivial giveaways: names, hosts, contacts and the headings a system is known by. Applied
# case-insensitively. Anything not matched here stays exactly as written.
_REDACT = [
    (r"https?://\S*opennovelty\S*", ""),
    (r"https?://(?:www\.)?deepscientist\S*", ""),
    (r"\bOpenNovelty\b", "this system"),
    (r"\bWisPaper\b", "a scholarly search engine"),
    (r"\bDeepReviewer(?:\s*2\.0)?\b", "this system"),
    (r"\bAfzal et al\.?(?:'s)?\s*(?:pipeline)?", "this system"),
    (r"[\w.+-]+@[\w-]+\.[\w.]+", "[contact removed]"),
    # headings a reader would recognise instantly
    (r"^#+\s*Novelty Assessment Report\s*$", ""),
    (r"^#+\s*Final Review Report\s*$", ""),
    (r"^#+\s*NOVELTY DELTA ANALYSIS FOR REVIEWER SUPPORT\s*$", ""),
    (r"^#\s*Novelty Assessment\s*\(.*?\)\s*$", ""),
    (r"^#\s*Novelty Assessment\s*$", ""),
]

_PREAMBLE = """> This is one system's assessment of the paper's novelty. Several systems assessed the
> same paper; they are presented in a common wrapper so that presentation does not decide
> the comparison. The text below is each system's own, unedited and complete: it was not
> shortened, reordered or rewritten, so the systems differ in length and structure.
>
> Where a system marks verbatim quotations, they appear in quotation marks; unmarked text
> is that system's own prose.
"""


def _redact(text: str) -> str:
    for pattern, repl in _REDACT:
        text = re.sub(pattern, repl, text, flags=re.I | re.M)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def normalize(paper: str, in_dir: str, out_dir: str, seed: int | None = None) -> dict:
    src = Path(in_dir)
    dst = Path(out_dir) / paper
    dst.mkdir(parents=True, exist_ok=True)

    found = []
    for suffix, label in SYSTEMS.items():
        f = src / f"{paper}__{suffix}.md"
        if f.exists():
            found.append((suffix, label, f))
    if not found:
        raise FileNotFoundError(f"no outputs for {paper} in {src}")

    # Deterministic per paper so a re-run keeps the same letters -- ratings collected under
    # one assignment must not silently point at different systems later.
    rng = random.Random(seed if seed is not None else paper)
    letters = [chr(ord("A") + i) for i in range(len(found))]
    rng.shuffle(letters)

    key = {"paper": paper, "assignment": {}, "note": "do not open before rating is complete"}
    for letter, (suffix, label, f) in zip(letters, found):
        body = _redact(f.read_text(encoding="utf-8"))
        doc = f"# Assessment {letter}\n\n{_PREAMBLE}\n---\n\n{body}\n"
        (dst / f"{letter}.md").write_text(doc, encoding="utf-8")
        key["assignment"][letter] = {"system": label, "source": f.name,
                                     "words": len(body.split())}
    (dst / "key.json").write_text(json.dumps(key, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
    return key


def main():
    ap = argparse.ArgumentParser(description="Neutral wrapper for blind rating")
    ap.add_argument("--paper", required=True)
    ap.add_argument("--in-dir", default="comparison/outputs")
    ap.add_argument("--out-dir", default="comparison/normalized")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()
    key = normalize(args.paper, args.in_dir, args.out_dir, args.seed)
    print(f"{args.paper}: {len(key['assignment'])} assessments -> {args.out_dir}/{args.paper}/")
    for letter, meta in sorted(key["assignment"].items()):
        print(f"  {letter}.md  {meta['words']:>6} words")
    print("key.json written (system labels are only in there)")


if __name__ == "__main__":
    main()
