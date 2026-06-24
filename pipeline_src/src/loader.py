# =============================================================================
# loader.py — Chargement, nettoyage de base et contrôles de cohérence
# =============================================================================
# Ce module :
#   1. Charge le fichier .dta depuis /input
#   2. Nettoie les types et codes manquants
#   3. Applique les contrôles de cohérence (outliers, incohérences logiques)
#   4. Retourne (df_clean, qc_log) — le log alimente le rapport QAQC
# =============================================================================

import os
import logging
import numpy as np
import pandas as pd
import pyreadstat

from config import (
    INPUT_DIR, INPUT_FILE,
    QC_AGE_MIN, QC_AGE_MAX, QC_TAILLE_MAX,
    QC_DUREE_QUARTIER_MAX, QC_MISSING_THRESH,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_numeric_or_nan(series):
    """Convertit proprement une série object (codes numériques stockés en str) en float."""
    return pd.to_numeric(series, errors="coerce")


def _flag_outlier(df, col, lo, hi, label, qc_log):
    """
    Met à NaN les valeurs hors bornes [lo, hi] et journalise.
    Retourne le df modifié.
    """
    mask = df[col].notna() & ((df[col] < lo) | (df[col] > hi))
    n = mask.sum()
    if n > 0:
        qc_log.append({
            "check": f"outlier_{col}",
            "description": f"{label} : valeurs hors [{lo}, {hi}]",
            "n_affected": int(n),
            "action": "Remplacé par NaN",
        })
        df.loc[mask, col] = np.nan
    return df


def _flag_incoherence(df, mask, label, action, qc_log):
    """Journalise une incohérence logique sans forcément modifier les données."""
    n = mask.sum()
    if n > 0:
        qc_log.append({
            "check": f"incoherence",
            "description": label,
            "n_affected": int(n),
            "action": action,
        })
    return n


# ---------------------------------------------------------------------------
# Chargement principal
# ---------------------------------------------------------------------------

def load_raw(filepath: str):
    """Charge le .dta et retourne (df, meta)."""
    logger.info(f"Chargement : {filepath}")
    df, meta = pyreadstat.read_dta(filepath)
    logger.info(f"Dimensions brutes : {df.shape[0]} lignes × {df.shape[1]} colonnes")
    return df, meta


# ---------------------------------------------------------------------------
# Nettoyage des types
# ---------------------------------------------------------------------------

def clean_types(df: pd.DataFrame, qc_log: list) -> pd.DataFrame:
    """
    - Convertit les colonnes object contenant des codes numériques en int/float
      (sauf les colonnes 'other' textuelles et les colonnes de codes-choix multiples
       qui doivent rester en string pour le mapping).
    - Remplace les chaînes vides par NaN.
    - Conserve les colonnes de type string multi-choix (III_17, II_1, II_2…).
    """
    df = df.copy()

    # Colonnes "other" textuelles : on garde en str, on nettoie juste les espaces
    other_cols = [c for c in df.columns if c.endswith("_other")]
    for col in other_cols:
        df[col] = df[col].astype(str).str.strip().replace({"": np.nan, "nan": np.nan})

    # Colonnes de codes stockés en string (catégoriels nominaux)
    # On les garde en string propre (sans espaces) pour que les mappings fonctionnent
    str_cat_cols = [
        "I_4", "I_7", "I_10", "II_3", "II_5", "II_22", "II_23",
        "III_4", "III_23", "III_26", "III_30", "Commune",
    ]
    for col in str_cat_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace({"": np.nan, "nan": np.nan})

    # Colonnes chaînes vides → NaN (colonnes multi-réponses textuelles)
    multichoix_cols = ["III_7", "III_9", "III_16", "III_20", "III_32", "III_33"]
    for col in multichoix_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace({"": np.nan, "nan": np.nan})

    # Variables continues : s'assurer qu'elles sont bien numériques
    num_cols = ["I_3", "I_9", "I_5_1", "I_5_2", "I_5_3", "I_5_4", "III_1"]
    for col in num_cols:
        if col in df.columns:
            df[col] = _to_numeric_or_nan(df[col])

    # I_5 (taille ménage totale) — stocké en str dans certaines éditions
    if "I_5" in df.columns:
        df["I_5"] = _to_numeric_or_nan(df["I_5"])

    # Colonnes de type Likert (int64 avec labels) : vérification minimale
    likert_cols = [
        "I_2", "I_6", "I_8", "I_11",
        "I_12_1", "I_12_2", "I_12_3", "I_12_4", "I_12_5",
        "II_4", "II_6", "II_7", "II_8", "II_11",
        "II_12_1", "II_12_2", "II_12_3", "II_12_4",
        "II_13", "II_14", "II_15", "II_16", "II_17", "II_18", "II_19", "II_20",
        "II_24", "II_25_1", "II_25_2",
        "III_1", "III_2", "III_3", "III_5", "III_6", "III_8",
        "III_10", "III_11", "III_12", "III_13", "III_14", "III_15",
        "III_18", "III_19", "III_21", "III_22", "III_24", "III_25", "III_27",
        "III_28", "III_29", "III_31",
    ]
    for col in likert_cols:
        if col in df.columns:
            df[col] = _to_numeric_or_nan(df[col])

    # Colonnes binaires 0/1 multi-sélection
    binary_cols = [c for c in df.columns if c.startswith("_v")]
    for col in binary_cols:
        df[col] = _to_numeric_or_nan(df[col])

    logger.info("Nettoyage des types terminé.")
    return df


# ---------------------------------------------------------------------------
# Contrôles de cohérence et outliers
# ---------------------------------------------------------------------------

def quality_checks(df: pd.DataFrame, qc_log: list) -> pd.DataFrame:
    """
    Applique les contrôles de qualité :
    - Outliers sur âges et tailles
    - Cohérences logiques (skip patterns)
    - Taux de manquants élevés
    """
    df = df.copy()

    # --- Outliers âge répondant ---
    df = _flag_outlier(df, "I_3", QC_AGE_MIN, QC_AGE_MAX,
                       "Âge répondant", qc_log)

    # --- Outliers âge CM ---
    df = _flag_outlier(df, "I_9", QC_AGE_MIN, QC_AGE_MAX,
                       "Âge chef de ménage", qc_log)

    # --- Taille ménage ---
    if "I_5" in df.columns:
        df = _flag_outlier(df, "I_5", 0, QC_TAILLE_MAX,
                           "Taille ménage totale", qc_log)

    # --- Durée dans le quartier (III_1 est binaire ici, pas de contrôle numérique) ---

    # --- Cohérence : si II_13 = 2 (pas de benne), II_14/16/17/18/19/20 doivent être NaN ---
    cols_benne_detail = ["II_14", "II_16", "II_17", "II_18", "II_19", "II_20"]
    mask_no_benne = df["II_13"] == 2
    for col in cols_benne_detail:
        if col in df.columns:
            incoherent = mask_no_benne & df[col].notna()
            _flag_incoherence(
                df, incoherent,
                f"Ménage sans benne (II_13=2) mais {col} renseigné",
                "Conservé — skip pattern non appliqué par l'enquêteur",
                qc_log,
            )

    # --- Cohérence : II_24 payant, mais II_25_1 manquant ---
    if "II_24" in df.columns and "II_25_1" in df.columns:
        mask_payant_sans_montant = (df["II_24"] == 1) & df["II_25_1"].isna()
        _flag_incoherence(
            df, mask_payant_sans_montant,
            "Service déclaré payant (II_24=1) mais montant manquant (II_25_1)",
            "Conservé comme NaN — montant inconnu",
            qc_log,
        )

    # --- Cohérence : II_8 = Non (ne revend pas), mais II_9 renseigné ---
    binary_v_rev = ["_v18", "_v19", "_v20", "_v21", "_v22"]
    if "II_8" in df.columns:
        mask_no_revente = df["II_8"] == 2
        for col in binary_v_rev:
            if col in df.columns:
                incoherent = mask_no_revente & (df[col] == 1)
                _flag_incoherence(
                    df, incoherent,
                    f"Pas de revente (II_8=2) mais {col}=1",
                    "Conservé — possible erreur de saisie",
                    qc_log,
                )

    # --- Cohérence : III_12 = Non (pas de dépôts sauvages), mais III_13/14 renseignés ---
    if "III_12" in df.columns:
        mask_no_depot = df["III_12"] == 3
        for col in ["III_13", "III_14"]:
            if col in df.columns:
                incoherent = mask_no_depot & df[col].notna()
                _flag_incoherence(
                    df, incoherent,
                    f"Pas de dépôt sauvage (III_12=3) mais {col} renseigné",
                    "Conservé — skip pattern",
                    qc_log,
                )

    # --- Taux de manquants par variable ---
    n = len(df)
    for col in df.columns:
        rate = df[col].isna().mean()
        if rate > QC_MISSING_THRESH:
            qc_log.append({
                "check": "missing_rate",
                "description": f"Variable '{col}' : {rate:.1%} de valeurs manquantes",
                "n_affected": int(df[col].isna().sum()),
                "action": "Alerte — à interpréter selon le skip pattern attendu",
            })

    logger.info(f"Contrôles qualité : {len(qc_log)} signalements générés.")
    return df


# ---------------------------------------------------------------------------
# Point d'entrée du module
# ---------------------------------------------------------------------------

def run(qc_log: list) -> tuple:
    """
    Charge, nettoie et contrôle les données.
    Retourne (df_clean, meta).
    """
    filepath = os.path.join(INPUT_DIR, INPUT_FILE)
    df, meta = load_raw(filepath)
    df = clean_types(df, qc_log)
    df = quality_checks(df, qc_log)
    return df, meta
