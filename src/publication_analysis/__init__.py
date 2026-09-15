"""Publication / inferential-analysis namespace.

This package is a strictly separate, read-only-with-respect-to-modeling
companion to the canonical predictive modeling pipeline
(``analysis/modeling/final_modeling/``). It builds descriptive,
univariable-association, and adjusted-association reporting for the
project book / manuscript.

Hard boundaries (see module docstrings for detail):

- No module in this package imports from, executes, or writes under
  ``analysis/modeling/final_modeling/`` or ``outputs/final_modeling/``.
  The single permitted exception is a read-only load of the hand-authored
  ``ENDOMETRIOSIS_FAMILY_RATIONALE`` registry in
  ``analysis/modeling/final_modeling/endometriosis_family.py``, done via
  ``importlib`` file-path loading (never a package import) so that loading
  it cannot trigger any other code in that package.
- No module in this package fits, tunes, or re-executes the predictive
  model. Predictive-model context is a read-only consumer of persisted,
  already-written artifacts (see ``predictive_context_loaders.py``).
- All file writes in this package are validated to land under
  ``outputs/publication_analysis/`` (see ``publication_exports.py``).

This is an association / descriptive analysis, not a causal analysis.
Do not use causal language ("causes", "effect of", "independent causal
effect") in code comments, docstrings, or generated notebook text — use
"association", "adjusted association", "predictive contribution",
"incremental predictive value", or "exploratory finding".
"""
