# Quantum Escapement — Experiment 001 Review Contract v1.0

**Status: BINDING ACCEPTANCE CRITERIA. Written before implementation exists.**

Authority: `QUANTUM_ESCAPEMENT_FROZEN_BASELINE_v0.3.md`, sections 5 (Six
Primitives), 6 (Canonical Execution Loop), 7.3 (Delayed Commitment), 9
(Reversibility), 11 (BeliefState), 12 (EVI), and the Experiment 001
definition in `ESCAPEMENT_V2_TO_QUANTUM_ESCAPEMENT_COMPLETE_HISTORY_v1.0.md`.

Where this contract and an implementation disagree, this contract wins.
Where this contract and the frozen baseline disagree, the baseline wins and
this contract is defective and must be amended — not worked around.

---

## 0. Why this document exists, and why it exists *now*

Experiment 001 is the first proof-of-mechanism for Quantum Escapement. It
is the moment the architecture stops being a folder structure and starts
being a claim that can be false.

This contract is written **before** any implementation so that it cannot
be retrofitted to whatever gets built. That ordering is the entire point.
It is not a formality.

The specific risk being controlled: Escapement v1 reached 122 passing
routing evaluations, full green CI, and a clean repository doctor — while
an independent adversarial review still found a genuine router
false-positive that two of the suite's own test cases triggered and none
of them caught, plus a test case that asserted something *structurally
impossible to fail*. Everything was green. Some of it proved nothing.

Every rule in section 5 and section 6 below exists because that specific
failure mode was observed in v1, not because it is theoretically tidy.

---

## 1. Scope

**In scope:** whether the Experiment 001 run demonstrates the *mechanism*
described in the frozen baseline.

**Explicitly out of scope** — a run may be judged PASS while all of the
following remain absent, and a reviewer must not withhold PASS for their
absence:

- LLM/provider integration of any kind
- MCP client or server
- vector database or embedding-based retrieval
- multi-agent, subagent, or recursive execution
- UI, dashboard, or Observatory
- more than one execution capability
- persistent cross-episode learning
- calibration accuracy (the hook must exist; its output need not be good)
- performance, latency, or cost optimisation

Adding any of the above **does not improve** the verdict. A run that
implements the mechanism with three deterministic in-process strategies
and one fake execution capability is a stronger result than one that
integrates four providers and cannot prove criterion 8.

---

## 2. The trace is the only evidence surface

The verdict is computed from a machine-generated append-only event trace.
Not from source inspection, not from a summary, not from the implementer's
description of what happened.

**Required: `events.jsonl`**, one JSON object per line, appended in causal
order, written by the runtime during the run — never hand-authored, never
post-processed into existence.

Minimum event envelope:

```json
{
  "seq": 17,
  "type": "BELIEF_UPDATED",
  "episode_id": "exp001-<deterministic-id>",
  "payload": { },
  "caused_by": [12, 14],
  "rationale": "free text, required on decision events"
}
```

Required event types for Experiment 001:

```text
EPISODE_OPENED
INTENT_DECLARED
OBSERVATION_CREATED
BELIEF_UPDATED
STRATEGY_GENERATED
STRATEGY_RANKED
INFORMATION_ACTION_EVALUATED
INFORMATION_ACTION_SELECTED
INFORMATION_ACTION_EXECUTED
EVIDENCE_ADDED
EXPLORATION_STOPPED
STRATEGY_COMMITTED
EXECUTION_COMPLETED
VERIFICATION_COMPLETED
EPISODE_CLOSED
```

`caused_by` is mandatory on `BELIEF_UPDATED`, `STRATEGY_RANKED`,
`INFORMATION_ACTION_SELECTED`, `EXPLORATION_STOPPED`, and
`STRATEGY_COMMITTED`. An event that changes a decision without a causal
link to the evidence that changed it is a contract violation regardless of
whether the resulting decision was correct.

**Rationale — v1 lesson.** In v1 several eval cases carried an accurate
prose `description` while asserting a *different* field than the one the
description named. The description was right and the assertion was
irrelevant, and both looked fine in a green run. Requiring the causal link
in the trace, rather than in commentary, removes the gap between "what we
say happened" and "what the system recorded happening."

---

## 3. Preconditions — checked before any criterion is scored

If any precondition fails, the verdict is **FAIL** and criteria 1–15 are
not scored. These are cheap, mechanical, and catch the defects already
identified in the current skeleton.

