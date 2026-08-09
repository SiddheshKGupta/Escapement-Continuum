# Escapement-Continuum — Roadmap

Version 0.1.0-alpha. Research line, not a product. Nothing here is
validated until an experiment says so.

---

## Where we actually are

Built and passing 93 tests:

```text
six typed primitives          intent, state, capabilities, policy,
                              strategy, evidence
belief representation         five ordered labels, no floats
JTMS                          justification network; explain() generates
                              causal chains rather than hand-attaching them
information layer             actions bound to capabilities, coarse EVI,
                              Marginal Value Theorem stopping rule
agent loop                    owns the reasoning; capabilities injected
event trace                   append-only, contract-enforced at write time
Experiment 001                runs, commits RECURSIVE, 21-event trace
```

Not built, and honestly named: no model integration, no tool execution,
no memory fabric, no multi-agent, no MCP surface, no calibration data.

**Experiment 001 is not passed.** It passes tests I wrote for an
implementation I wrote. That is the exact correlation risk that an
independent review has already caught twice in this project. Until
someone else scores it against the contract, it is a candidate result.

---

## Step 0 — Independent scoring of Experiment 001 (blocks everything)

Nothing downstream is worth building on an unverified first result.

- Hand `QUANTUM_EXPERIMENT_001_REVIEW_CONTRACT_v1.0.md` (at v1.1) and
  `experiments/_001/events.jsonl` to a reviewer who did not write the
  implementation — Codex or Antigravity.
- They score the fifteen criteria, run the M1–M8 mutation set, and
  construct one novel mutation per clause A6.
- Required output: PASS, PARTIAL, or FAIL — with `PARTIAL` naming
  exactly which criterion is unproven. A rounded-up PARTIAL is worse
  than a FAIL, because it removes the reason to fix anything.

**Exit condition:** a verdict written by someone other than the author.

---

## Step 1 — The decision journal (starts now, runs forever)

The honest form of self-hosting, and the one that builds the RLM case
rather than asserting it.

Continuum does **not** write Continuum. It records the decisions about
Continuum as episodes: intent, strategy ensemble, evidence, commitment,
and — critically — a *prediction* made before the outcome is known.

Why this and not real self-hosting:

- It needs no model integration, so it can start today.
- It generates the calibration data that foundations §8 requires and
  §12 defers everything else behind. Isotonic calibration needs roughly
  100 episodes; we have zero.
- It is falsifiable. If after thirty decisions the predictions are badly
  calibrated, that is a real negative result about the approach, not an
  embarrassment to explain away.
- It tests H1 (delayed commitment), H2 (EVI) and H6 (calibration)
  against real decisions rather than fixtures.

**The rule that keeps it safe:** Continuum records and structures
decisions. It does not gate them. Advisory only until calibration
exists. This is baseline §35's own mitigation for
"Self-optimization instability" — empirical calibration *before* policy
mutation — and inverting it is how a research system starts believing
its own uncalibrated advice.

**What a strong RLM claim looks like at the end of this:** not "it built
itself", which is circular and unverifiable, but "here are N recorded
decisions with predictions made before outcomes were known, and here is
the calibration curve." A skeptic can check the second claim.

---

## Step 2 — Experiment 002: fixed harness vs adaptive strategy

The first comparison that could embarrass the thesis, which is why it
comes early.

- Same task, same capabilities, same budget.
- Arm A: fixed routing (v1's model).
- Arm B: adaptive strategy ensemble with delayed commitment.
- Pre-register what would count as *no difference* before running.

A null result here is the single most informative outcome available at
this stage, and must be publishable within the project rather than
retried until it inverts.

---

## Step 3 — Model integration as a capability

Only after 001 is independently scored and 002 is designed.

The identity constraint holds: the model is a `CapabilityKind.MODEL`
inside the loop, not the loop's brain. The seam already exists —
`Performs` in `loop.py`. Integration means implementing that protocol,
not restructuring the loop.

Guard: if integrating a model requires changing `run_episode()`'s
control flow, the identity claim was wrong and that is a finding worth
recording, not a merge conflict to resolve quietly.

---

## Step 4 — Experiments 003 through 005

```text
003  direct vs recursive           needs real execution (step 3)
004  attribution and replay        needs multiple episodes (step 1)
005  context projection            needs multi-agent; d-separation
                                   from foundations §7.2 applies here
```

Sequenced by dependency, not by interest.

---

## Step 5 — MCP server surface

Deferred deliberately. Baseline §28 lists `MCP-first architecture` as an
explicit **non-goal**, and `MCP_TOOL` appears only as a capability kind
— the client direction.

Exposing Continuum via MCP is intended. Letting MCP shape how it is
built is not. The distinction is recorded in the Experiment 001 contract
§9 and should survive contact with the first person who wants to demo it.

The design consequence is already locked: the event trace and state
projection are the product surface, not debug output, so they are built
to be read by a stranger's tool.

---

## Standing rules

1. **No mechanism ships without an experiment that could falsify it.**
   Baseline §35's mitigation for Overdesign is that every mechanism must
   survive ablation.
2. **Independent scoring for anything self-authored.** Established the
   hard way: two adversarial reviews in this project each found real
   defects — a vacuous test asserting something structurally impossible
   to fail, and a router false-positive that two of the suite's own
   cases triggered without catching.
3. **PARTIAL is a real verdict.** Rounding it up removes the reason to
   fix anything.
4. **No claim outruns its evidence.** Continuum has not beaten anything.
   It has not been shown to help. It runs one fixture experiment whose
   result has not been independently confirmed.
