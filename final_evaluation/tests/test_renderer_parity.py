"""The two report renderers must agree about the same document.

The pipeline's Summary tab and the study dashboard are independent Vite apps, so the
dashboard copies the renderer rather than importing it (see ReportRenderer.jsx's header).
Copies drift. The rules that decide what a reader actually concludes from the page -- which
overlap degree is shown as "strong", whether a missing evidence check is drawn as a secured
result, where an assessment's jump link lands -- are therefore kept in ONE file per app,
`components/assessmentStyle.js`, and those two files must be byte-identical. If they are
not, the same frozen report can be coloured one way in the pipeline and another way in the
study, which would be a presentation difference nobody declared.

The colour block in the two stylesheets is checked the same way, for the same reason: the
classes mean nothing without it.

    python -m pytest final_evaluation/tests/test_renderer_parity.py
"""
import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
APP = REPO / "frontend" / "src"
DASH = REPO / "final_evaluation" / "dashboard" / "frontend" / "src"

SHARED = "components/assessmentStyle.js"
# The colour block, delimited in both stylesheets by these two sentinel comments.
CSS_START = "/* --- assessment colour + the blocks of one comparison"
CSS_END = "/* --- end of the shared assessment block"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def test_shared_assessment_module_is_identical():
    a = (APP / SHARED).read_text(encoding="utf-8")
    b = (DASH / SHARED).read_text(encoding="utf-8")
    assert _sha(a) == _sha(b), (
        f"{SHARED} differs between the two apps ({_sha(a)} vs {_sha(b)}). "
        "Copy the intended version over the other; do not edit one app only."
    )


def test_assessment_colour_block_is_identical():
    blocks = []
    for root in (APP, DASH):
        css = (root / "styles.css").read_text(encoding="utf-8")
        assert CSS_START in css and CSS_END in css, (
            f"{root / 'styles.css'} lost the assessment colour block or its sentinels")
        blocks.append(css[css.index(CSS_START):css.index(CSS_END)])
    assert _sha(blocks[0]) == _sha(blocks[1]), (
        "the assessment colour block differs between the two stylesheets "
        f"({_sha(blocks[0])} vs {_sha(blocks[1])})"
    )


def test_every_class_the_module_emits_has_a_rule():
    """A class the renderers can emit but no stylesheet styles is an invisible state."""
    js = (APP / SHARED).read_text(encoding="utf-8")
    kinds = {
        "as-" + k for k in ("same", "substantial", "partial", "weak", "unknown", "strong")
    } | {
        "vd-" + k for k in ("challenged", "unchallenged", "uncertain")
    } | {
        "ev-" + k for k in ("material", "nonmaterial", "insufficient", "nocheck")
    }
    # The names really are the ones the module derives, not a second list to maintain.
    for name in ("same", "substantial", "partial", "weak", "unknown"):
        assert f"'{name}'" in js, f"assessmentStyle.js no longer emits as-{name}"
    css = (APP / "styles.css").read_text(encoding="utf-8")
    styled = {c for c in kinds if f".{c}" in css}
    # `as-strong`, `as-unknown` and `ev-material` inherit the defaults on `.as` on purpose:
    # "strong" is carried by the degree tint, and a solid outline IS the default.
    inherits_default = {"as-strong", "as-unknown", "ev-material"}
    missing = kinds - styled - inherits_default
    assert not missing, f"classes with no rule in frontend/src/styles.css: {sorted(missing)}"
