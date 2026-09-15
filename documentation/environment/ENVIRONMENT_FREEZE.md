# ENVIRONMENT FREEZE — submission snapshot

> **Provenance note (submission package):** retained from the canonical
> research repository with submission-context annotations (such as this
> note); scientific/environment facts otherwise unchanged. Source: the
> canonical research repository at
> commit `e7676be3167c706950ce1a564fc454223f0d265d` (tag `final-project-2026`)
> at `docs/finalization/ENVIRONMENT_FREEZE.md`. Internal repository paths
> mentioned below (e.g. `requirements/...`) refer to that canonical
> repository, not this submission package. Verified current and consistent
> with the actual final local environment as of this submission's assembly
> (2026-09-10) — cross-checked directly against a fresh `pip freeze` in the
> same `.venv312`. This submission's own root `requirements.txt` is derived
> from that same verified environment, scoped to only the packages actually
> imported by the code included in this package (plus one addition,
> `patsy`, which this snapshot's "key package versions" table does not
> separately list but which is installed in `.venv312` and is a direct
> import of the submitted publication-analysis source).
>
> **One disclosed inconsistency, not silently resolved:** the co-located
> `documentation/environment/data-cleaning-b-py31210-lock.txt` in this same
> submission folder pins different (newer) versions of several packages
> (`numpy==2.5.1`, `pandas==3.0.3`, `scipy==1.18.0`, `matplotlib==3.11.1`)
> than this freeze document's table below and than the versions actually
> installed in the live `.venv312` verified above (`numpy 2.3.5`,
> `pandas 2.3.3`, `scipy 1.16.3`, `matplotlib 3.10.0`). That lock file's
> SHA-256 (quoted below) matches this document's own citation of it, so the
> lock file's *pinned spec* was apparently regenerated at some point after
> this freeze without `.venv312` being rebuilt from it -- a
> canonical-repository provenance gap this submission cannot resolve on its
> own. The root `requirements.txt` and this freeze document both follow the
> verified live environment; treat the lock file's exact pins as
> historical/aspirational for those four packages rather than as the
> currently-running environment.

**Freeze date: 2026-09-03.** Captured from the live `.venv312` on the analysis
machine. No secrets are included.

---

## Interpreter

| | |
|---|---|
| Python executable | `.venv312\Scripts\python.exe` (repo-root virtual env) |
| Python version | **3.12.10** |
| pip version | 26.1.2 |
| OS | Windows 11 Pro, 10.0.26200 |

## Canonical dependency spec

`requirements/data-cleaning-b-py31210-lock.txt` — SHA-256
`682d4796e950972a5228d8f8f922c98773cf909d03cddad4d6d47f762d052d75`. This is
the project's canonical lock file (created for Data Cleaning B; also the
practical environment for EDA C and final modeling). Install with:

```
py -3.12 -m venv .venv312
.venv312\Scripts\python.exe -m pip install --no-deps -r requirements/data-cleaning-b-py31210-lock.txt
```

Never reuse a `.venv` copied from another machine — always build it fresh from
the lock file.

Other `requirements/` files: `data-cleaning-b.in` (source spec),
`data-cleaning-b-lock.txt` (**mislabeled** earlier Python-3.10 lock — superseded;
the real py3.10-mislabel note and the preserved copy are under
`recovery_evidence/data-cleaning-b-lock-MISLABELED-py310-DEPRECATED.txt`).

## Key package versions observed in `.venv312` (2026-09-03)

| Package | Version |
|---|---|
| numpy | 2.3.5 |
| pandas | 2.3.3 |
| scipy | 1.16.3 |
| **scikit-learn** | **1.9.0** |
| statsmodels | 0.14.6 |
| joblib | 1.5.3 |
| threadpoolctl | 3.6.0 |
| matplotlib | 3.10.0 |
| seaborn | 0.13.2 |
| openpyxl | 3.1.5 |
| nbformat | 5.10.4 |
| nbclient | 0.11.0 |
| nbconvert | 7.17.1 |
| ipykernel | 7.3.0 |
| pytest | 9.1.1 |

The final scientific run's own `run_manifest.json` independently records
`python_version = 3.12.10` and `sklearn_version = 1.9.0` — consistent with the
above.

## Consistency check vs repository dependency documentation

- `README.md` "Environment" and
  `docs/finalization/canonical_reproducibility_runbook.md` §1 both state
  Python 3.12.10 + the same lock-file SHA-256 + the same package list
  (numpy 2.3.5 / pandas 2.3.3 / scipy 1.16.3 / scikit-learn 1.9.0 / …). **No
  material mismatch** between the installed environment and the repository
  documentation was found at freeze time.
- Final-modeling code is not separately pinned in a requirements file — a
  documented, non-blocking gap (`docs/finalization/provisional_pipeline_lock.md`
  §7). In practice it runs in `.venv312` with the versions above.

## Notes

- No `pyproject.toml` / `environment.yml` is used by this project; the
  `requirements/` `.txt` lock is the single canonical spec.
- `.gitignore` blocks patient data by extension; no environment file contains
  credentials, tokens, or dataset paths beyond the repo-relative
  `data/raw/active/` convention. **This describes the canonical research
  repository's `.gitignore`**, which blocks essentially all `.csv`/`.xlsx`/
  `.ipynb` output by extension (patient-level and aggregate alike) — this
  submission does not use, and is not bound by, that blanket rule. This
  curated submission has its own narrower `.gitignore`: it intentionally
  tracks the approved, privacy-safe aggregate `.csv`/`.xlsx` tables and the
  six executed `.ipynb` notebooks under this package, while still excluding
  every patient-level path (raw/processed clinical workbooks, row-level
  out-of-fold predictions, delivery-id key sidecars — see the root
  `README.md` and `SUBMISSION_MANIFEST.md` for the exact exclusion list).
