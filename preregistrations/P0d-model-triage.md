# P0d Model triage spike plan

This plan is the lab's first measured test of its central bet: that AI members do useful research work. It gives two model families the audit's real triage work, the slowest step in its pipeline, and compares them with the confirmed labels under a rule fixed before the run. It runs as plain scripts beside the platform, like P0 Task 7, before P2 restarts.

Status: draft

**Goal.** Measure whether models from two families, given the audit's reduced reproducers, can tell a known upstream issue from a new one, explain the likely cause, and draft a report a maintainer would accept, accurately enough and fast enough to shorten the time from a run to a filed finding.

**Why now.** No AI member has run yet; the earliest planned test was pilot week 6, after P2 to P4 (D-089). Meanwhile the audit's slowest step was not compute or checking but the human work after a witness: deciding whether a case is new, finding its cause, and writing it up. The audit's final ledger holds 1,472 cases, 172 of them with a witnessed difference (D-155), so the test needs no new data. A negative answer here is cheap, and it would change what P2 should build.

**Estimate.** 3 to 5 founder hours (assumption, replaced by measurement): confirming the labels, approving the canaries, grading blind. API spend is capped at $8 across all API families (D-163).

**Not in scope.** No record, no committer, no runner, no member profiles. Nothing is filed upstream from model output without the founder's approval. The models see only circuits, tool names and versions, and public issue texts. They never see the labels, the ledger or any private file.

## The cases (frozen by the tag `p0d-prereg`)

The cases, labels, canaries and the mapping of neutral names to ids stay private until the record (D-157 rule 5). This plan states the rules; `spikes/qopt_triage/hashes.json` fixes the content.

- **Labels first.** The founder confirmed the label of every witnessed case on 2026-10-28. A label has two fields: `status` and `issue` (a known issue id, `new`, or unresolved). Criterion (i) is scored on `issue`. Records that disagreed with each other were settled at this step; the record lists each one. Totals: 168 #16864, 2 #17315, 2 unresolved, and the unresolved cases stay out of the set.
- **The set.** 24 real cases: one for each distinct reduced signature, then 20 more drawn from the rest, with `random.Random(int("d6d2b83", 16))` over sorted ids. 23 are #16864 and 1 is #17315. Two further cases from the same draw, outside the set, check the harness. The models see each case under a neutral name, `case-01` to `case-29`, in an order shuffled with the same seed.
- **Canaries.** Five planted faults, each inside a case that already shows #16864, so a known issue explains part of the difference and the planted fault the rest. The founder approved each one. QCEC proves each edit not equivalent to the clean output and to the input with only #16864's effect applied. Each fault is at least 25,000 times Qiskit's measured tolerance of 1e-05. An earlier set was replaced before the trial because a trivial rule scored 28 of 29 against it.
- **Canary labels and scoring.** Every canary is labelled `Qiskit/qiskit#16864 + new`. An answer of `new` or `Qiskit/qiskit#16864 + new` scores correct, and `Qiskit/qiskit#16864` alone scores wrong. A canary's draft report must describe the planted fault to count under (ii).
- **Issue texts.** One fixed search: Qiskit/qiskit issues labelled `bug`, created 2026-08-01 to 2026-10-27, in any state. It returns 68 issues. They were captured once, at 2026-10-28T11:51:38Z, with number, title, body, state and creation date and no comments. Every model gets the same texts.
- **Distinct pairs.** The set is kept as drawn. The 29 cases hold 16 distinct input/output pairs and 14 distinct inputs, because many real cases reduce to the same small circuit. The record reports a secondary row: accuracy over the 16 pairs, each counted once. It decides nothing.
- **Trial overlap.** The two trial cases are one input/output pair asked twice. Two set cases share that input but not its output; the record names them. Claude's and Gemini's answers on the trial pair have been seen, and their answers on those two cases have not.

## What each model does, per case

Given the reduced input, the tool's output for it, the tool and version, and the frozen issue texts:

1. **Known or new.** Name the matching issue, answer "new", or name an issue and "new" together.
2. **Cause.** One short paragraph on the likely cause, naming a pass or function where it can.
3. **Draft report.** An issue text in the tool's usual form: the reproducer, expected and actual output, and versions. It states as fact only what was given about the case, and writes "not given" for anything else. The trial prompted this line, and it ran on the earlier prompt, so the line's effect is unmeasured.

**Routes (D-163).** Claude: `claude-opus-5-5`, effort high, on the founder's plan through the official CLI, one call per case in a throwaway container holding only the case packet, with every tool disabled. Gemini: `gemini-4-argon`, thinking level high, on its API.

