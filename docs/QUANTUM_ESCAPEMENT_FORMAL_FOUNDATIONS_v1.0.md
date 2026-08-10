# Quantum Escapement — Formal Foundations v1.0

**Purpose:** replace metaphor with machinery. For every open problem in the
frozen baseline, name the existing formalism that already solves it, state
what it concretely changes, and record what we are refusing to borrow.

**Admission rule.** A science earns a place here only if it supplies
formal machinery that resolves a *named* problem in
`QUANTUM_ESCAPEMENT_FROZEN_BASELINE_v0.3.md`. Resemblance is not
admission. Section 9 lists what was considered and rejected, and why —
that list is part of the design, not an appendix.

This document exists because the baseline's own risk register names
**Overdesign**, **False precision**, and **Quantum branding confusion** as
top research risks. A document that adds five more metaphors would
worsen all three. Every borrowing below either reduces work or prevents a
specific error.

---

## 1. The honest formal frame: this is a POMDP

Strip the vocabulary and Quantum Escapement is a **Partially Observable
Markov Decision Process** whose action set includes both world-changing
actions and information-gathering actions, executed by heterogeneous
capabilities of differing cost and reliability.

```text
Baseline term          POMDP term
─────────────────────────────────────────────
ObservedState          observation history
BeliefState            belief state b(s)
INTENT                 reward function / goal
CAPABILITY             action set (with costs)
STRATEGY               policy π
INFORMATION_ACTION     information-gathering action
EVIDENCE               observation
COMMITMENT             policy selection under bounded deliberation
```

**Why naming this matters, concretely:**

1. **It imports decades of machinery.** Belief update, value of
   information, optimal stopping, and policy evaluation are solved
   problems in this frame. We should not reinvent them under new names.

2. **It explains why the architecture must be heuristic — rigorously.**
   Solving POMDPs optimally is PSPACE-hard in the finite-horizon case and
   undecidable in general. This is not a caveat; it is *load-bearing
   justification*. The baseline's insistence on coarse distributions and
   heuristic EVI is not a v0.1 shortcut to be apologised for and later
   replaced with something exact. **Exactness is provably unavailable.**
   Anyone who later proposes "let's compute the true optimal strategy"
   is proposing something impossible, and this section is the answer.

3. **It gives an honest novelty claim.** The contribution is not a new
   decision theory. It is: *a POMDP formulation where the action set is
   LLM-and-tool capabilities, the belief state spans an engineering task,
   and deliberation itself is budgeted.* That is defensible in a paper.
   "Quantum-inspired execution" is not.

**Consequence for the repository:** the six primitives should be
documented with their POMDP correspondence stated inline. It costs six
sentences and permanently anchors the vocabulary to something rigorous.

---

## 2. The unifying objective: Expected Free Energy

The baseline currently treats two things as separate mechanisms: pursuing
the intent, and gathering information (EVI, §12). It has no single
quantity that trades them off, which is why "is this information worth
it?" reads as a heuristic bolted onto the side.

**Active inference already unifies them.** Under the Free Energy
Principle (Friston), an agent selects the policy minimising *expected
free energy*, which decomposes exactly into:

```text
G(π)  =  −(pragmatic value)   −  (epistemic value)
           ↑                        ↑
      progress toward          expected information
      the intent               gain about hidden state
```

This is the single most relevant existing framework to what the baseline
is describing, and the mapping is not loose:

| Baseline concept | Active inference term |
|---|---|
| Strategy ensemble | policy space Π |
| EVI of an information action | epistemic value term |
| Intent progress | pragmatic value term |
| "Is more information worth it?" | comparing G(π) across policies |
| Delay cost, context burden | additional cost terms in G |
| Commitment | selecting argmin G(π) when deliberation stops |

**What this concretely changes:**

- EVI stops being a bolt-on. Information actions and execution actions
  are scored on **one scale**, so "inspect the dependency map" and
  "just start implementing" become directly comparable. The baseline
  currently cannot compare them without a conversion rule it does not
  specify.
- The system gets a principled answer to *analysis paralysis* (a named
  risk): exploration stops when no information action's epistemic value
  exceeds the pragmatic cost of delay. That is a computation, not a
  `max_questions = 5` rule — which the baseline explicitly rejects.
