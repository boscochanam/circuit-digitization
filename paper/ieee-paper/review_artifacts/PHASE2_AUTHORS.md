# Phase 2(c): author-field discrepancy inventory

Source anchors are at `02da5e6`; A/B = paper-access.tex/paper-build.tex. All facts below are transcriptions or differences in existing files, not independent identity verification. No author, affiliation, ORCID, biography, funding, acknowledgment or publication metadata field was edited. `phase2_evidence/author_fields.json` records field hashes and equality against `8f4e18b`.

| Existing byline name | A ORCID at lines 45–50 (unverified transcription) | Bio present A / B |
|---|---|---|
| Bosco Chanam | 0009-0009-2527-0967 | 464 / 439 |
| Chris Dcosta | 0009-0007-7295-0573 | 468 / 443 |
| Pranavesh Kumar Talupuri | 0009-0005-8974-2012 | 472 / 447 |
| Shwetambari Chiwhane (A); Shwetambari A. Chiwhane (B byline) | 0000-0002-3534-9654 | 476 / 451; both bios omit the middle initial |
| Ashay Kumar Singh | 0009-0004-9105-7383 | 498 / 473 |
| Arghadeep Das | 0009-0000-9207-7694 | 502 / 477 |

All six are present in the same byline order (A:45–50, B:32). A has six active ORCID links; B has none, only the example comment at B:30–31. A's “add each author's ORCID” comment at :43–44 is stale relative to its populated links. Neither the presence of a link nor its format verifies ownership. No bios are missing; presence is not factual approval.

| Gap / discrepancy | Exact evidence | Required disposition |
|---|---|---|
| Middle initial | A:48 and both bio headings omit “A.”; B:32 and paper/AGENTS.md author list include it | **HUMAN-ONLY:** affected author and byline consent holders confirm the preferred publication name; no normalization guessed |
| ORCID ownership and template difference | A:45–50 populated; B:30–32 has comment only | **HUMAN-ONLY:** each author confirms their ID; **TEAM-DECISION:** keep B's template-specific absence or synchronize verified IDs after authorization |
| Affiliation/current employment scope | A:51/B:33 put Bosco with SIT; A:465/B:440 bio says currently at Bharat Forge's AI Incubation Centre | **HUMAN-ONLY:** author confirms affiliation appropriate to the work and present-address treatment; these can coexist, so no false-affiliation conclusion |
| Other affiliation/contact facts | A:51–52,58; B:33–35: SIT and USC assignments, correspondence; A includes all emails while B lists only corresponding email | **HUMAN-ONLY:** confirm factual addresses/contact permissions; template difference alone is not a factual conflict |
| Funding declaration already populated | A:53 `This work received no external funding.`; B:36 identical text | **HUMAN-ONLY:** authors verify truth and required disclosures; do not treat the absence of a grant number as proof of no funding |
| Six bios and portraits already present | Table above; `figures/authors/*.jpg` | **HUMAN-ONLY:** confirm biographical facts, current positions, degree wording, numerical career claims and portrait permission; no missing degrees/history invented |
| Bio text synchronization | A:487 uses curly apostrophe in “Shwetambari’s”; B:462 straight apostrophe; other bio content matches | **TEAM-DECISION:** typography normalization after protected-field authorization; this is not a biographical fact difference |
| Bio grammar | A:480/B:455 “Engineering specializing from”; A:483/B:458 “She is life member”; A:492–493/B:467–468 “Presently” mid-sentence and “4 research scholar” | **HUMAN-ONLY:** approve protected bio editing and supply intended specialization if any; concrete grammar defects are inventoried, not repaired |
| Publication history placeholder | A:35 `Date of publication xxxx 00, 0000, date of current version xxxx 00, 0000.` | **HUMAN-ONLY:** accountable builder obtains template/editorial disposition; **TEAM-DECISION:** remove/omit as instructed by the actual template or retain publisher-populated placeholder if required; never invent dates |
| DOI template value | A:36 `10.1109/ACCESS.2024.0429000` | **HUMAN-ONLY:** confirm publisher/template disposition; this inventory supplies no evidence that it is this article's assigned DOI. Do not substitute a guessed identifier |
| Author approval assertion | A:411/B:387 acknowledgment says authors reviewed and take responsibility | **HUMAN-ONLY:** obtain actual approvals tied to final package hashes; the sentence is not a consent record |
| Response signer | R:23 `[Author signatory pending confirmation] et al.` | **HUMAN-ONLY:** Bosco designates/approves authorized signer; no signature or email sent |

A:35–36 publication metadata are explicitly included; B has no corresponding history/DOI fields. These are template/production disposition gaps, not a request for authors to create a DOI or publication date.

Inventory completion: PASS. Factual truth, consent, funding and final protected-field approval: unverified; remain HUMAN-ONLY. Scientific limitations are separately documented and are not cured by these approvals.
