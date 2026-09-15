# Preprocessing configuration: raw Excel column names → standardized variable names.
# Source of truth: docs/variable_documentation/active/ (single .xlsx file — see Active vs Archive Policy)
# Do NOT change standardized names without updating the documentation first.

import glob as _glob
import os as _os

# Anchored to this file's own location, not the process working directory
# (PARTNER-FIX-04, finding F-5), so raw-file discovery resolves the same
# canonical file regardless of the directory the caller was invoked from.
# This file lives at src/preprocessing/src/preprocessing_config.py, so
# the project root is 3 levels up.
_PROJECT_ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..", "..", ".."))


def _resolve_active_file(folder, label):
    """Return the single canonical .xlsx file in folder (resolved from the
    project root, not the process working directory), or raise a clear
    error. Ignores Excel temporary lock files (~$*.xlsx) and .gitkeep."""
    abs_folder = _os.path.join(_PROJECT_ROOT, folder)
    candidates = sorted(
        f for f in _glob.glob(_os.path.join(abs_folder, "*.xlsx"))
        if not f.endswith(".gitkeep") and not _os.path.basename(f).startswith("~$")
    )
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) == 0:
        raise FileNotFoundError(
            f"No .xlsx file found in '{abs_folder}'. "
            f"Place the current {label} file there before running."
        )
    raise RuntimeError(
        f"Multiple .xlsx files found in '{abs_folder}': {candidates}. "
        f"Move older files to the archive/ folder, keeping only the current {label}."
    )


# Raw dataset path — resolved from data/raw/active/, anchored to the
# project root (not the process working directory), at import time.
# active/ must contain exactly one .xlsx file (the current dataset).
# Move older datasets to data/raw/archive/ before running.
RAW_DATA_PATH = _resolve_active_file("data/raw/active", "raw dataset")

# Output paths (relative to project root)
OUTPUT_PROCESSED_PATH = "outputs/preprocessing/processed/"
OUTPUT_AUDIT_PATH = "outputs/preprocessing/audit/"
OUTPUT_REVIEW_PATH = "outputs/preprocessing/review/"
LOGS_PATH = "outputs/preprocessing/logs/"

# ---------------------------------------------------------------------------
# CURRENT APPROVED COHORT BASELINE (added 2026-08-16, centralization pass)
#
# This is a CURRENT FROZEN-COHORT REGRESSION GATE, not a permanent
# architectural invariant. It exists so preprocessing, EDA A, A2, Data
# Cleaning B, and EDA C can each fail loudly if their own live output
# unexpectedly drifts from the cohort the data owner most recently approved
# (Decision 67, 2026-08-15: 16 suspected-superficial-only-endometriosis
# exclusions, 447->431 rows, target 385/62->370/61). It is NOT the same kind
# of thing as e.g. "exactly one target column" or "no temporal leakage" --
# those are permanent structural invariants that never change; this value
# has already changed multiple times under approved clinical decisions
# (386/62 -> 385/62 -> 370/61) and will change again after a future
# supervisor-approved cohort revision.
#
# This is the single authoritative source for these three values. Every
# pipeline stage that needs to assert the current cohort/target counts
# imports them from here rather than independently declaring its own copy
# (previously duplicated across 6 files / 7 call sites -- see
# docs/clinical_decisions/manual_decisions_log.md, Decision 67 audit
# closure). Update this block ALONE, deliberately, after a future
# supervisor-approved cohort revision -- do not silently let a changed
# pipeline output redefine these values; a real revision should be a
# conscious edit here, immediately followed by every downstream stage's
# regression gate failing loudly until it is made.
#
# This module is preprocessing's own config file (zero dependencies outside
# the standard library, no import of anything under analysis/), so every
# downstream stage importing FROM here preserves the correct, one-directional
# pipeline dependency (preprocessing is upstream of everything); nothing
# here ever imports anything downstream.
CURRENT_APPROVED_COHORT_ROWS = 431
CURRENT_APPROVED_TARGET_N0 = 370
CURRENT_APPROVED_TARGET_N1 = 61
CURRENT_COHORT_DECISION = "Decision 67"
CURRENT_COHORT_AS_OF = "2026-08-15"

