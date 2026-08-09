# Decision journal

Roadmap step 1. The honest form of self-hosting.

Continuum does not write Continuum. It records the decisions *about*
Continuum as structured entries, each carrying a prediction made before
the outcome is known.

```bash
python -m escapement.journal --path journal/decisions.jsonl list
python -m escapement.journal --path journal/decisions.jsonl show d002-jtms-not-hand-rolled-invalidation
python -m escapement.journal --path journal/decisions.jsonl report

python -m escapement.journal --path journal/decisions.jsonl record \
  --id d009-some-decision \
  --question "what was being decided" \
  --chosen "what was chosen" \
  --alternative "what else was genuinely on the table" \
  --rationale "why, citing something" \
  --predict "a falsifiable claim about the future" \
  --confidence LIKELY \
  --criteria "BROKE if ..."

python -m escapement.journal --path journal/decisions.jsonl resolve d009-some-decision held --note "what happened"
```

## Why this and not real self-hosting

Routing development through `run_episode()` today would mean recording
that Continuum chose things it did not choose — it has no model
integration and cannot write code. That is narration, not evidence.

It would also make the correlation problem structural, in a project
where independent review has twice found real defects in self-authored
work, and it inverts baseline §35's own mitigation for
self-optimization instability: *empirical calibration before policy
mutation.*

**The rule:** the journal records and structures decisions. It does not
gate them. Advisory until calibration exists.

## What makes an entry worth recording

- **Alternatives that were genuinely defensible.** Strawmen make the
  journal longer without making it evidence.
- **A prediction that could be wrong**, with criteria stating how you
  would know. Enforced at construction — a prediction without
  resolution criteria is rejected.
- **Rationale citing something** — a document section, a review finding,
  a test result.

## Retrospective entries

The eight seeded entries are marked `retrospective`, because they record
decisions made before the journal existed. Their author already knew how
the build was going, so counting them toward calibration would flatter
the hit rate for free. They are **excluded by default**.

They earn their place a different way: every one of their predictions is
*forward*-looking — about rework that has not happened yet — so they
become scoreable later without ever having been graded on hindsight.

## Why there is no Brier score

Foundations §8 names Brier and log score as the strictly proper rules,
and eventually they are the right instruments. A proper scoring rule
needs a probability. Our confidences are ordered labels, deliberately,
because a point probability cannot distinguish uncertainty from
ignorance (foundations §4).

Computing Brier would mean deciding that LIKELY "means" 0.75 on no
evidence, and the system would then optimise against a number nobody
measured — the exact False precision failure the ordinal representation
exists to prevent.

What *is* measurable without inventing anything is a reliability table:
for each label, how often did predictions at that label actually hold?
That is counted, not asserted. Raw labels and outcomes are stored, so
Brier can be computed later if a calibrated mapping is ever justified.

## Reading the report honestly

Below ten resolved predictions the report refuses to show a trend and
says so. Roughly 100 resolved predictions is where isotonic calibration
becomes meaningful; thirty is a first signal.

If the rates come back badly calibrated, that is a real negative result
about the approach — which is the point of recording them.
