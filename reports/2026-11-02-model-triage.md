# Model triage spike (P0d), 2026-10-28 to 2026-11-02

The set ran under the rule fixed by the tag `p0d-prereg` (commit `4091e70`, tag object `2f451f2`), timestamped in Bitcoin blocks 973830, 973864 and 973887. The plan is `docs/plans/P0d-model-triage.md`.

## Outcome

**Fail under the registered rule (D-171),** because (ii) was not graded as registered. The rule says the founder grades every report blind. The founder graded no report. 32 of the 53 reports were graded only by an AI draft that no person read, and the other 21 take their grades from an outside reader who used a tool. The key is now open, so blind founder grading can't be redone.

Claude's numbers are reported beside the outcome. This record makes no claim that the models cannot do this work.

Gemini also falls short on (i), and that result mostly measures failed calls.

| Criterion | Threshold | Claude (`claude-opus-5-5`, plan) | Gemini (`gemini-4-argon`, API) |
|---|---|---|---|
| (i) accuracy over 29 | at least 27 | 29 | **24, below** |
| (i) canaries correct | 5 of 5 | 5 | **1, below** |
| (ii) fileable of 29, not graded as registered | at least 21 | 21, on the outside reader's strict readings; 21 to 29 across the sets | 23 under every set |
| (iii) median per case | under 10 minutes | 24.5 s | 46.4 s |
| (iii) budget | see the plan | no limit hit; effect on the founder's own plan use not stated | 3.40 USD for the set; 3.81 USD booked of 8 |

Secondary row, with each of the 16 distinct input and output pairs counted correct only if every case in it was correct: Claude 16, Gemini 11. It decides nothing.

### (i) in detail

- Gemini's 5 wrong answers are its 5 calls that ended at `MAX_TOKENS` with no reply: cases 02, 06, 09, 16 and 24. Four of them are canaries. It got every case it answered right, 24 of 24. Its canary score of 1 of 5 therefore mostly shows the failed calls, not its judgement of those canaries. Under the rule a failed call scores wrong, with no retry.
- **The duplicate rule carries the score.** 28 of Claude's 29 answers and 23 of Gemini's 24 name #16974, not #16864. The rule counting #16974 as #16864 was fixed before the tag, and the trial prompted it. Upstream did close #16974 as a duplicate of #16864, but the frozen texts the models saw hold no comments, so they could not see that.

### (ii) in rows

A call with no reply scores unfileable, so the denominator stays 29. The rule says 58 reports; 53 exist.

| Row | Claude | Gemini | Reaches 21 of 29? |
|---|---|---|---|
| (a) Result | 21 of 29 | 23 of 29 | Both, Claude exactly |
| (b) Claude without the 5 cases that Gemini left unanswered | 18 of 24 | n/a | No, 18 is below 21; as a share, 75% against the 70% line |
| (c) All three readings A | 29 of 29 | 23 of 29 | Both |
| (d) The 21 outside-reader reports alone | 7 of 15 | 6 of 6 | Too few reports to reach it; 47% and 100% |
| AI-draft reports alone | 14 of 14 | 17 of 18 | Too few reports to reach it |

- **Claude's (ii) depends on the outside reader's strict readings.** Its 21 is 7 outside-reader reports and 14 AI-draft reports. No person read those 14.
- **The founder does not adopt these readings as their own,** because the key is open and doing so would not be blind.
- **All 8 reports that turn on the readings are Claude's**: R09, R11, R23, R35, R39, R43, R47 and R48. They concern a sign slip in a gloss of the dropped term, a claim of non-equivalence where the report's own checker prints True, and R09's extra rotation.
- The AI draft's one failure is R01, a digit slip in a stated output (Gemini).
- Canaries fileable: Claude 4 of 5, Gemini 1 of 5.

### (ii) across the five grade sets

Each set grades the same 21 reports, with the AI draft's grades kept on the other 32. Gemini is 23 of 29 under all five.

| Set | Claude | Agrees with locked grades (of 21) |
|---|---|---|
| A | 29 | 13 |
| B | 29 | 13 |
| C | 26 | 16 |
| D, the outside reader (locked) | 21 | 21 |
| E, received after the lock | 28 | 14 |
| Majority of the five | 28 | n/a |

Set D alone fails R23, R35, R39, R43 and R48, the sign-slip reports. R09 fails under C, D and E; R11 and R47 fail under C and D. The other 13 reports are unanimous.