# Decision 32 (2026-07-29): protected small-cell cohort exclusion for a
# documented placenta_accreta/previa case. This count is a protected small
# cell (n<5) under this project's disclosure policy and must never appear as
# a literal in any rendered notebook cell's source or output -- only here, in
# a plain config module that is imported (never displayed) by the notebooks
# that need it. See docs/clinical_decisions/manual_decisions_log.md Decision 32.
DECISION_32_PLACENTA_EXCLUDED_ROWS = None  # exact protected small-cell count redacted in this public repository copy

# ---------------------------------------------------------------------------
# COLUMN MAPPING
# Each entry: (raw_name, standardized_name, mapping_type, notes)
#
# mapping_type values:
#   exact     – raw name and standardized name are identical (or trivially identical)
#   inferred  – standardized name derived from documentation heading, not from raw name directly
#   duplicate – raw name appears multiple times; resolved by context / neighboring columns
#   excluded  – internal-use column; kept in raw/reference but not used as a predictor
#
# IMPORTANT: match raw columns by NAME, not by index.
# ---------------------------------------------------------------------------

COLUMN_MAPPING = [
    # (raw_name,                                            standardized_name,                         mapping_type,  notes)
    ("NUM",                                                 "subject_number",                          "inferred",    "Patient ID. Not primary analysis ID; delivery_id created separately."),
    ("AGE",                                                 "AGE",                                     "exact",       ""),
    ("G",                                                   "G",                                       "exact",       "Gravida count."),
    ("nulliparity",                                         "nulliparity",                             "exact",       "1=nulliparous, 0=parous."),
    ("P",                                                   "P",                                       "exact",       "Parity count."),
    ("LIVE BIRTH",                                          "LIVE_BIRTH",                              "inferred",    ""),
    ("EUP",                                                 "EUP",                                     "exact",       ""),
    ("AB",                                                  "AB",                                      "exact",       ""),
    ("S/P CS",                                              "S_P_CS",                                  "inferred",    "Binary: 0=no prior CS, 1=prior CS. A clinically reviewed single-record correction is applied in Batch 3; record key redacted in this package."),
    ("CS",                                                  "CS",                                      "exact",       "Number of prior cesarean deliveries (ordinal)."),
    ("VBAC",                                                "VBAC",                                    "exact",       ""),
    ("smoking",                                             "smoking",                                 "exact",       "0=never, 1=current, 2=past. Keep 3-level; merge in EDA only."),
    ("alcohol",                                             "alcohol",                                 "exact",       ""),
    ("Any medical problem",                                 "any_medical_problem",                     "inferred",    ""),
    ("comment",                                             "any_medical_problem_comment",             "duplicate",   "Free-text comment adjacent to any_medical_problem. Direct raw-to-final mapping (Decision 34, 2026-07-29) -- no intermediate comment_1 name."),
    ("regular medications",                                 "regular_medications",                     "inferred",    ""),
    ("comment.1",                                           "regular_medications_comment",             "duplicate",   "Free-text comment adjacent to regular_medications. Direct raw-to-final mapping (Decision 34, 2026-07-29) -- no intermediate comment_2 name."),
    ("Fetus Anamoly",                                       "Fetus_Anamoly",                           "inferred",    ""),
    ("comments",                                            "Fetus_Anamoly_comment",                   "duplicate",   "Free-text comment adjacent to Fetus_Anamoly. Direct raw-to-final mapping (Decision 34, 2026-07-29) -- no intermediate comment_3 name."),
    ("deep",                                                "deep_endometriosis",                      "inferred",    ""),
    ("adenomyosis",                                         "adenomyosis",                             "exact",       "Binary existence variable. Will be corrected in Batch 6 using adenomyosis_sonographic_features_clean."),
    ("superficial",                                         "superficial_endometriosis",               "inferred",    "Keep; overlaps with peritoneal_endometriosis but agreement only ~63.2%; do not merge before EDA."),
    ("CLINICAL DIAGanosis only",                            "clinical_diagnosis_only",                 "inferred",    ""),
    ("endometriosis CS scar ",                              "cs_scar_endometriosis",                   "inferred",    "Note: raw name has trailing space."),
    ("peritoneal endometriosis",                            "peritoneal_endometriosis",                "inferred",    ""),
    ("diagnosis_date",                                      "diagnosis_date",                          "exact",       "Keep as-is. New column diagnosis_year will be created in Batch 5."),
    ("endometrioma",                                        "endometrioma",                            "exact",       "Primary existence variable. A clinically reviewed single-record QA correction is applied in Batch 7; record key redacted in this package."),
    ("endometrioma size",                                   "endometrioma_size",                       "inferred",    "Numeric size. Will be parsed in Batch 7."),
    ("endometrioma place",                                  "endometrioma_place",                      "inferred",    "Placement codes. endometrioma_place_clean and endometrioma_laterality will be created in Batch 7."),
    ("מאפיינים סונגרפיים של ADENOMYOSIS",                  "adenomyosis_sonographic_features",        "inferred",    "Multi-code field. adenomyosis_sonographic_features_clean will be created in Batch 6."),
    ("endometriosis surgery",                               "endometriosis_surgery",                   "inferred",    "Will be cleaned to binary in Batch 8; free text → endometriosis_surgery_comment."),
    ("ניתוח אנדו- הוסר",                                   "endo_resection_sites",                    "inferred",    "Raw multi-code/free-text field preserved unchanged. Batch 8 creates clinically grouped endo_resection_sites_clean and 10 grouped multi-hot columns."),
    ("האם הייתה פתיחת נרתיק בניתוח",                       "vaginal_opening_during_surgery",          "inferred",    ""),
    ("האם הוצא מוקד במעי",                                  "bowel_lesion_resected",                   "inferred",    ""),
    ("האם הוצא מוקד בשלופחית",                              "bladder_lesion_resected",                 "inferred",    ""),
    ("פירוט הניתוח",                                        "surgery_details",                         "inferred",    "Free-text surgical detail. Reference only; no automatic coding."),
    ("ניתוח אנדו- הפרדת הידבקויות ",                       "endo_surgery_adhesiolysis",                "inferred",    "Note: raw name has trailing space."),
    ("הערות",                                               "comment_1",                               "inferred",    "Free-text comment adjacent to endo surgery group. Renumbered from previous processed name comment_4 under Decision 57; generic comments now run consecutively from comment_1."),
    ("weight before pregnancy ",                            "weight_before_pregnancy",                 "inferred",    "Note: raw name has trailing space."),
    ("weight in pregnancy ",                                "weight_in_pregnancy",                     "inferred",    "Note: raw name has trailing space."),
    ("highth",                                              "height",                                  "inferred",    "Typo in raw name ('highth'). Standardized to height."),
    ("BMI before",                                          "BMI_before",                              "inferred",    ""),
    ("BMI after ",                                          "BMI_after",                               "inferred",    "Note: raw name has trailing space."),
    ("tretmetn - ASPIRIN during pregnancy",                 "aspirin_during_pregnancy",                "inferred",    "Typo in raw name ('tretmetn')."),
    ("Clexane during pregnancy\xa0",                        "clexane_during_pregnancy",                "inferred",    "Raw name contains non-breaking space (\\xa0)."),
    ("mode of conception",                                  "mode_of_conception",                      "inferred",    "Source/reference column. Do not delete, do not modify. mode_of_conception_ivf_vs_all is the preferred IVF candidate. Final selection deferred to EDA/modeling (Keren/Gidi, 2026-05-12)."),
    ("אופן כניסה להריון",                                   "mode_of_conception_details",              "inferred",    "Free-text detail of conception method. Reference."),
    ("mode of conception IVF VS all",                       "mode_of_conception_ivf_vs_all",           "inferred",    ""),
    ("PPROM",                                               "PPROM",                                   "exact",       ""),
    ("gestational age at PPROM",                            "gestational_age_at_PPROM",                "inferred",    "Will be normalized in Batch 11; gestational_age_at_PPROM_days will be derived."),
    ("hypertensive disorder only during pregnancy ",        "pregnancy_related_hypertensive_disorder", "inferred",    "Note: raw name has trailing space. 'only during' means distinct from pre-existing chronic hypertension."),
    ("PIH",                                                 "PIH",                                     "exact",       ""),
    ("mild PET",                                            "mild_PET",                                "inferred",    ""),
    ("SEVERE PET",                                          "severe_PET",                              "inferred",    ""),
    ("ANY PET",                                             "any_PET",                                 "inferred",    "Will be corrected deterministically in Batch 12 (23 missing → 0 where mild=0 and severe=0)."),
    ("SIPET",                                               "SIPET",                                   "exact",       ""),
    ("HELLP",                                               "HELLP",                                   "exact",       "All missing will be filled with 0 in Batch 12 (clinical justification: severe event would have been documented)."),
    ("Eclampsia",                                           "eclampsia",                               "inferred",    "All missing will be filled with 0 in Batch 12 (same justification as HELLP)."),
    ("gestational diabetes",                                "gestational_diabetes",                    "inferred",    ""),
    (" diabetes-type",                                      "diabetes_type",                           "inferred",    "Note: raw name has leading space."),
    ("IUGR",                                                "IUGR",                                    "exact",       ""),
    ("placental abruption",                                 "placental_abruption",                     "inferred",    ""),
    ("placenta accreta",                                    "placenta_accreta",                        "inferred",    ""),
    ("placenta previa",                                     "placenta_previa",                         "inferred",    ""),
    ("CHORIOAMNIONITIS",                                    "chorioamnionitis",                        "inferred",    ""),
    ("PPH",                                                 "PPH",                                     "exact",       ""),
    ("OLIGOHYDRAMNION",                                     "oligohydramnios",                         "inferred",    ""),
    ("POLYHYDRAMNION",                                      "polyhydramnios",                          "inferred",    ""),
    ("meconium stained amniotic fluid",                     "meconium_stained_amniotic_fluid",         "inferred",    ""),
    ("IUFD",                                                "IUFD",                                    "exact",       ""),
    ("celestone",                                           "celestone",                               "exact",       ""),
    ("magnesium",                                           "magnesium",                               "exact",       ""),
    ("comments.1",                                          "comment_2",                               "duplicate",   "Free-text comment adjacent to celestone/magnesium group. Renumbered from previous processed name comment_5 under Decision 57."),
    ("gestational age at delivery",                         "gestational_age_at_delivery",             "inferred",    "Will be normalized in Batch 11; gestational_age_at_delivery_days will be derived."),
    ("induction of labor",                                  "induction_of_labor",                      "inferred",    "Multi-code field. Used with start_of_labor to derive induction_any_bin in Batch 14."),
    ("start of labor",                                      "start_of_labor",                          "inferred",    "Multi-code field. Used with induction_of_labor to derive induction_any_bin."),
    ("indication for induction ",                           "indication_for_induction",                "inferred",    "Note: raw name has trailing space. Batch 14 normalizes this into indication_for_induction_clean (multi-code string, sorted/deduped); it does not generate multi-hot/dummy variables. Rare-category grouping or later encoding remains deferred to future EDA/model design (Decision 26)."),
    ("CS-caseVScontrol",                                    "CS_case_vs_control",                      "inferred",    "Post-event leakage variable. Keep for reference; exclude from model."),
    ("comment.2",                                           "comment_3",                               "duplicate",   "Free-text comment adjacent to CS_case_vs_control. Renumbered from previous processed name comment_6 under Decision 57."),
    ("trial of labor",                                      "trial_of_labor",                          "inferred",    "Cohort definition variable. Corrected version trial_of_labor_corrected will be created in Batch 2."),
    ("Type of CS",                                         "type_of_CS",                              "inferred",    "Source for target variable. Keep for reference; exclude from model."),
    ("indication for CS",                                  "indication_for_CS",                       "inferred",    "Post-event leakage. CS subgroup only. Batch 15 creates indication_for_CS_clean, normalizing multiple indication codes into a consistent comma-separated representation; no code-specific multi-hot variables are currently generated (any future one-hot/multi-hot encoding is deferred to later descriptive or model-design work). The variable and all derivatives are excluded from the primary pre-labor model because they depend on the cesarean decision or outcome."),
    ("comment.3",                                           "comment_4",                               "duplicate",   "Free-text comment adjacent to indication_for_CS. Renumbered from previous processed name comment_7 under Decision 57."),
    ("האם בניתוח הCS נצפו נגעים חשודים לאנדומטרזיוס",     "suspected_endo_lesions_during_CS",        "inferred",    "CS subgroup only. Vaginal deliveries → NaN in Batch 15."),
    ("ממצאים בחלל הבטן",                                   "abdominal_cavity_findings",               "inferred",    "CS subgroup only."),
    ("surgery dehiscence",                                  "surgery_dehiscence",                      "inferred",    "Post-event leakage. CS subgroup only."),
    ("Other surgery complications",                         "other_surgery_complications",             "inferred",    "Post-event leakage."),
    ("adhesions",                                           "adhesions",                               "exact",       ""),
    ("comments.2",                                          "comment_5",                               "duplicate",   "Free-text comment adjacent to surgery/adhesions group. Renumbered from previous processed name comment_8 under Decision 57."),
    ("כמות דימום-בניתוח",                                  "blood_loss_during_surgery",               "inferred",    "Post-event leakage."),
    ("Hb before delivery",                                  "Hb_before_delivery",                      "inferred",    ""),
    ("Hb after delivery",                                   "Hb_after_delivery",                       "inferred",    ""),
    ("Hb diff",                                             "Hb_diff",                                 "inferred",    "Post-event leakage."),
    ("intrapartum fever",                                   "intrapartum_fever",                       "inferred",    "Post-event leakage."),
    ("postpartum fever",                                    "postpartum_fever",                        "inferred",    "Post-event leakage."),
    ("surgical site infection",                             "surgical_site_infection",                 "inferred",    "Post-event leakage."),
    ("endometritis",                                        "endometritis",                            "exact",       "Post-event leakage."),
    ("Any blood transfusion (including cryo and plasma)",   "any_blood_product_transfusion",           "inferred",    "Post-event leakage."),
    ("Hospitalization days",                                "hospitalization_days",                    "inferred",    "Post-event leakage."),
    ("comment.4",                                           "comment_6",                               "duplicate",   "Free-text comment adjacent to hospitalization_days. Renumbered from previous processed name comment_9 under Decision 57."),
    ("gender",                                              "gender",                                  "exact",       ""),
    ("PH-vein",                                             "pH_vein",                                 "inferred",    ""),
    ("PH-Artery",                                           "pH_artery",                               "inferred",    ""),
    ("PH-artery less then 7.1",                             "pH_artery_or_vein_less_than_7_1",         "inferred",    "Raw header is historically artery-only-worded, but clinical review confirmed the field represents artery-OR-vein pH < 7.1 (Decision 50). Batch 17 recalculates the processed variable from the continuous pH_artery/pH_vein measurements; the raw binary field is retained only as source/audit evidence and is not treated as authoritative."),
    ("apgar1",                                              "apgar1",                                  "exact",       "Post-event leakage."),
    ("apgar5",                                              "apgar5",                                  "exact",       "Post-event leakage."),
    ("APGAR 5 less then 7",                                 "apgar_5_less_than_7",                     "inferred",    ""),
    ("birth weight",                                        "birth_weight",                            "inferred",    ""),
    ("percentile by דולברג",                               "percentile_by_Dolberg",                   "inferred",    ""),
    ("SGA",                                                 "SGA",                                     "exact",       ""),
    ("LGA",                                                 "LGA",                                     "exact",       ""),
    ("IVH",                                                 "IVH",                                     "exact",       ""),
    ("IVH grade 1-2",                                       "IVH_grade_1_2",                           "inferred",    ""),
    ("IVH grade 3-4",                                       "IVH_grade_3_4",                           "inferred",    ""),
    ("niccu admission",                                     "NICU_admission",                          "inferred",    "Typo in raw name ('niccu')."),
    ("RDS",                                                 "RDS",                                     "exact",       ""),
    ("mechanical ventilation",                              "mechanical_ventilation",                  "inferred",    ""),
    ("lenth of mechanical ventilation",                     "length_of_mechanical_ventilation",        "inferred",    "Typo in raw name ('lenth')."),
    ("NEC",                                                 "NEC",                                     "exact",       ""),
    ("sepsis",                                              "sepsis",                                  "exact",       ""),
    ("hypoglycemia",                                        "hypoglycemia",                            "exact",       ""),
    ("neonatal jaundice used phototherapy",                 "neonatal_jaundice_used_phototherapy",     "inferred",    ""),
    ("neonatal death",                                      "neonatal_death",                          "inferred",    ""),
    ("age at neonatal death",                               "age_at_neonatal_death",                   "inferred",    ""),
    ("congenital anomaly",                                  "congenital_anomaly",                      "inferred",    ""),
    ("congenital anomaly - comment",                        "congenital_anomaly_comment",              "inferred",    ""),
    ("long term outcome",                                   "long_term_outcome",                       "inferred",    ""),
    ("long term outcome - comment",                         "long_term_outcome_comment",               "inferred",    ""),
    ("צורת הלידה",                                         "delivery_mode",                           "excluded",    "Internal-use column. Not a predictor. Excluded from modeling dataset."),
    ("comments.3",                                          "comment_10",                              "duplicate",   "Free-text comment. Last generic comment column before Status. Documentation had comment_11 (old numbering); corrected to comment_10 as there are exactly 10 generic comment columns in current dataset."),
    ("Status",                                              "Status",                                  "excluded",    "Internal-use column. Not a predictor. Excluded from modeling dataset."),
]

