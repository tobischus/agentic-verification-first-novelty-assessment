<!--
instructions_version: human_instructions_v2
Base text is verbatim from the task (Section 8, page 2 "Einweisung und Teilnahme").
v2 (2026-09-15) makes exactly two changes requested after the first dashboard review,
and nothing else:
  - the sentence "Do not favor matching terminology, particular report formats, longer
    or shorter reports, more positive judgments, or more negative judgments." is
    replaced by the "Do not prefer terminology, format, length ..." sentence below;
  - the sentence "Verification labels are system claims, not independent validation."
    is added.
Every other sentence is unchanged from v1. Rendered as-is on the Instructions page; the
hash of THIS file's body is recorded at consent time (see
dashboard/backend/models.py: Participant.consent_instructions_sha256), so a participant
who consented to v1 keeps a consent record pointing at v1's hash, not this one.
-->

You will compare two reports about the same scientific submission. Evaluate how well
they support a reviewer in assessing novelty. You receive the submission and both
reports, but not the original prior-work papers, expert reference reviews, internal
traces, or automated judgments. Check descriptions of the submission against the
submission. Evaluate statements about prior work only as supported by the displayed
material; you cannot independently authenticate unavailable sources. The submission's
own novelty claims are not ground truth. Verification labels are system claims, not
independent validation.

Evaluate each criterion separately. Do not prefer terminology, format, length, or
positive or negative judgments by themselves. Consider clarity and effort when assessing
reviewer usefulness. Read both reports and consult the submission before deciding. Work
independently, without external research or AI assistance. Do not discuss study cases
until ratings have been submitted.

Choose Tie when the reports are comparable on a criterion, including equally weak.
Choose Unclear when you cannot form a defensible preference. Report technical problems
separately. You can pause and resume. Your responses are stored under a participant ID;
the study organizer can associate that ID with you. No participant names are shown to
other participants.
