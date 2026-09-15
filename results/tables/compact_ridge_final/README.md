# Compact Ridge Final Results (Decision 99)

> **Provenance note (submission package):** retained from the canonical
> research repository's results documentation with submission-context
> annotations; scientific content unchanged. Internal
> repository paths below (`outputs/...`, `analysis/...`) refer to the
> canonical repository, not this submission package. In this submission,
> the two tables named here live directly under this folder (no `tables/`
> subfolder), and the three figures + `figures_metadata.md` live under the
> sibling folder `results/figures/compact_ridge_final/` (no `figures/`
> subfolder here) — see `documentation/FIGURE_TABLE_INDEX.md` for the exact
> submission-relative paths.

This directory contains the **minimal publication-facing predictive-model
outputs** for the current, locked final model. It was generated as a
**results/visualization task only** — no model fitting, predictor selection,
hyperparameter search, refitting, new cross-validation, architecture
comparison, or new statistical inference was performed to produce anything
in this directory.

## Model source

- **Current final model:** Compact Ridge logistic regression (Decision 99,
  see `docs/finalization/COMPACT_RIDGE_FINAL_LOCK.md` and
  `CLAUDE.md`'s "Current pipeline state" table).
- **Frozen predictors (6):** `AGE`, `nulliparity`, `S_P_CS`, `BMI_before`,
  `derived_hypertension_pih_pet_spectrum`, `induction_any_bin`. No
  `gestational_age_at_delivery_days`. No endometriosis-specific predictor
  (see Decision 99 rationale: the completed endometriosis exploratory
  analyses on `exploratory/overnight-model-improvement` found no stable
  incremental predictive value from any endometriosis phenotype/severity/
  surgical-history variable; that negative result is retained rather than
  forcing a predictor into the model).
- The historical **Stage 3 / LASSO** architecture (winner of the original
  `final_run`) remains a **historical baseline only** and is shown in the
  performance table strictly as a contextual comparator — it is not a
  current candidate model.

## Exact artifact inputs used (read-only; already verified)

All inputs came from the already-regenerated, already-verified Compact
Ridge lock artifact tree at `outputs/final_modeling/compact_ridge_lock/`
(50/50 outer folds, 0 failures, 4,310 OOF predictions, 431-row final refit,
hash/integrity-verified handoff from the isolated regeneration worktree —
see the prior handoff task in this session):

- `report/locked_validation_oof_predictions.csv` — 4,310 out-of-fold rows
  (431 deliveries x 10 repeated-CV repeats) → source for all three figures.
- `report/locked_validation_manifest.json` — locked repeat-level summary
  metrics (both Compact Ridge and the historical Stage 3/LASSO baseline
  live in this one manifest) → source for the performance table and every
  figure annotation.
- `report/fold_level_metrics.csv` — used only to confirm 50/50 `OK` folds
  during validation.
- `report/coefficient_stability.csv` — outer-fold coefficient
  median/IQR/sign-consistency → source for the coefficient table's
  stability columns.
- `final_refit/coefficients_source_level.csv` and
  `final_refit/coefficients_encoded.csv` — full 431-row final-refit
  coefficients → source for the coefficient table.
- `final_refit/final_refit_manifest.json` — confirms 431 rows used, chosen
  C = 0.3162, intercept = -2.0476, `converged: true`.
- `final_refit/preprocessing_spec.json` — confirms the categorical
  encoding scheme for `derived_hypertension_pih_pet_spectrum` (full-dummy,
  not reference/drop-first).

**No other file was read for scientific content.** No publication-analysis,
notebook, or WIP path was opened for editing.

## What was NOT done

- No model was refit for these outputs beyond what is already in the
  locked artifact tree.
- No new cross-validation, hyperparameter search, or predictor search was
  run.
- No new statistical inference (e.g. bootstrap CIs) was computed; only the
  already-locked repeat-level means/SDs are reported.
- No odds-ratio interpretation of the Ridge coefficients — they remain
  labeled as penalized coefficients on the standardized/encoded scale.
- No threshold or clinical-classification metrics (sensitivity/specificity
  at a cutpoint, etc.) were produced.
- No external/independent validation — this is internal, repeated,
  subject-grouped cross-validation performed after exploratory model
  development on the same dataset.
- The historical Figures 1-10 set (LASSO selection-frequency,
  endometriosis-predictor selection-frequency, constrained-vs-unconstrained,
  Stage 3A/3B sensitivity, class-weight distribution) was **not**
  regenerated for this architecture — those belonged to the Stage 3/LASSO
  pipeline and do not map onto a fixed 6-predictor Ridge model.

## Contents

```
outputs/results/compact_ridge_final/
├── README.md                                  (this file)
├── tables/
│   ├── table_final_model_performance.csv/.md   Compact Ridge vs. historical
│   │                                           Stage 3/LASSO baseline
│   └── table_final_ridge_coefficients.csv/.md  Full-refit Ridge coefficients
│                                               + outer-fold stability
└── figures/
    ├── figure_compact_ridge_precision_recall.png/.svg
    ├── figure_compact_ridge_roc.png/.svg
    ├── figure_compact_ridge_calibration.png/.svg
    └── figures_metadata.md                     Exact repeated-CV aggregation
                                                 method for each figure
```

## Generating script

`analysis/reports/compact_ridge_final_outputs.py` — reads only the locked
artifacts listed above, performs internal validation checks against the
locked manifest (numbers must match to the rounded decimal shown), and
writes every file in this directory.

**Canonical-repository regeneration command** (not runnable from this
curated submission — the script itself, and the locked
`outputs/final_modeling/compact_ridge_lock/` artifact tree it reads,
including the excluded row-level `locked_validation_oof_predictions.csv`,
are canonical-repository inputs not included in this package; see the root
`README.md` reproducibility tiers):

```
python analysis/reports/compact_ridge_final_outputs.py
```

## Caveats carried through every output

> Performance represents internal repeated subject-grouped cross-validation
> after exploratory model development on the same dataset; it is not
> independent or external validation.

> Ridge coefficients are penalized coefficients on the standardized/encoded
> modeling scale and are not conventional adjusted odds ratios.

`BMI_before` is flagged in the coefficient table as directionally unstable
(sign consistency 0.54 across the 50 outer validation folds, vs. 1.00 for
every other continuous/binary predictor) — its full-refit coefficient sign
should not be over-interpreted.

## Note on the project's commit policy

Per `CLAUDE.md`, in the **canonical research repository** `.csv` files
cannot be committed (extension-level guard). The two tables here were
therefore produced in both `.csv` (machine-readable) and `.md`
(human-readable, git-committable) form for that reason, and both forms are
retained. **This submission's own Git policy is narrower and different:**
this curated package intentionally does track approved `.csv`/`.xlsx`
artifacts (including the `.csv` versions of these same two tables) — see
the root `README.md` and `SUBMISSION_MANIFEST.md` for the submission's
actual inclusion policy; the canonical guard described above does not apply
here.