| # | Precondition |
|---|---|
| P1 | `events.jsonl` is produced by the run, is valid JSONL, and `seq` is strictly increasing with no gaps |
| P2 | Every `async` call site has an `async def` definition. The current skeleton awaits `execute_information_action`, `execute`, and `verify` while declaring them with plain `def` — that contract mismatch must be resolved before scoring |
| P3 | Injected collaborators are consistently addressed. The current skeleton calls `self.memory.project(...)` and `self.policy.filter(...)` while declaring `memory` and `policy` as *methods*. Pick constructor-injected attributes or methods and be internally consistent |
| P4 | **AMENDED v1.1 — see §14.** Package layout follows frozen baseline §27: root package `escapement/`, with `intent, state, capabilities, information, policy, strategy, commitment, evidence, observation` present. Each module contains only fields Experiment 001 actually uses. The original wording of this precondition invented a six-module `quantum/` layout that contradicted the baseline, and was a contract defect |
| P5 | `ObservedState` and `BeliefState` are **separate types**, not two fields on one object, and no code path writes a belief into observed state without an intervening `EVIDENCE_ADDED` event |
| P6 | The word `Collapse` appears in no class, function, module, field, or event-type name. It is permitted only in explanatory prose. Baseline 7.3 is explicit that the technical term is `COMMIT` |
| P7 | No network call, no model provider call, no MCP call occurs during the run |

---

## 4. The fifteen criteria

Each maps a frozen success criterion to a mechanically checkable
assertion. `PASS` requires all fifteen.

| # | Frozen criterion | Checkable assertion against the trace |
|---|---|---|
| 1 | Multiple strategies coexist initially | ≥3 `STRATEGY_GENERATED` events precede the first `STRATEGY_COMMITTED`; DIRECT, SEQUENTIAL, RECURSIVE all present |
| 2 | No strategy prematurely selected | No `STRATEGY_COMMITTED` before at least one `EVIDENCE_ADDED`. No strategy holds `ESTABLISHED` or `RULED_OUT` at generation time (**amended v1.1** — originally read "certainty (1.0)", which is unrunnable once beliefs are ordinal labels per foundations §4) |
| 3 | Several information actions compared | ≥3 distinct `INFORMATION_ACTION_EVALUATED` events precede `INFORMATION_ACTION_SELECTED`, each with its own EVI figure |
| 4 | EVI selects a sensible action | The selected action is the argmax of evaluated EVI, `INFORMATION_ACTION_SELECTED.rationale` is non-empty, and the selected action is `INSPECT_DEPENDENCY_MAP` |
| 5 | Evidence updates ObservedState | ≥1 `OBSERVATION_CREATED` with `caused_by` referencing an `EVIDENCE_ADDED` event |
| 6 | World beliefs change | ≥1 `BELIEF_UPDATED` of kind `WorldBelief` whose before/after values differ, `caused_by` the observation from criterion 5 |
| 7 | Strategy beliefs change | ≥1 `BELIEF_UPDATED` of kind `StrategyBelief` whose before/after differ, `caused_by` the world-belief update from criterion 6 — **not** caused directly by the raw observation |
| 8 | Further information becomes uneconomic | A second round of `INFORMATION_ACTION_EVALUATED` occurs *after* the belief updates, and every EVI in that round falls below the comparator. **Amended v1.1:** under the Marginal Value Theorem rule (foundations §3.3) the comparator is *computed* — the expected return of simply proceeding — not configured. `EXPLORATION_STOPPED` must therefore carry the comparator value actually used, or a constant chosen after the fact would satisfy this criterion, which is clause A1 |
| 9 | Commitment occurs because the next action requires it | `STRATEGY_COMMITTED.rationale` cites *both* exhausted information value (criterion 8) and a concrete next action requiring a stable choice |
| 10 | Remaining uncertainty recorded | `STRATEGY_COMMITTED.payload.residual_uncertainty` is present and non-empty |
| 11 | A material alternative retained | `STRATEGY_COMMITTED.payload.retained_alternatives` contains ≥1 strategy that was still plausible at commit time — not a strategy already eliminated |
| 12 | Rationale preserved | Every event listed as requiring `caused_by` in §2 also carries non-empty `rationale` |
| 13 | Every transition explainable | The `caused_by` graph is fully connected from `INTENT_DECLARED` to `STRATEGY_COMMITTED` with no orphan decision events |
| 14 | Run is deterministic | Two runs from identical inputs produce byte-identical `events.jsonl` after excluding a documented allow-list of volatile fields (wall-clock timestamps only). The allow-list must be declared in the experiment README, not inferred |
| 15 | Run is replayable | Replaying the recorded event stream reproduces the same final commitment and the same belief values, without re-executing the information action |