# Variables documented but NOT present in current dataset
VARS_NOT_IN_DATASET = [
    {
        "standardized_name": "neonatal_id",
        "documented_raw_name": "neonatal ID",
        "reason": "Column does not exist in data 24.4.26.xlsx. Documentation confirms this variable was removed from the updated dataset. Do not create synthetically unless explicitly requested.",
    },
    {
        "standardized_name": "Infant_birth_date",
        "documented_raw_name": "Unnamed / blank header in source file",
        "reason": "Documentation states this column is no longer relevant in the updated dataset. Not present in data 24.4.26.xlsx.",
    },
]

# Post-event / leakage variables (must not be used as model inputs).
#
# Reference/documentation list only — NOT wired into pipeline execution.
# The authoritative leakage classification that actually reaches
# variable_classification_minimal.csv is the `leakage_exclude` group built
# directly inside batch_19_qa_inventory_and_classification()
# (run_preprocessing.py, classification_groups). This list predates that
# mechanism and is not automatically kept in sync with it: for example it
# still names "surgery_dehiscence", which was removed from the analytical
# dataset entirely (Decision 33) and can no longer appear in any output.
# Kept here as a human-readable reference; verify against
# variable_classification_minimal.csv for the current, authoritative set.
LEAKAGE_VARS = [
    "indication_for_CS",
    "blood_loss_during_surgery",
    "Hb_diff",
    "surgery_dehiscence",
    "surgical_site_infection",
    "intrapartum_fever",
    "postpartum_fever",
    "apgar1",
    "apgar5",
    "pH_artery",
    "hospitalization_days",
    "CS_case_vs_control",
    "other_surgery_complications",
    "endometritis",
    "any_blood_product_transfusion",
]

