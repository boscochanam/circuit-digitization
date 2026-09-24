# Individual reviewer verification, 15 September 2026

Base: origin/main at 1d64fe86f2910cce9332211e0a54b17597039b57.
Scope: issues #96 (R1-6), #97 (R2-1), #102 (R2-6).
These are source/evidence verdicts, not final PDF approval or new experiments.

## #96 / R1-6: verified after local bibliography corrections

Both requested works are cited in Related Work, paper-access.tex:101 and
paper-build.tex:77. They are application context; no benchmark or comparison
claim was changed. Both bibliography entries are synchronized.

Publisher-deposited Crossref records checked on 15 September 2026:
- https://api.crossref.org/works/10.1109/TCE.2026.3663359
- https://api.crossref.org/works/10.1109/TII.2026.3668794

Exact changes (the accompanying Git diff supplies complete before/after lines):
- paper-access.tex:428 and paper-build.tex:405: five named authors followed by
  'et al.' changed to first author plus 'et al.' for the eight-author work;
  year-only publication detail changed to vol. 72, no. 2, pp. 3213--3224,
  May 2026. Title and DOI unchanged.
- paper-access.tex:429 and paper-build.tex:406: seven named authors changed to
  first author plus 'et al.'; added no. 6 and Jun. to the existing vol. 22,
  pp. 4801--4812, 2026. Title and DOI unchanged.
- RESPONSE_TO_REVIEWERS.md:71: replaced the first reference's Feb 2026 shorthand
  with final issue metadata and expanded the second reference's issue metadata.
  The final issue dates are May and June; they are not early-access dates.

Source formatting uses numbered bibitems, sentence-case article titles,
abbreviated italic journal titles, volume/issue/pages/date, and DOI.
Rendered reference appearance remains part of shared build issue #86.

## #97 / R2-1: verified, no manuscript edit needed

paper-access.tex:379 (Discussion) explicitly includes all four sampling
dimensions: component count, drafter, crossing/bus structure, capture conditions.
It specifies independent annotation followed by adjudication, per-image effort
and provenance logs, and identifies the protocol as future work. One annotator
and absent historical timing logs are disclosed; no historical hours or target
sample count is invented. Abstract (:62), real evaluation (:240), and Conclusion
(:405) restrict the evidence to 31 images from one corpus. Equivalent clauses
are present in paper-build.tex and the R2-1 response.

Stored evidence in docs/research/experiments/bootstrap_ci_n31.json:
- join/scale_completion.micro: point 0.8903088391906283;
  lo 0.8547155162311028; hi 0.9239503010306861.
  Matches 0.890 and [0.855, 0.924] at paper-access.tex:242.
- VLM_minus_ours_micro: point 0.03276808388629482;
  lo -0.009184500410865945; hi 0.07809612609512304.
  Matches +0.033 and [-0.009, +0.078] at :370. The prose explicitly says
  inclusion of zero does not establish equivalence.

This verifies the requested disclosure and scoped conclusions. It does not
establish broader generalization or recover unrecorded annotation costs.

## #102 / R2-6: verified, no manuscript edit needed

paper-access.tex:130 states one scalar per image, the large-IC/small-discrete
example, fixed clamps, and absence of controlled rescaling. Completion's retained
scale dependence appears at :147; the sweep and ablation boundaries at :242,
:245 and :264. Equivalent clauses appear in paper-build.tex and the R2-6 response.

Implementation checks:
- wire_detection/core/join_graph.py:55 estimate_scale uses the middle sorted
  component diagonal, with fallback; :117-122 applies fixed pixel clamps.
- wire_detection/core/completion.py:94 _scale_tau uses the same scalar and
  min(60,max(24,0.62*s)); :137-138 scales completion reach by this value.
- wire_detection/core/join_strategies.py:370 sets completion reach_factor=4.0.

Stored docs/research/experiments/join_reach_sweep_n31.json gives macro F1
0.8954648168964782 to 0.9032210952911355 for relaxed-witness reach factors
3.0 through 5.0, matching 0.895--0.903. The fixed-pixel ablation changes only
base tolerances; completion retains scaling. The existing ablation artifact
reports base 0.816 versus 0.820 and full-pipeline ties at 418/37/66.
The manuscript does not infer identical connections, dispensability, or
mixed-size robustness from these aggregate ties.

## Handoff

All three individual source checks pass after the local #96 correction.
No GitHub verdict has been posted and no issue has been closed by this check.
Existing PDFs predate the bibliography update; final pagination, highlighted
copy, and rendered-page approval remain in shared issue #86.