---

## 5. Anti-gaming clauses

These exist because each was observed passing in v1 while proving nothing.

**A1 — No vacuous assertions.** A criterion satisfied by a condition that
*cannot fail given the code's structure* does not count. v1 precedent:
`overlap-01-single-design-director` asserted two capabilities never
co-occur, when they were added in mutually exclusive phase branches and
could never have co-occurred regardless of whether the rule it claimed to
test existed at all.

**A2 — No empty-collection evidence.** An assertion over an empty set
(`retained_alternatives: []`, `residual_uncertainty: {}`) is a no-op and
scores FAIL for that criterion, not PASS. v1 precedent:
`"forbidden_skills": []` intersected with any actual set is always empty
and could never fail.

**A3 — Superset vs exact must be declared.** For every collection
assertion the checker must state whether it is "must contain" or "must
equal." v1 precedent: `capability-trap-03` used a must-contain assertion
to test that something *did not* appear, which it structurally could not
detect.

**A4 — Red before green.** Each of the fifteen checks must be demonstrated
failing at least once against a deliberately broken implementation, and
that demonstration recorded. A check never observed failing is not
evidence.

**A5 — Mutation set.** The following mutations must each flip at least one
named criterion from PASS to FAIL. If a mutation changes nothing, the
corresponding criterion is not actually being tested and the contract is
not satisfied:

```text
M1  commit immediately after strategy generation        -> breaks 2, 9
M2  make all three EVI values identical                 -> breaks 4
M3  write the observation straight into BeliefState     -> breaks 5, 6, 7 (and P5)
M4  drop caused_by from BELIEF_UPDATED                  -> breaks 7, 13
M5  clear retained_alternatives at commit               -> breaks 11
M6  skip the second EVI round                           -> breaks 8
M7  seed a strategy at ESTABLISHED before evidence      -> breaks 2
M8  introduce unordered dict iteration into ranking     -> breaks 14
```

**A6 — The reviewer must attempt one novel falsification.** Beyond M1–M8,
whoever reviews must construct at least one mutation not listed here and
report whether it was caught. v1 precedent: the mutations *I* thought of
all passed; the independent reviewer's novel case found the real bug.

**A7 — Correct outcome is not sufficient.** Selecting RECURSIVE is not
evidence of anything. A hardcoded `return RECURSIVE` satisfies the
scenario's narrative and fails this contract entirely. The verdict is
about the path, never the destination.

---

## 6. Verdict

```text
PASS      P1-P7 all hold
          AND all 15 criteria hold
          AND M1-M8 each flip a named criterion
          AND A6 novel falsification attempted and reported

PARTIAL   preconditions hold, mechanism demonstrably runs,
          but >=1 criterion or >=1 mutation unproven
          -> must name exactly which, and why

FAIL      any precondition fails
          OR any criterion is satisfied only vacuously (A1/A2)
          OR the outcome is correct but the path is not demonstrated (A7)
```

`PARTIAL` is a legitimate, useful result and must not be rounded up.
Escapement v1's own release semantics treat a truthful `PARTIAL` as a
success of the process; the same applies here.

---

## 7. What this contract deliberately does not require

Stated explicitly so a reviewer does not invent scope:

- No requirement that EVI be numerically well-calibrated. Coarse,
  heuristic, even hand-tuned figures are acceptable at v0.1. Baseline §12
  says early EVI may remain heuristic. What must be real is that the
  *comparison* happens and drives the selection.
- No requirement that beliefs be probabilities. Ordinal or interval
  values satisfy every criterion above. Baseline §10 permits coarse
  distributions.
- No requirement that the repository under analysis be real. A fixture
  with a known dependency map is preferable — it makes criterion 14
  achievable.
- No requirement for a database. `events.jsonl` is sufficient and
  preferred at this stage.
- **No policy gate.** Added v1.1: no criterion tests POLICY, and with one
  reversible information action against a fixture there is nothing to
  gate. An inert filter asserted against would be a vacuous pass under
  A1. POLICY is therefore out of scope for Experiment 001, which also
  resolves criterion 13's connectivity — a silent filter removing a
  candidate would otherwise be an unrecorded orphan decision.