Set E was saved at 18:04 local time, after the grades were locked at 17:54 and the scores were written at 17:58. It changes no grade and is a sensitivity row only.

These sets are not independent checks. They read the same page, with the same facts boxes and the same framing of the reading questions. They also leave the 32 AI-draft grades untested, 14 of which are Claude's fileable reports.

## Departures from the registered grading

1. **OD-BN 1.** The founder asked for an expert AI draft in place of grading alone. The plan became: the founder settles 13 flagged reports and 8 drawn at random, checked against the draft.
2. **OD-BO 1.** The founder then asked for a second AI from another provider to grade the 21, replacing the random check. Any 8 or more disagreements of 21 would send grading back to the founder. So the planned founder agreement measure was dropped.
3. **OD-BP 1.** Sets A to D were compared with the draft. 8 of 21 disagreed, which reached the reversal line. The line is recorded as reached, and no further grading followed.
4. **Set D's authorship, corrected.** Set D was first reported as the founder's own, and the three readings were recorded on that basis. The founder has since stated that a friend made it. `grades.json` stays as locked, so its 21 entries still carry the source `founder`; this record calls them "outside reader". The reader is not named.
5. **AI draft.** The other 32 entries carry the source `ai-draft` (Sonnet 5.5) and were not seen by a person.
6. **Same family.** A Claude model drafted the grades on reports that are partly Claude's, and also wrote the facts boxes on the review page. Those boxes used no verdict words, but they frame what a reader looks at. The canaries were also built by a Claude model and approved by the founder.
7. **Private text left the lab.** The founder uploaded the review page, which held private case text, to outside AI provider(s). The outside reader also saw case text. The plan kept that text private until this record.

### The outside reader and the founder's answers

The founder has answered the first question. The others are recorded as not stated, not as unknown.

| Question | Answer |
|---|---|
| The reader graded by hand or used an AI | Used a tool, as the founder reports; which tool, and whether it was an AI, is not stated |
| The reader saw the other sets, the AI draft or any readings first | Not stated |
| The reader was told which family wrote what, or discussed reports with anyone | Not stated |
| The reader's background in Qiskit or quantum circuits | Not stated |
| The founder's time spent grading | Not stated; no report was graded by the founder |
| Claude's run blocked the founder's own plan use | Not stated |
| Models behind sets A, B, C and E | Not stated |
| The founder noticed the lone-input pattern | Not stated |

Set D's file has the same four fields as the model sets, including an `uncertain` field that is not on the review page. Because a tool was used, set D cannot be counted as a person's independent judgement, and how much of it was the reader's own is not stated.

## Limits on blinding

- **Lone pairs.** Each of the 5 no-reply cases has a unique input and output pair, so the pack shows those 5 pairs with one report each. Anyone comparing pairs could tell that report came from Claude. Row (b) is the sensitivity for this. The founder was told of it after the grades were locked.
- **Family plumbing was shown to the founder before grading.** That includes completed cases, failed calls, tokens, cost and median times per family, and that Gemini could no longer reach (i).
- Writing style may hint at the family.
- Row (d)'s reports were not a blind sample of the 53: 13 were flagged by the draft and 8 were drawn at random.

## The mechanical pass

All 53 reproducers ran and showed a difference, so **the pass removed nothing**. Every report had the state "ran". These choices were made after the tag and before any report ran:

- An AssertionError counts as running. A report is unfileable only if it has no Python block, fails or times out, or every transpile call it makes is equivalent to its input. A case the check could not settle goes to the grader.
- The check uses `rtol=0, atol=1e-9`. On controls, `Operator.equiv`'s default called 3 of 31 given inputs equivalent at distances up to 1e-5. The tighter check can only send more reports on, so it failed nothing.
- It ran on Qiskit 2.5.2 in a container with no network. The base image, `python:3.13-slim`, was not pinned by digest. The built image id is `8e38f66a60b5`.

A reproducer can only show the #16864 part of a canary, because the planted fault is not in Qiskit.

## Correction: Linux and Windows

The pack said the outputs differ on one input. The review page said 6 of 16. Neither holds.

