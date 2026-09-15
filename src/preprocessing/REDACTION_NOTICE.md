# Redaction Notice

This repository is the canonical public submission repository, and this preprocessing source is its privacy-redacted copy of the project preprocessing implementation.

It contains the preprocessing orchestration and general deterministic logic, but intentionally removes or neutralizes record-specific material that could expose or facilitate linkage to individual clinical records, including:

- literal record keys (`subject_number` / `delivery_id`) used for individual adjudications;
- patient-specific clinical/free-text excerpts and rationales;
- record-specific decision rows and exact values used only to verify manual corrections; and
- protected small-cell details that are not necessary to understand the preprocessing method.

Generic schema column names such as `subject_number` and `delivery_id` remain because they describe how the code joins and validates records; they are not patient identifiers by themselves.

Record-specific correction blocks are represented as redacted/no-op placeholders. Therefore this public repository copy is suitable for inspection of the preprocessing code and methodology, but it is **not** an executable substitute for the canonical private preprocessing source and cannot reproduce the complete raw-data pipeline exactly.

No raw or processed patient-level datasets, row-key sidecars, or row-level OOF predictions are included.