---

## 14. Amendments log

**v1.1** — following an independent design review of the six primitive
contracts against this document and the foundations:

| Change | Reason |
|---|---|
| P4 rewritten | Original invented a six-module `quantum/` layout contradicting frozen baseline §27, which specifies root `escapement/` and ten packages including `information/`, `commitment/`, `observation/`. Per this contract's own precedence rule (§0), the baseline wins and the contract was defective |
| Criterion 2, M7 restated | Referred to "certainty (1.0)". Unrunnable once beliefs are ordinal labels (foundations §4), which §7 of this contract already permits. Now `ESTABLISHED` |
| Criterion 8 comparator | "The stated threshold" was undefined and configurable. Under MVT the comparator is computed, so `EXPLORATION_STOPPED` must carry the value used |
| POLICY declared out of scope | §1 |

**Not yet amended, tracked as open:** criterion 9 now has a `next_action`
field to read against (added to STRATEGY), and criterion 11 is now
representable via a candidate lifecycle (`CANDIDATE / ELIMINATED /
RETAINED / COMMITTED`). Both are implemented; the criteria text still
describes them only implicitly and should be tightened before scoring.

---

## 8. Placement

Per the separate-repository decision (history §23), this belongs in the
new research repository, not in the Escapement v1 repository:

```text
experiments/001_useful_uncertainty/
├── README.md          <- declares the determinism allow-list (criterion 14)
├── scenario.py
├── capabilities.py
├── strategies.py
├── information_actions.py
├── run.py
├── expected_trace.json
└── CONTRACT.md        <- this document
```

The research line should not inherit v1's version number; `0.1.0-alpha`
or no product version at all is more honest for a system whose first
experiment has not yet passed.

---

## 9. Finalised identity, and what it means for this experiment

The identity is settled: **Quantum Escapement is an AI agent runtime that
owns the execution loop, with models as capabilities — and it is both an
MCP client and an MCP server.**

**The agent half is already fully encoded above.** Criteria 1–15 test
exactly the loop from baseline §6, in which Quantum — not a model —
observes, generates the strategy ensemble, evaluates information value,
commits, executes, and updates belief. Criterion 7's requirement that a
StrategyBelief change be caused by a WorldBelief change (and not directly
by the raw observation) is precisely the assertion that Quantum is doing
the reasoning rather than transcribing a model's answer. Nothing in the
contract needs to change for the agent identity.

**The MCP-server half needs a sequencing guard, and here is why.** The
frozen baseline v0.3 lists `MCP-first architecture` in its explicit
**non-goals**, and `MCP_TOOL` appears only as one kind in the Capability
Fabric — the *client* direction. The history document is equally direct:
MCP is transport and interoperability, *not the brain*.

Those are not in conflict with "Quantum is an MCP server." They are in
conflict with MCP becoming the organising principle. The distinction to
hold:

```text
Quantum exposes itself via MCP        -> intended, later
MCP shapes how Quantum is built       -> explicit non-goal
```

So Experiment 001 keeps MCP out of scope (§1), and that exclusion is a
*sequencing* decision, not a retraction of the finalised identity.

**But the server identity does change one thing now, and it should be
locked before implementation.** If Quantum is eventually an MCP server,
then the event trace and Observable State Projection are not debugging
conveniences — they are the product surface. What an external host will
consume through MCP resources *is* projected state and evidence.

That promotes three criteria from research hygiene to interface design:

- **13 (every transition explainable)** — becomes the guarantee a
  consuming host relies on, not a nicety for the implementer.
- **15 (replayable)** — becomes the basis for a host reconstructing
  Quantum's reasoning without holding Quantum's context, which is the
  whole point of "communicate state, not transcripts."
- **11 (retained alternatives)** — becomes externally visible optionality
  a host can inspect or override, not an internal bookkeeping field.

Practical consequence for the implementer: design `events.jsonl` and the
state projection as if they will be read by a stranger's tool, because
they will be. Do not encode meaning in field ordering, do not rely on
implicit context to interpret a value, and keep event payloads
self-describing. This costs nothing at v0.1 and is expensive to retrofit.

That is the only amendment the MCP-server decision makes to this
contract. It adds no criterion and relaxes none.
