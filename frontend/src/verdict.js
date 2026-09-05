// Reader-facing wording for the overlap and verdict vocabulary.
//
// The DECISIONS -- whether a comparison counts as overlapping prior work, and in which
// order overlaps are shown -- are not made here. They come from the backend as
// `is_overlap` and `overlap_rank`, computed in src/novelty_assessment/verdict.py, because
// a rule restated in two languages is a rule that will eventually disagree with itself.
// What is left here is presentation: the words and the badge colours.

export const DEGREE_LABEL = {
  same: 'same contribution', substantial: 'substantial overlap', partial: 'partial overlap',
  superficial: 'no overlap', none: 'no overlap',
}

export const degreeLabel = (deg) => DEGREE_LABEL[deg] || deg

// Artifact B's per-claim verdict. `uncertain` exists in the schema but the agent never
// emits it today; it is rendered anyway so an old artifact does not fall through blank.
export const VERDICT = {
  challenged: { label: 'challenged by prior work', cls: 'low' },
  not_challenged: { label: 'not challenged in the examined literature', cls: 'mid' },
  uncertain: { label: 'uncertain', cls: 'mid' },
}
