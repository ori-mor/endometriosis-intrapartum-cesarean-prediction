"""ONE publication-facing clinical display-label layer.

Tables and figures intended for manuscript/project-book reading should not
rely only on the internal Python variable name where a documented clinical
meaning already exists elsewhere in the repository. This module never
renames the actual dataframe/source variables and never invents a clinical
meaning that is not already documented — a predictor without an entry here
falls back to its bare technical name unchanged.

Labels below are restated (not invented) from clinical descriptions already
approved and documented in ``CLAUDE.md`` / the publication representation
contract's own ``clinical_unit`` / ``reason`` fields / the Compact Ridge
locked artifacts. Extending this dictionary with a new predictor requires a
documented English clinical source — never a guess.
"""
from __future__ import annotations

import pandas as pd

# predictor (technical, analysis-matrix column name) -> clinical display label.
# Deliberately partial: only predictors with an unambiguous, already-documented
# English clinical description are listed. See module docstring.
DISPLAY_LABELS: dict[str, str] = {
    "AGE": "Maternal age",
    "BMI_before": "Pre-pregnancy BMI",
    "BMI_after": "BMI near delivery",
    "weight_before_pregnancy": "Weight before pregnancy",
    "weight_in_pregnancy": "Weight in pregnancy",
    "height": "Height",
    "nulliparity": "Nulliparity",
    "G": "Gravidity (number of pregnancies)",
    "P": "Parity (number of previous deliveries)",
    "AB": "Prior abortions/miscarriages",
    "CS": "Number of prior cesarean sections",
    "S_P_CS": "Status post previous cesarean section",
    "LIVE_BIRTH": "Number of prior live births",
    "induction_any_bin": "Labor induction (any)",
    "indication_for_induction_status": "Indication for labor induction",
    "mode_of_conception": "Mode of conception",
    "mode_of_conception_ivf_vs_all": "Conception via IVF (vs. all other modes)",
    "smoking": "Smoking status",
    "Hb_before_delivery": "Hemoglobin before delivery",
    "gestational_age_at_delivery_days": "Gestational age at delivery (days)",
    "derived_hypertension_pih_pet_spectrum": "Hypertensive disease spectrum (PIH/PET)",
    "severe_PET_cat": "Severe pre-eclampsia",
    "any_PET_cat": "Any pre-eclampsia",
    "endometriosis_surgery": "Prior endometriosis surgery",
    "endometrioma": "Endometrioma present",
    "endometrioma_size_status": "Endometrioma size category",
    "endometrioma_presence_laterality": "Endometrioma laterality",
    "endo_surgery_adhesiolysis": "Prior endometriosis-related adhesiolysis",
    "derived_endo_surgery_adhesion_status": "Documented adhesion status at prior endometriosis surgery",
    "oligohydramnios": "Oligohydramnios",
    "celestone": "Antenatal corticosteroids (Celestone)",
    "IUFD": "Intrauterine fetal death",
    "gender": "Fetal sex",
    # --- Extended 2026-09-05 targeted correction pass: sourced from
    # CLAUDE.md's already-approved English clinical text and from the
    # repository's own data dictionary (docs/data_dictionary/
    # clinical_variable_dictionary.yaml, description_he field) via a direct,
    # conservative translation of short, unambiguous, non-coded entries only.
    # Sonographic/coded fields with any translation ambiguity (e.g. the
    # adenomyosis_feature_* ultrasound-finding codes, derived_* composite
    # variables whose exact construction is not restated here) are
    # deliberately left as fallback technical names rather than guessed.
    "EUP": "History of ectopic pregnancy",
    "VBAC": "Vaginal birth after cesarean (VBAC)",
    "Fetus_Anamoly": "Fetal anomaly detected before delivery (current pregnancy)",
    "deep_endometriosis": "Deep infiltrating endometriosis phenotype",
    "adenomyosis": "Adenomyosis (presence)",
    "cs_scar_endometriosis": "Endometriosis in prior cesarean-section scar",
    "peritoneal_endometriosis": "Peritoneal endometriosis phenotype",
    "vaginal_opening_during_surgery": "Vaginal opening performed during endometriosis surgery",
    "bowel_lesion_resected": "Bowel endometriosis lesion resected",
    "bladder_lesion_resected": "Bladder endometriosis lesion resected",
    "aspirin_during_pregnancy": "Aspirin treatment during pregnancy",
    "clexane_during_pregnancy": "Clexane (low-molecular-weight heparin) treatment during pregnancy",
    "PPROM": "Preterm prelabor rupture of membranes (PPROM)",
    "gestational_age_at_PPROM_days": "Gestational age at PPROM (days)",
    "pregnancy_related_hypertensive_disorder": "Pregnancy-related hypertensive disorder (any)",
    "PIH": "Gestational hypertension (PIH), without proteinuria",
    "mild_PET": "Mild preeclampsia",
    "SIPET": "Superimposed preeclampsia (chronic hypertension with new-onset preeclampsia)",
    "gestational_diabetes": "Gestational diabetes",
    "IUGR": "Intrauterine growth restriction (IUGR)",
    "placental_abruption": "Placental abruption",
    "polyhydramnios": "Polyhydramnios (excess amniotic fluid)",
    "meconium_stained_amniotic_fluid": "Meconium-stained amniotic fluid",
    "magnesium": "Magnesium sulfate administration (neuroprotection)",
    "intrapartum_fever_or_chorioamnionitis_bin": "Intrapartum fever or chorioamnionitis",
    "endo_resection_no_resection": "No endometriosis lesion resected",
    "endo_resection_ovarian_endometrioma_unilateral": "Unilateral ovarian endometrioma resected",
    "endo_resection_ovarian_endometrioma_bilateral": "Bilateral ovarian endometrioma resected",
    "endo_resection_adnexa": "Adnexal endometriosis lesion resected",
    "endo_resection_fallopian_tube": "Fallopian tube endometriosis lesion resected",
    "endo_resection_uterus": "Uterine endometriosis lesion resected",
    "endo_resection_lesion": "Other endometriosis lesion resected (unspecified site)",
    "endo_resection_adhesiolysis": "Adhesiolysis performed at prior endometriosis surgery",
    "endo_resection_appendix": "Appendiceal endometriosis lesion resected",
    # --- Extended 2026-09 targeted closure pass: the 17 predictors that
    # previously fell back to their bare technical name. Every label below is
    # restated (never invented) from an already-approved, already-documented
    # source:
    #  - adenomyosis_feature_1..11 / adenomyosis_features_unknown: one
    #    binary indicator per documented sonographic-feature code, source
    #    docs/data_dictionary/clinical_variable_dictionary.yaml, entry
    #    "adenomyosis_sonographic_features", codes_he 1-11 (confirmed 1:1
    #    code<->column mapping: ADENOMYOSIS_FEATURE_CODES = range(1, 12) in
    #    cleaning_b_part4_transformations_imputation_plan.py). Hebrew source
    #    text translated conservatively into standard sonographic
    #    (MUSA-criteria-equivalent) terminology, never reinterpreted.
    #  - derived_placental_dysfunction_proxy: restated directly from its own
    #    documented construction rule in
    #    analysis/eda/notebook_build/eda_c/eda_c_part3_feature_engineering.py
    #    ("1 if any_PET_cat=='present' OR IUGR==1; 0 if both absent") --
    #    explicitly NOT a validated clinical score.
    #  - derived_diabetes_type_grouped: restated from its documented
    #    deterministic coarsening of diabetes_type
    #    (analysis/eda/notebook_build/eda_c/contracts/model_coentry_constraints.yaml:
    #    "{0->no_diabetes, 1/2/3->pregestational, 4->GDMA1, 5->GDMA2}").
    #  - derived_prior_endo_surgery_procedure_status: restated from its
    #    documented construction rule (same eda_c_part3 file); mirrors the
    #    existing sibling label style already used for
    #    derived_endo_surgery_adhesion_status above.
    #  - diabetes_type: raw source column label; its 6 raw numeric CODES
    #    (0-5) are separately translated for Table 1 display via
    #    publication_representations._RAW_CODE_TO_LABEL['diabetes_type']
    #    (display-only, never mutates the analysis matrix or feeds any fit --
    #    diabetes_type remains DESCRIPTIVE_ONLY / NOT_FITTED throughout).
    #  - endo_resection_epiploica: docs/data_dictionary/
    #    clinical_variable_dictionary.yaml, entry "endo_resection_sites",
    #    codes_he item 8 ("אפיפלואיקה" = epiploic appendage); mirrors the
    #    existing sibling endo_resection_* label style.
    "adenomyosis_feature_1": "Adenomyosis sonographic finding: globular uterine configuration",
    "adenomyosis_feature_2": 'Adenomyosis sonographic finding: "question-mark"-shaped uterine contour',
    "adenomyosis_feature_3": "Adenomyosis sonographic finding: myometrial wall asymmetry",
    "adenomyosis_feature_4": "Adenomyosis sonographic finding: echogenic myometrial islands / increased echogenicity",
    "adenomyosis_feature_5": "Adenomyosis sonographic finding: myometrial cysts",
    "adenomyosis_feature_6": "Adenomyosis sonographic finding: junctional zone irregularity",
    "adenomyosis_feature_7": "Adenomyosis sonographic finding: junctional zone thickening",
    "adenomyosis_feature_8": "Adenomyosis sonographic finding: echogenic subendometrial buds (junctional zone)",
    "adenomyosis_feature_9": "Adenomyosis sonographic finding: fan-shaped shadowing",
    "adenomyosis_feature_10": "Adenomyosis sonographic finding: ill-defined endometrial-myometrial border",
    # Source codes_he item 11 itself flags this finding as non-specific ("also
    # written for findings unrelated to endo[metriosis]") -- the caveat is
    # kept in the label rather than silently dropped.
    "adenomyosis_feature_11": "Adenomyosis sonographic finding: diffuse myometrial vascularity (non-specific finding per source documentation)",
    "adenomyosis_features_unknown": "Adenomyosis sonographic finding: unspecified/not documented",
    "derived_placental_dysfunction_proxy": "Placenta-mediated complication proxy (pre-eclampsia or IUGR present)",
    "derived_diabetes_type_grouped": "Diabetes type (grouped: pregestational vs. gestational)",
    "derived_prior_endo_surgery_procedure_status": "Documented procedure status at prior endometriosis surgery",
    "diabetes_type": "Diabetes type (raw source coding)",
    "endo_resection_epiploica": "Epiploic-appendage endometriosis lesion resected",
}


def display_label(predictor: str) -> str:
    """The approved clinical display label for ``predictor``, or the bare
    technical name unchanged if no documented label exists (never a guess)."""
    return DISPLAY_LABELS.get(predictor, predictor)


def add_display_label_column(
    df: pd.DataFrame, predictor_col: str = "predictor", label_col: str = "clinical_display_label",
) -> pd.DataFrame:
    """Return a copy of ``df`` with an added ``label_col`` mapped from
    ``predictor_col`` via ``display_label``. The technical ``predictor_col``
    is left untouched alongside it (traceability) — this never replaces or
    renames the technical column."""
    out = df.copy()
    out[label_col] = out[predictor_col].map(display_label)
    return out