# Internal-use columns (excluded from modeling dataset).
#
# Reference/documentation list only — NOT wired into pipeline execution.
# The columns that are actually dropped from the working DataFrame are
# controlled by the separate, local `_INTERNAL_USE_COLS` list defined
# inside batch_2_cohort_target() (run_preprocessing.py). That list is the
# authoritative one for physical column removal; it currently drops
# "delivery_mode", "Status", "comment_10", "clinical_diagnosis_only", and
# "surgery_dehiscence" (Decision 33), which only partially overlaps with
# the list below. "type_of_CS" and "CS_case_vs_control" here are NOT
# physically dropped — they are retained in the dataset and excluded from
# the predictor pool only via their variable_classification_minimal.csv
# classification (target-source / leakage_exclude respectively).
INTERNAL_USE_VARS = [
    "delivery_mode",
    "Status",
    "type_of_CS",   # Source for target; not a predictor
    "CS_case_vs_control",  # Also leakage
]

# Planned QA corrections (not yet implemented; documented here for traceability)
PLANNED_QA_CORRECTIONS = [
    {
        "variable": "S_P_CS",
        "issue": "Single-record binary inconsistency identified during clinical QA",
        "affected_subject_number": None,
        "action": "Approved record-specific correction; identifier redacted",
        "reason": "Record-level key and rationale are withheld from this privacy-redacted package.",
        "batch": "Batch 3 (obstetric history)",
        "requires_approval": False,
    },
    {
        "variable": "endometrioma",
        "issue": "Single-record inconsistency identified from supporting clinical fields",
        "affected_subject_number": None,
        "action": "Approved record-specific correction; identifier redacted",
        "reason": "Record-level key and rationale are withheld from this privacy-redacted package.",
        "batch": "Batch 7 (endometrioma group)",
        "requires_approval": False,
    },
    {
        "variable": "adenomyosis",
        "issue": "Single-record inconsistency identified during clinical review",
        "affected_subject_number": None,
        "action": "Approved record-specific correction; identifier and source excerpt redacted",
        "reason": "Record-level key and patient-specific source excerpt are withheld from this privacy-redacted package.",
        "batch": "Batch 6 (adenomyosis group)",
        "requires_approval": False,
    },
]
