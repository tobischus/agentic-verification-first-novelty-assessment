// Reader-facing wording for overlap degrees and verdicts.
export const DEGREE_LABEL = {
  same: 'same contribution',
  substantial: 'substantial overlap',
  partial: 'partial overlap',
  superficial: 'no overlap',
  none: 'no overlap',
}

export const degreeLabel = (deg) => DEGREE_LABEL[deg] || deg

export const VERDICT = {
  challenged: { label: 'challenged by prior work', cls: 'low' },
  not_challenged: { label: 'not challenged in the examined literature', cls: 'mid' },
  uncertain: { label: 'uncertain', cls: 'mid' },
}