**The routes are not identical.** Both get the same prompt, issue texts and case. The CLI adds 1,774 characters (0.8%), including the platform and date, as measured against a local stub. Claude's reply format is enforced by a schema tool, Gemini's is checked afterwards. Claude's output limit is 128,000, Gemini's 32,000. Claude's cache is explicit, Gemini's implicit. Token counts differ by about 26,000 on the same text, at least 93% of it tokenizer. The record states all of this.

## The rule (fixed before the run)

Thresholds set by the founder on 2026-10-30.

- **Pass** when at least one model family meets all three:
  - (i) known-or-new accuracy of at least 90% over the 29 (at least 27 correct), with every canary scored correct;
  - (ii) at least 70% of its draft reports (at least 21 of 29) fileable, graded blind by the founder, on facts only;
  - (iii) a median of under 10 minutes of wall-clock time per case; on an API route, inside the $8 cap; on a subscription route, inside the plan's usage window without blocking the founder's own use.
- **Fail** otherwise.

**Fileable (ii).** All 58 reports are shuffled under neutral names, with model, route and label hidden. A script first runs each reproducer against Qiskit 2.5.2; one that fails to run or shows no difference is unfileable. The founder grades the rest. A report is fileable when the reproducer works, the expected and actual outputs are right, it describes every difference, and its versions are right: Qiskit 2.5.2 is required, "not given" is correct for anything else, and an unsupported Python or operating-system claim is a wrong fact. Canaries count inside the 70%, with no separate floor. Wording is not graded.

**Duplicates (i).** An issue that upstream closed as a duplicate of a labelled issue counts as that issue. All 68 captured issues were read on 2026-10-30T12:40:50Z. One qualifies: Qiskit/qiskit#16974, closed 2026-09-10 as a duplicate of Qiskit/qiskit#16864. None qualifies for #17315. The list is frozen in `spikes/qopt_triage/duplicates.json` and does not change with later upstream activity. On a canary, `#16974 + new` scores as `#16864 + new`, and `#16974` alone is wrong. The trial prompted this rule: Claude and Gemini answered `#16974` where the label is `#16864`, a pass trace confirmed the label, and upstream's closure was found. The frozen texts hold no comments, so the models cannot see the closure. The cause and report are still graded separately under (ii).

**Against a trivial strategy.** "#16864 if the input has an angle below 1e-3, else new" scores 23 of 29 (79.3%) and gets no canary right. The other trivial strategies tried score 5 of 29.

**Reported, not thresholded.** Founder minutes per case, cost per correct answer, and refusals.

**What follows.** Neither outcome changes a plan by itself; the founder decides.
- **Pass** is evidence that triage roles are worth the P2 runner. P2's first batch should then put one such role to work.
- **Fail** is evidence that, for this work, the scripts plus the founder are the right shape. The member design is reconsidered before P2 restarts.

## Set-run rules (fixed before any result is seen)

1. Each family runs each of the 29 cases once, in neutral-name order. No retries, no reruns, no replacing a case.
2. A cache miss changes nothing: the run continues and the cost is reported as it falls.
3. The $8 cap is not raised during the run. Cases not reached score wrong under (i) and (ii) for that family, and the record says where it stopped.
4. A failed call scores wrong and is booked at its worst case. A provider refusal (401, 402, 403 or 429) is not a model result: that family stops, and the remaining cases resume once it is resolved.
5. An interrupted run resumes with the remaining cases only, to a new folder. Completed cases are never re-sent.
6. Gemini's prices hold until 2026-11-30, and the harness refuses the route after that date. The Gemini run starts by 2026-11-29. Later than that, the price is checked and the harness updated as a recorded change.

## Tasks

1. **Labels and set.** Settle the labels, draw the set, build the canaries for the founder's approval one at a time, capture the issue texts. Commit only the hashes.
2. **Prompt and harness.** One fixed prompt and a script that sends each case once to each model and stores the replies with their times and costs. Run it on two cases outside the set to check it works. The trial cap is $1, raised once to $1.60 for one Gemini rerun so that the corrected cost bound would not block its second call. One more call per family on the first trial case checks the final prompt and harness, for plumbing and the "not given" line only.
3. **Tag.** Tag `p0d-prereg` with the thresholds, the set hashes, the prompt, the harness, the adapter, the sandbox and the routes, and anchor the tag with a third-party timestamp.
4. **Run.** Each case once per model, under the rules above.
5. **Grade.** The founder grades the reports blind. A script scores (i) and (iii).
6. **Record.** A history record with every number, every failure and the cost, and the decision.

## What would reverse this

If the founder cannot confirm the labels without new triage work, the set is not ready and the spike waits. If the canaries are too easy (every model gets every canary and every known case right on the two trial cases), harder canaries are made before the tag. Making them is a recorded change, not a reason to skip the test.