Running the same pipeline on both platforms gives different output on **3 of the 14 distinct inputs**: case-02 and the inputs of canaries C1 and C2. On T1, T2 and T3 the two platforms agree. Their given outputs differ because the fault was planted there. The draft and the review page attributed those differences to the platform, and at least one grade note (R23) repeats that. Readers were told to judge against the given output, but readers of those three canaries were given a wrong explanation of why the printout differed.

Exact text never matched the given output on either platform (0 of 31), so this compares the platforms with each other. The cause of the text mismatch has not been checked.

## Run plumbing

| | Claude | Gemini |
|---|---|---|
| Cases called once | 29 of 29 | 29 of 29 |
| Reports | 29 | 24 |
| Failed calls | 0 | 5, `MAX_TOKENS` |
| Provider refusals | 0 | 2, Google's spend cap (cases 17 and 27) |
| Output tokens | 115,891 | 272,983 |
| Input tokens | 70, plus 3,069,071 cache read and 120,431 cache write | 2,038,990, plus 1,793,887 cache read |
| Median and maximum per case | 24.5 s, 172.4 s | 46.4 s, 342.0 s |
| Total call time | 1,117 s | 2,941 s |
| Cost | 3.90 USD API equivalent, on the plan | 3.40 USD |

Total booked API spend is 3.81 USD of 8, which adds 0.41 USD for the trials and the final check.

- Google's cap stopped Gemini twice. It resumed each time with the remaining cases only, in a new folder. Both refusal records were moved aside with a log line, as provider refusals rather than model results.
- During the Gemini run, a separate AI session managing the project read call metadata only and told the founder that 4 calls had ended at `MAX_TOKENS` and that Gemini could no longer reach (i). A fifth followed.
- The tagged adapter is dry-path only, so Claude's calls ran through a private runner using the tagged adapter's functions, one call per case. The CLI adds 1,774 characters (0.8%) around the fixed prompt.
- Two trial attempts on 2026-10-28 ran without keys; no request reached a provider, and the spend was 0.

## Founder effort

No report was graded by the founder. The time spent is not stated, so the plan's estimate of 3 to 5 hours is not replaced by a measurement.

## Where each number comes from

The files are private. Their hashes fix what this record read.

| Numbers | File | sha256 |
|---|---|---|
| (i), (ii) rows, (iii), pairs | `scores.json` | `0cd0131ea5864081235940a393ff384ef16fd2c7362673c38838613a08066c6d` |
| Grades and their sources | `grades.json` | `c53d1534bf898fdc15a0a68e9e6a024d744f3aa651c4104949964efe61b93c82` |
| Report key | `sealed-map.json` | `450698a79b43f86832db897fcb629d56f04dd962b2ea95912c0d2a7fb2be251f` on disk (CRLF); `1ed6f771dd6b3ec67da94cc230ee138f3a4a5bac7855f79c397595de1bb1de00` with LF, the form logged before grading |
| Mechanical pass | `mechanical-results.json` | `b71eca9f81851ffcac2847f1f4c0432a4b61b8e06908f014c6ea001558b32400` |
| Blind pack | `pack.html` | `f5225ae6ba0074a1f96ed2aa9299af90ca8a3b8f263acffc2622ec082525c4be` |
| Review page | `review.html` | `7c17d4a33bc8ee88a65623822c28fb901e97f89a48313d48b27ab35effedd11a` |
| AI draft | `draft-grades.json` | `e2767636f3e39a62dc7a82c242c5299b4562f9793abe6d118fd07050a370db4e` |
| Set A | `second-model-A.json` | `5afb9920d809c129108fd390d67300db9602de1398d6a2cc62cf5695d0cbdd65` |
| Set B | `second-model-B.json` | `c07d0aa835091651560e1cb42ca3618b347bb6016ee02652749f5da5714f5ac5` |
| Set C | `second-model-C.json` | `59c22044a9701373fb6d24e9f78bec4dd90c2c972de2e0f00be1bcda5e6084ed` |
| Set D | `second-model-D.json` (the name predates the correction above) | `53d42fa438a7a1946d2aae0d037ebb4648e953f8fe8f88eb4e8db5143dd3d842` |
| Set E | `second-model-E.json` | `8e74a4f6ce9d3e1826580ddd2afeca51d69204dd9cf97bed0cdfd86bf49e7cb5` |

Reports, canaries and case-to-circuit mappings stay private until the founder decides to publish them.

## Decision

Fail under the registered rule, by the founder (D-171). No upstream filing follows from this spike's model output (D-157).