- Curiosity is bounded by design rather than by a cap. Epistemic value
  falls as beliefs sharpen; the agent naturally stops exploring.

**Honesty constraint.** Do not claim to *implement* the Free Energy
Principle. Claim: *"the objective is structured as expected free energy —
pragmatic plus epistemic value — computed with coarse estimates."* The
decomposition is what we are borrowing. The neuroscience is not.

---

## 3. Commitment timing — three formalisms, each solving a different half

The baseline says commit when "the next action requires concreteness"
(§7.3). That is a description, not a decision rule. Three distinct
formalisms cover the three distinct situations, and conflating them is
what makes the current definition feel vague.

### 3.1 Sequential Probability Ratio Test (Wald) — *when evidence suffices*

The question "have I seen enough evidence to choose?" is **the** classical
sequential analysis problem. SPRT: keep sampling while the likelihood
ratio sits between two thresholds; stop when it crosses either.

Wald's result is that SPRT is *optimal* — it minimises expected samples
for given error rates. Mapped here:

```text
while  lower < evidence_ratio(RECURSIVE vs alternatives) < upper:
        gather more information
stop and commit when a boundary is crossed
```

This gives criterion 8 of the Experiment 001 contract ("further
information becomes uneconomic") a real, defensible implementation rather
than a tuned constant. The thresholds encode tolerance for choosing
wrongly, which is a *policy* input — exactly where the baseline's
three-zone governance (BLACK/WHITE/GREY) should set them.

### 3.2 Real options theory — *when irreversibility dominates*

The baseline's §9 (Reversibility) says high reversibility → delay
commitment, low reversibility → commit earlier with higher evidence. That
is precisely **option value under irreversibility** (Dixit & Pindyck).

The formal result worth importing: under uncertainty, an irreversible
action carries an *opportunity cost of committing now* equal to the value
of the option to wait. This is why the naive "positive expected value →
act" rule is wrong for irreversible actions, and it is a rigorous
statement of the baseline's intuition.

```text
reversible action    →  option to wait is cheap, exercise readily
irreversible action  →  option has real value, require a higher
                        threshold before exercising
```

**This inverts a naive reading.** One might assume low reversibility
means *decide sooner to be safe*. Real options says the opposite for the
*action*: irreversibility raises the evidence bar and makes waiting more
valuable. What must happen earlier is the **policy gate**, not the
action. The baseline's wording ("earlier commitment gate") is right; this
formalism explains why, and prevents the misreading.

### 3.3 Marginal Value Theorem (Charnov, foraging ecology) — *when to leave*

From behavioural ecology: an animal foraging a depleting patch should
leave when the patch's marginal return rate drops to the *habitat
average* rate. Not when the patch is empty — when it drops below what is
available elsewhere.

This is the sharpest available answer to "when do we stop investigating
*this* line of inquiry?" and it corrects a real error:

> Stop investigating not when this information source is exhausted, but
> when its marginal yield falls below the yield of **just proceeding**.

That is a genuinely different — and better — stopping rule than "EVI
below a fixed threshold," because the threshold becomes the opportunity
cost of the alternative rather than an arbitrary constant. Biology earns
its place here; this is a theorem, not an analogy.

---

## 4. Belief representation without false precision

The baseline forbids invented probabilities (risk: **False precision**)
but still requires belief updates. These are in tension unless the
representation supports *ignorance* as distinct from *uncertainty*.

**Point probabilities cannot express "I don't know."** `P = 0.5` means
"equally likely," which is a strong claim. It is not the same as having
no information — but standard Bayesian representation cannot tell them
apart, and this is exactly how false precision enters.

**Use credal sets / interval-valued probability (Walley's imprecise
probability), or Dempster–Shafer belief functions.**

```text
Point:     P(modular) = 0.7          ← claims precision we lack
Interval:  P(modular) ∈ [0.4, 0.9]   ← honest: leaning yes, weak evidence
Ignorance: P(modular) ∈ [0.0, 1.0]   ← honest: genuinely unknown
```

Evidence *narrows the interval*. That is a visible, auditable
representation of learning, and it makes Experiment 001's criterion 6
("world beliefs change") observable as interval contraction rather than a
number nudging from 0.7 to 0.75 for reasons nobody can defend.

Dempster–Shafer adds an explicit mass for "unassigned," directly
representing the baseline's `Believed != Proven` invariant.

**Recommendation for v0.1:** ordered interval labels, not floats.

```text
RULED_OUT  <  UNLIKELY  <  PLAUSIBLE  <  LIKELY  <  ESTABLISHED
```

with the rule that evidence moves a belief at most one step per
observation unless the evidence is decisive. This is coarse, honest,
survives the "no invented probabilities" constraint, and is sufficient for
every Experiment 001 criterion. Floats can come later *if calibration
data justifies them* — which is the baseline's own rule.

---

## 5. State invalidation: this is a solved problem in classical AI

The baseline's §21.5 (state invalidation), §21.3 (dependency graph), and
§21.4 (selective propagation) describe **Truth Maintenance Systems** —
specifically a justification-based TMS (Doyle, 1979) or assumption-based
ATMS (de Kleer, 1986). This is 45-year-old, well-understood machinery.

What a JTMS provides, matching the baseline point for point:

| Baseline need | TMS mechanism |
|---|---|
| State dependency graph | justification network |
| Invalidation on new evidence | dependency-directed backtracking |
| `STALE`, not `FAILED` | node label `OUT` rather than deleted |
| Provenance | justification records |
| Selective propagation | only nodes reachable from the changed node |
| Retained alternatives | ATMS environments |

**The critical property we should copy:** a TMS marks beliefs `IN` or
`OUT` **without deleting them**, so a belief invalidated by evidence can
be revived if that evidence is later retracted. The baseline's insistence
on `STALE` rather than `FAILED` is exactly this instinct, arrived at
independently. Naming it means we get the algorithms for free.

**ATMS additionally tracks which assumption-set supports each belief** —
which is precisely "retained alternatives with their supporting
rationale," Experiment 001 criterion 11.

**Do not build a bespoke invalidation engine.** Implement a small JTMS.
It is a few hundred lines and it is *correct*, which a hand-rolled
propagation scheme will not be.

Related: **AGM belief revision** (Alchourrón–Gärdenfors–Makinson) gives
the rationality postulates for what a *correct* belief update must
satisfy — notably minimal change. Useful as a conformance check on the
belief engine.

---

## 6. Capability interaction: submodularity and Shapley

Baseline §7.6 calls capability interaction effects "interference." The
real machinery is **non-additive set functions**.

```text
Submodular    v(A ∪ {x}) − v(A)  decreases as A grows
              → diminishing returns: two code reviewers
                overlap heavily; the second adds less

Supermodular  the increment increases with A
              → genuine complements: architecture analysis
                plus dependency inspection are worth more
                together than apart
```

**Why this is worth importing rather than approximating:**

1. **Greedy selection has a proven bound.** Maximising a submodular
   function under a cardinality constraint via greedy selection achieves
   ≥ (1 − 1/e) ≈ 63% of optimal (Nemhauser et al.). So the obvious
   implementation — add capabilities one at a time by marginal value —
   is *provably near-optimal*, not merely reasonable. That converts a
   guess into a guarantee.

2. **Shapley values solve attribution.** When a strategy using four
   capabilities succeeds, "which capability deserves credit?" is the
   baseline's §24 Failure Attribution problem. The Shapley value is the
   unique attribution satisfying efficiency, symmetry, null-player, and
   additivity. It is expensive to compute exactly, but with ≤6
   capabilities it is trivially enumerable.

This directly feeds StrategyBeliefs: Shapley attribution over episodes is
how the system learns *which capability actually helped*, rather than
crediting everything present when something worked — a failure mode I
have seen repeatedly in v1's own evaluation work, where a passing result
was attributed to the whole configuration.

---

## 7. Context budget and state projection

### 7.1 Context allocation → submodular maximisation under a knapsack

"Which state objects enter the context window?" is selection under a
budget with diminishing returns — the same structure as §6. Greedy by
marginal-information-per-token carries the same (1 − 1/e) guarantee.

This replaces v1's fixed word budgets with something adaptive. Note the
continuity: v1 enforced `≤1,000 words` for invoked skill context and it
worked, but it could not distinguish 1,000 words of *relevant* context
from 1,000 words of noise. Marginal value per token can.

### 7.2 Observable State Projection → Markov blanket / d-separation

Baseline §21.6 asks what subset of state a subagent should see. Pearl's
**d-separation** answers this exactly: a node's **Markov blanket**
(parents, children, children's other parents) renders it conditionally
independent of the entire rest of the network.

```text
"What does the security subagent need to see?"
    = the Markov blanket of the security-relevant state nodes
```

Everything outside the blanket is, by construction, information that
cannot change that subagent's conclusions. This is the rigorous form of
"shared truth without shared context" — and it is *checkable*, which a
heuristic projection is not.

It also gives Experiment 005 a real success criterion: a projection is
correct if excluded state is d-separated from the subagent's decision.

Pleasing convergence: the Markov blanket is also the formal boundary of an
agent in active inference (§2). The same construct defines both the
agent's boundary and its context projection. That is not decoration — it
means one implementation serves both.

---

## 8. Calibration: proper scoring rules

Baseline §23 requires calibration from data. The machinery is settled.

- **Brier score** and **logarithmic score** are *strictly proper*: they
  are minimised only by reporting one's true belief. Using an improper
  score would actively incentivise the system to misreport confidence.
- **Reliability diagrams** show whether things predicted at "likely"
  actually occur at that rate.
- **Isotonic regression / Platt scaling** map raw confidence to
  calibrated confidence once enough episodes exist.

With interval beliefs (§4), the calibration target becomes *coverage*:
do 80% intervals contain the truth 80% of the time? Under-coverage means
overconfidence; over-coverage means uselessly wide intervals.

**Sequencing rule, from the baseline's own risk register
("Self-optimization instability"):** calibrate *before* any policy
mutation. Measure first. Adapt second. Never simultaneously.

---

## 9. Rejected borrowings — and why

This section is load-bearing. The failure mode is a system that sounds
profound and computes nothing.

| Considered | Rejected because |
|---|---|
| **Actual quantum formalism** (Hilbert spaces, amplitudes, Born rule) | Requires complex amplitudes and interference. We use classical probability by explicit baseline decision. Importing the mathematics would be wrong, not merely unnecessary. |
| **Genetic algorithms** for strategy generation | Needs large populations and cheap fitness evaluation. Our fitness evaluations are LLM calls costing seconds and cents. Wrong cost regime by orders of magnitude. |
| **Immune-system metaphors** (self/non-self, danger theory) for the trust firewall | Pure analogy. Provides no algorithm that access-control lists and provenance tracking do not already provide better. |
| **Category theory** for capability composition | Real mathematics, but here it would describe composition we already understand rather than resolve any open question. Notation, not insight. |
| **Thermodynamic entropy** as a system-health metric | Shannon entropy over the belief state is meaningful and already used in §2's epistemic value. Thermodynamic analogies beyond that (temperature, free energy as *heat*) have no referent here. |
| **Renormalisation group** for recursive decomposition | Genuinely elegant, and the scale-coarsening parallel is real. But it presupposes scale-invariance we have no evidence for in task decomposition. Revisit only if empirical data shows self-similar structure. |
| **Nash equilibrium** for capability selection | Capabilities are not strategic agents optimising against us. Game theory becomes relevant only for genuine multi-agent negotiation, which is out of scope for v0.1–v0.5. |
| **Quantum annealing / QAOA** | We are not solving an optimisation problem of that class, and there is no hardware in the loop. Would be a false claim. |

**Standing rule:** any future borrowing must name the problem it solves,
the mechanism it supplies, and what breaks without it. If the answer to
the third is "nothing," it is decoration.

---

## 10. Precision guard: where the quantum metaphor actively misleads

The baseline mitigates "Quantum branding confusion" by saying
*quantum-inspired*. Necessary but insufficient — three specific terms
will cause **engineering errors**, not just PR confusion, if taken
literally.

### 10.1 "Interference" (§7.6) is the dangerous one

In physics, interference arises from **complex probability amplitudes**
and is precisely what makes quantum probability differ from classical.
Classical probabilities cannot interfere — that is a theorem, not a
limitation of our implementation.

Since the baseline commits to classical probability, **capability
interaction effects are not interference.** They are non-additive utility
(§6). The risk is concrete: an engineer who takes "interference"
literally will look for cancellation and phase relationships that cannot
exist, and may implement signed amplitude arithmetic that produces
negative probabilities.

**Recommendation:** rename to `CapabilityInteraction` in all code, with
`sub_additive` / `super_additive` classifications. Keep "interference"
only in prose, flagged as analogy.

### 10.2 "Entanglement" (§7.7)

Real entanglement produces correlations violating Bell inequalities —
impossible to reproduce with shared classical information. What the
baseline describes is *shared state between agents*: classical
correlation via a common cause. That is ordinary, well-understood, and
fine.

**Keep the name if it aids communication** — `StateEntanglement` is
evocative and the baseline uses it consistently. But document once, in
the code, that this is classical correlation. Nobody should go looking
for non-locality.

### 10.3 "Superposition" (§7.1)

A strategy ensemble is a **set of candidate policies with associated
belief weights** — a mixture, not a superposition. A quantum superposition
is a single state in a complex vector space that can interfere with
itself. Ours cannot, and should not be expected to.

The baseline's translation (superposition → strategy ensemble) is already
correct. The guard is: do not let anyone "improve" the ensemble by adding
phase or amplitude.

---

## 11. What this changes in Experiment 001

Concretely, without expanding scope:

1. **Belief representation** → ordered interval labels (§4), not floats.
   Criterion 6 becomes *interval contraction*, which is observable and
   defensible.
2. **Stopping rule** → Marginal Value Theorem (§3.3): stop when marginal
   information yield falls below the return of proceeding. Criterion 8
   gets a real rule instead of a tuned constant.
3. **EVI** → structured as epistemic value in an expected-free-energy
   comparison (§2), so information and execution actions are scored on
   one scale. Still coarse; now principled.
4. **Belief propagation** → a minimal JTMS (§5). Criterion 7's causal
   chain (observation → world belief → strategy belief) becomes the
   justification network, so `caused_by` in the trace is *generated by the
   mechanism* rather than manually attached. That is a materially
   stronger guarantee than the contract currently asks for.
5. **Retained alternatives** → ATMS environments (§5). Criterion 11 stops
   being a bookkeeping field and becomes a live structure.
6. **Naming** → `CapabilityInteraction`, not interference (§10.1).

None of this adds a dependency, a provider, or a service. It is all
in-process, deterministic, and replayable — so the Experiment 001 review
contract stands unchanged.

---

## 12. Minimal implementable subset for v0.1

Ruthlessly cut, in dependency order:

```text
1. Interval belief labels + one-step-per-evidence update       (§4)
2. Minimal JTMS: nodes, justifications, IN/OUT, propagation    (§5)
3. Expected-free-energy scoring: pragmatic + epistemic         (§2)
4. MVT stopping rule                                           (§3.3)
5. Greedy submodular context selection                         (§7.1)
6. Brier score logging — recorded, not yet acted on            (§8)
```

Deferred with justification, not forgotten:

```text
Shapley attribution      needs ≥1 episode of real data first   (§6)
d-separation projection  needs multi-agent, which is v0.5+     (§7.2)
SPRT thresholds          needs calibrated likelihoods          (§3.1)
Real options valuation   needs cost/benefit magnitudes         (§3.2)
Isotonic calibration     needs ~100 episodes                   (§8)
```

The deferrals share a pattern worth stating: **each needs empirical data
that does not exist yet.** Implementing them now would mean inventing
their inputs — which is precisely the "False precision" risk the baseline
warns against. They are correctly ordered *after* first data, not
dropped.

---

## 13. The one-paragraph defence

> Quantum Escapement is a POMDP formulation of AI-assisted software
> delivery in which the action set comprises heterogeneous model, tool,
> and human capabilities with differing cost and reliability; belief is
> represented with imprecise probability to avoid false precision;
> information-gathering and world-changing actions are scored on a single
> expected-free-energy objective; commitment timing follows optimal-
> stopping rules modulated by action reversibility; belief revision uses
> justification-based truth maintenance so that invalidation and
> provenance are structural rather than bolted on; and every mechanism is
> required to survive ablation against a deterministic, replayable
> evidence trace.

No quantum claim. No borrowed mystique. Every clause names a real
formalism and points at a mechanism that can be tested — and, more
importantly, that can *fail*.
