# E3: source audit

`source_audit.py` (`python -m final_evaluation.cli source-audit`) re-checks every quote an
agent or linear report shows against the hash-pinned source text it was verified
against. It also checks the 90-day gap between each pinned prior-work version and the
submission. It needs no model.

`opennovelty_audit.py` locates the quotes of the OpenNovelty reports in the cited papers
and checks whether these papers precede the submission.
