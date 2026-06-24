# =============================================================================
# builder.py — Construction des variables analytiques thématiques
# =============================================================================
# Ce module transforme les variables brutes (codes numériques, multi-select, etc.)
# en variables propres, labellisées et dérivées, organisées en 4 blocs :
#   A. Caractéristiques du ménage
#   B. Caractéristiques du Chef de Ménage
#   C. Déchets ménagers
#   D. Conséquences et perception
#
# Principe de scalabilité : toutes les étiquettes sont dans config.py.
# Pour une nouvelle édition : mettre à jour config.py, ce module reste stable.
# =============================================================================

import logging
import numpy as np
import pandas as pd

from config import (
    SEXE, STATUT_REPONDANT, STATUT_OCCUPATION, TYPE_LOGEMENT,
    TYPE_ENSEIGNEMENT_CM, NIVEAU_INSTRUCTION_CM, ALPHA_CM,
    MODE_STOCKAGE, PLACE_STOCKAGE, PROPORTION_TRAITEE, TRAITEMENT_PRATIQUE,
    ACCES_BENNE, SERVICE_COLLECTE_ALTERNATIF, RAISON_SERVICE_ALTERNATIF,
    SATISFACTION_COLLECTE, MONTANT_EVACUATION, FREQUENCE_PAIEMENT,
    MONTANT_MEDIAN_FCFA, FREQ_TO_MONTHLY,
    SATISFACTION_4PT, FREQUENCE_COMPORTEMENT, GESTIONNAIRE_PLACE,
    VARS_ABSENTES,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers génériques
# ---------------------------------------------------------------------------

def _map(series, mapping, default=np.nan):
    """Applique un dictionnaire de mapping à une série, NaN si absent."""
    return series.map(mapping).where(series.notna(), default)


def _oui_non(series):
    """Convertit 1→Oui, 2→Non, autre→NaN."""
    return series.map({1: "Oui", 2: "Non"})


def _satisfaction4(series):
    return _map(series, SATISFACTION_4PT)


def _binary_flag(series):
    """0/1 binaire : retourne la série telle quelle après cast int."""
    return series.fillna(0).astype(int)


def _concat_binary_flags(df, cols, sep=" | "):
    """
    Construit une chaîne textuelle des libellés des colonnes binaires = 1.
    Ex : pour les maladies, sources de déchets, etc.
    cols : list of (col_name, label)
    """
    def row_labels(row):
        labels = [lbl for col, lbl in cols if row.get(col, 0) == 1]
        return sep.join(labels) if labels else np.nan
    return df.apply(row_labels, axis=1)


# ---------------------------------------------------------------------------
# BLOC A — Caractéristiques du Ménage
# ---------------------------------------------------------------------------

def build_menage(df: pd.DataFrame) -> pd.DataFrame:
    """Construit les variables de caractéristiques du ménage."""
    out = pd.DataFrame(index=df.index)

    # Identifiants géographiques disponibles
    out["commune_code"]    = df["Commune"].astype(str).str.strip()
    out["quartier"]        = df["quartier"].astype(str).str.strip().replace({"nan": np.nan})

    # Variables absentes — noter NaN avec documentation
    for var in ["region", "departement", "milieu_residence"]:
        out[var] = np.nan  # voir VARS_ABSENTES dans config.py

    # Taille du ménage
    composantes = ["I_5_1", "I_5_2", "I_5_3", "I_5_4"]
    if all(c in df.columns for c in composantes):
        out["nb_enfants_0_4"]   = df["I_5_1"].fillna(0).astype(int)
        out["nb_enfants_5_15"]  = df["I_5_2"].fillna(0).astype(int)
        out["nb_adultes_H"]     = df["I_5_3"].fillna(0).astype(int)
        out["nb_adultes_F"]     = df["I_5_4"].fillna(0).astype(int)

    if "I_5" in df.columns:
        out["taille_menage"] = df["I_5"]
    else:
        # Recalcul si I_5 manquant
        out["taille_menage"] = (
            df.get("I_5_1", 0).fillna(0) +
            df.get("I_5_2", 0).fillna(0) +
            df.get("I_5_3", 0).fillna(0) +
            df.get("I_5_4", 0).fillna(0)
        )

    # Statut d'occupation du logement
    out["statut_occupation"]  = _map(df["I_6"], STATUT_OCCUPATION)

    # Type de logement (habitat)
    out["type_habitat"]       = _map(df["I_7"].astype(str), TYPE_LOGEMENT)

    # PROXY niveau de vie (dépenses + actifs non collectés directement)
    # Construit à partir de : type_habitat, statut_occupation, montant payé déchets
    # Score de 0 à 3 : 1 pt chacun si propriétaire, si logement structuré (villa/appart), si service payant
    proxy = pd.Series(0, index=df.index)
    proxy += (df["I_6"] == 2).astype(int)                        # propriétaire
    proxy += df["I_7"].astype(str).isin(["1", "2"]).astype(int)  # villa ou appart
    proxy += (df["II_24"] == 1).astype(int)                      # paie pour déchets
    out["proxy_niveau_vie"] = proxy
    out["proxy_niveau_vie_label"] = proxy.map({
        0: "Faible", 1: "Moyen-bas", 2: "Moyen-haut", 3: "Élevé"
    })

    logger.info(f"Bloc A (ménage) : {out.shape[1]} variables construites.")
    return out


# ---------------------------------------------------------------------------
# BLOC B — Caractéristiques du Chef de Ménage
# ---------------------------------------------------------------------------

def build_cm(df: pd.DataFrame) -> pd.DataFrame:
    """Construit les variables du Chef de Ménage."""
    out = pd.DataFrame(index=df.index)

    out["cm_sexe"]              = _map(df["I_8"], SEXE)
    out["cm_age"]               = df["I_9"]

    # Groupe d'âge CM
    bins   = [0, 25, 35, 45, 60, 200]
    labels = ["Moins de 25 ans", "25-34 ans", "35-44 ans", "45-59 ans", "60 ans et plus"]
    out["cm_tranche_age"] = pd.cut(
        df["I_9"], bins=bins, labels=labels, right=False
    ).astype(object).where(df["I_9"].notna(), np.nan)

    # Statut du répondant par rapport au CM
    out["repondant_statut"]     = _map(df["I_4"].astype(str), STATUT_REPONDANT)
    out["repondant_est_cm"]     = (df["I_4"].astype(str) == "1").map({True: "Oui", False: "Non"})

    # Niveau d'études
    out["cm_branche_etudes"]    = _map(df["I_10"].astype(str), TYPE_ENSEIGNEMENT_CM)
    out["cm_niveau_etudes"]     = _map(df["I_11"], NIVEAU_INSTRUCTION_CM)

    # Alphabétisation (multilingue) — consolider en variable synthétique
    alpha_cols = {
        "I_12_1": "Français",
        "I_12_2": "Anglais",
        "I_12_3": "Arabe",
        "I_12_4": "Langue nationale",
        "I_12_5": "Autre langue étrangère",
    }
    out["cm_alpha_francais"]    = _map(df["I_12_1"], ALPHA_CM)
    out["cm_alpha_anglais"]     = _map(df["I_12_2"], ALPHA_CM)
    out["cm_alpha_arabe"]       = _map(df["I_12_3"], ALPHA_CM)
    out["cm_alpha_lng_nat"]     = _map(df["I_12_4"], ALPHA_CM)

    # Alphabétisé dans au moins une langue ?
    alpha_bin = pd.DataFrame({
        lang: (df[col] == 1).astype(float) for col, lang in alpha_cols.items()
        if col in df.columns
    })
    out["cm_est_alphabetise"] = alpha_bin.max(axis=1).map({1.0: "Oui", 0.0: "Non"})

    # Situation matrimoniale — non collectée directement
    out["cm_situation_matrimoniale"] = np.nan  # absent du questionnaire

    # Statut d'emploi du répondant (I_6 = statut occupation logement, pas emploi)
    # Le questionnaire ne collecte pas directement le statut emploi ni secteur du CM
    out["cm_statut_emploi"]  = np.nan  # absent — voir VARS_ABSENTES
    out["cm_secteur_emploi"] = np.nan  # absent
    out["cm_revenu"]         = np.nan  # absent — proxy dans bloc ménage

    logger.info(f"Bloc B (CM) : {out.shape[1]} variables construites.")
    return out


# ---------------------------------------------------------------------------
# BLOC C — Déchets Ménagers
# ---------------------------------------------------------------------------

def build_dechets(df: pd.DataFrame) -> pd.DataFrame:
    """Construit les variables sur la gestion des déchets."""
    out = pd.DataFrame(index=df.index)

    # --- Sources de déchets (multi-select _v1 à _v7) ---
    sources = [
        ("_v1", "Consommation alimentaire / cuisine"),
        ("_v2", "Gestion foyer hors alimentation"),
        ("_v3", "Élevage"),
        ("_v4", "Animaux domestiques"),
        ("_v5", "Entretien du logement"),
        ("_v6", "Commerce / activités productives"),
        ("_v7", "Autre source"),
    ]
    for col, lbl in sources:
        if col in df.columns:
            out[f"src_{col}"] = _binary_flag(df[col])
    out["sources_dechets_liste"] = _concat_binary_flags(df, sources)
    out["nb_sources_dechets"] = sum(
        df[col].fillna(0) for col, _ in sources if col in df.columns
    ).astype(int)

    # --- Nature des déchets (multi-select _v8 à _v17) ---
    natures = [
        ("_v8",  "Plastiques"),
        ("_v9",  "Papier / Carton"),
        ("_v10", "Restes d'aliments"),
        ("_v11", "Vêtements / Tissus"),
        ("_v12", "Déchets électroménagers"),
        ("_v13", "Déchets verts"),
        ("_v14", "Métal"),
        ("_v15", "Excréments d'animaux"),
        ("_v16", "Médicaments"),
        ("_v17", "Autre nature"),
    ]
    for col, lbl in natures:
        if col in df.columns:
            out[f"nat_{col}"] = _binary_flag(df[col])
    out["natures_dechets_liste"] = _concat_binary_flags(df, natures)
    out["nb_natures_dechets"] = sum(
        df[col].fillna(0) for col, _ in natures if col in df.columns
    ).astype(int)

    # --- Mode de stockage ---
    out["mode_stockage"]           = _map(df["II_3"].astype(str), MODE_STOCKAGE)
    out["stockage_couvert"]        = _oui_non(df["II_4"])
    out["place_stockage"]          = _map(df["II_5"].astype(str), PLACE_STOCKAGE)
    out["capacite_stockage_suffisante"] = _oui_non(df["II_6"])

    # --- Pratiques de tri et revente ---
    out["tri_avant_evacuation"]    = _oui_non(df["II_7"])
    out["revente_dechets"]         = _oui_non(df["II_8"])

    # Types revendus (multi-select)
    revendus = [
        ("_v18", "Journaux"), ("_v19", "Verre"), ("_v20", "Ferraille"),
        ("_v21", "Plastique"), ("_v22", "Autre déchet revendu"),
    ]
    out["types_revendus_liste"] = _concat_binary_flags(df, revendus)
    out["raison_non_revente"]   = _map(df["II_10"], {
        1: "Pas connaissance",
        2: "Revenus faibles",
        3: "Ne connaît pas les modes",
        4: "Manque de temps",
        5: "Pas intéressé",
    })

    # --- Traitement auto-effectué ---
    out["proportion_traitee_soi"]  = _map(df["II_11"], PROPORTION_TRAITEE)
    out["traitement_enfouissement"] = _map(df["II_12_1"], TRAITEMENT_PRATIQUE)
    out["traitement_incineration"]  = _map(df["II_12_2"], TRAITEMENT_PRATIQUE)
    out["traitement_recyclage"]     = _map(df["II_12_3"], TRAITEMENT_PRATIQUE)
    out["traitement_compostage"]    = _map(df["II_12_4"], TRAITEMENT_PRATIQUE)

    # Indicateur synthétique : au moins un traitement pratiqué
    traitements_bin = pd.DataFrame({
        "enf": (df["II_12_1"].isin([1, 2])).astype(float),
        "inc": (df["II_12_2"].isin([1, 2])).astype(float),
        "rec": (df["II_12_3"].isin([1, 2])).astype(float),
        "com": (df["II_12_4"].isin([1, 2])).astype(float),
    })
    out["au_moins_un_traitement"]  = traitements_bin.max(axis=1).map({1.0: "Oui", 0.0: "Non"})

    # --- Accès aux services d'évacuation publics (bennes tasseuses) ---
    out["acces_benne_tasseuse"]    = _map(df["II_13"], ACCES_BENNE)
    out["benne_service_principal"] = _oui_non(df["II_14"])
    out["benne_point_distance"]    = _map(df["II_16"], {
        1: "Proche", 2: "Acceptable", 3: "Éloignée"
    })
    out["benne_point_nettoyage"]   = _oui_non(df["II_17"])
    out["benne_heure_convient"]    = _oui_non(df["II_18"])
    out["benne_frequence"]         = df["II_19"].map({1: "Régulière", 2: "Irrégulière"})
    out["satisfaction_benne"]      = _map(df["II_20"], SATISFACTION_COLLECTE)

    # --- Accès aux modes d'évacuation privés / alternatifs ---
    out["service_alternatif_type"] = _map(df["II_22"].astype(str), SERVICE_COLLECTE_ALTERNATIF)
    out["service_alternatif_raison"] = _map(df["II_23"].astype(str), RAISON_SERVICE_ALTERNATIF)

    # Indicateur : a accès à un service alternatif
    out["a_service_alternatif"]    = df["II_22"].astype(str).isin(["1", "2", "3", "other"]).map(
        {True: "Oui", False: "Non"}
    )

    # --- Montant mensuel déboursé (ou à débourser) pour l'évacuation ---
    out["service_evacuation_payant"] = _oui_non(df["II_24"])
    out["montant_evacuation_tranche"] = _map(df["II_25_1"], MONTANT_EVACUATION)
    out["frequence_paiement"]         = _map(df["II_25_2"], FREQUENCE_PAIEMENT)

    # Proxy montant mensuel en FCFA
    med = df["II_25_1"].map(MONTANT_MEDIAN_FCFA)
    freq = df["II_25_2"].map(FREQ_TO_MONTHLY)
    out["montant_mensuel_evacuation_fcfa"] = (med * freq).where(
        df["II_24"] == 1, other=0  # gratuit = 0 si non payant
    ).round(0)

    # Responsable de l'évacuation dans le ménage
    out["responsable_evacuation"] = _map(df["II_15"], {
        1: "Chef de ménage",
        2: "Conjoint du CM",
        3: "Femme de ménage",
        4: "Autre membre féminin adulte",
        5: "Autre membre féminin enfant",
        6: "Autre membre masculin adulte",
        7: "Autre membre masculin enfant",
    })

    # --- Infrastructure quartier : dépotoires normalisés ---
    out["existence_bacs_quartier"]    = df["III_2"].map({1: "Oui", 2: "Non", 3: "Ne sait pas"})
    out["satisfaction_bacs_quartier"] = _satisfaction4(df["III_3"])
    out["corbeilles_rue_presentes"]   = _oui_non(df["III_5"])
    out["satisfaction_corbeilles_disposition"] = _satisfaction4(df["III_6"])
    out["satisfaction_corbeilles_qualite"]     = _satisfaction4(df["III_8"])

    # Indicateur accès dépotoire normalisé (bac public OU corbeille présente)
    bac_ok = df["III_2"] == 1
    corbeille_ok = df["III_5"] == 1
    out["acces_depotoire_normalise"] = (bac_ok | corbeille_ok).map(
        {True: "Oui", False: "Non"}
    )

    # --- Comportements et environnement du quartier ---
    out["depot_sauvage_rue"]     = _map(df["III_10"], FREQUENCE_COMPORTEMENT)
    out["eaux_usees_rue"]        = _map(df["III_11"], FREQUENCE_COMPORTEMENT)
    out["depot_sauvage_observe"] = _map(df["III_12"], {
        1: "Oui, fréquemment", 2: "Oui, rarement", 3: "Non, jamais"
    })
    out["dernier_depot_sauvage"] = _map(df["III_13"], {
        1: "Moins de 2 jours", 2: "2 à 7 jours", 3: "Plus de 7 jours"
    })
    out["contact_autorites_depot"] = _oui_non(df["III_14"])
    out["satisfaction_reaction_autorites"] = _satisfaction4(df["III_15"])

    # Nuisibles attirés (multi-select _v23 à _v29)
    nuisibles = [
        ("_v23", "Moustiques"), ("_v24", "Mouches"), ("_v25", "Cafards"),
        ("_v26", "Souris"), ("_v27", "Vers"), ("_v28", "Rats"), ("_v29", "Autre"),
    ]
    for col, lbl in nuisibles:
        if col in df.columns:
            out[f"nuisible_{col}"] = _binary_flag(df[col])
    out["nuisibles_liste"] = _concat_binary_flags(df, nuisibles)
    out["nb_nuisibles"] = sum(
        df[col].fillna(0) for col, _ in nuisibles if col in df.columns
    ).astype(int)

    # --- Services de gestion publique (balayage, set setal) ---
    out["service_balayage_rues"]       = df["III_18"].map({1: "Oui", 2: "Non", 3: "Ne sait pas"})
    out["satisfaction_balayage"]       = _satisfaction4(df["III_19"])
    out["operations_nettoyage_quartier"] = _oui_non(df["III_21"])

    # Places publiques et marchés
    out["place_publique_presence"]     = _oui_non(df["III_22"])
    out["place_publique_gestionnaire"] = _map(df["III_23"].astype(str), GESTIONNAIRE_PLACE)
    out["place_publique_salubrite"]    = _satisfaction4(df["III_24"])
    out["marche_present"]              = _oui_non(df["III_25"])
    out["marche_gestionnaire"]         = _map(df["III_26"].astype(str), GESTIONNAIRE_PLACE)
    out["marche_gestion_qualite"]      = _satisfaction4(df["III_27"])

    # Connaissance et sensibilisation UCG
    out["connait_UCG"]                 = _oui_non(df["III_28"])
    out["campagne_sensibilisation"]    = _oui_non(df["III_29"])
    out["satisfaction_sensibilisation"] = _oui_non(df["III_31"])

    # Durée dans le quartier (binaire : moins d'un mois ou plus)
    out["duree_quartier_sup_1mois"] = df["III_1"].map({
        1: "Moins d'un mois", 2: "1 mois et plus"
    })

    logger.info(f"Bloc C (déchets) : {out.shape[1]} variables construites.")
    return out


# ---------------------------------------------------------------------------
# BLOC D — Conséquences et perception
# ---------------------------------------------------------------------------

def build_consequences(df: pd.DataFrame) -> pd.DataFrame:
    """Construit les variables sur les conséquences sanitaires et la perception."""
    out = pd.DataFrame(index=df.index)

    # Maladies déclarées (multi-select _v30 à _v38)
    maladies = [
        ("_v30", "Fièvre"),
        ("_v31", "Asthme"),
        ("_v32", "Rhume"),
        ("_v33", "Sinusite"),
        ("_v34", "Toux"),
        ("_v35", "Nausées / Vomissements"),
        ("_v36", "Démangeaisons"),
        ("_v37", "Aucune maladie"),
        ("_v38", "Autre maladie"),
    ]
    for col, lbl in maladies:
        if col in df.columns:
            out[f"maladie_{col}"] = _binary_flag(df[col])
    out["maladies_declarees_liste"]   = _concat_binary_flags(df, maladies)
    out["nb_maladies_declarees"]      = sum(
        df[col].fillna(0) for col, lbl in maladies
        if col in df.columns and lbl != "Aucune maladie"
    ).astype(int)
    out["aucune_maladie"]             = _binary_flag(df.get("_v37", pd.Series(0, index=df.index)))

    # Nombre de types de maladies dans le ménage (variable IV_count)
    if "IV_count" in df.columns:
        out["nb_types_maladies_menage"] = pd.to_numeric(df["IV_count"], errors="coerce")

    # Indicateur synthétique : ménage touché par au moins une maladie liée aux déchets
    # (hors rhume/aucune qui peuvent être non liés)
    maladies_dechets_cols = ["_v31", "_v33", "_v34", "_v35", "_v36"]  # asthme, sinusite, toux, nausées, démangeaisons
    presence_maladie = sum(
        df[col].fillna(0) for col in maladies_dechets_cols if col in df.columns
    )
    out["maladie_potentiellement_liee_dechets"] = (presence_maladie >= 1).map(
        {True: "Oui", False: "Non"}
    )

    # Perception sur les conséquences — non collectée directement comme variable unique
    # On peut la dériver de la présence de dépôts sauvages + maladies signalées
    # Proxy : ménage signale nuisibles ET maladies
    if "nb_nuisibles" in df.columns:
        has_nuisibles = df.get("_v23", pd.Series(0, index=df.index)).fillna(0)
    else:
        has_nuisibles = pd.Series(0, index=df.index)

    out["perception_risque_sanitaire"] = np.nan  # Variable narrative non structurée

    # Suggestions d'amélioration (open-ended III_33) — conservé comme texte
    if "III_33" in df.columns:
        out["suggestions_amelioration"] = df["III_33"].astype(str).replace({"nan": np.nan})

    logger.info(f"Bloc D (conséquences) : {out.shape[1]} variables construites.")
    return out


# ---------------------------------------------------------------------------
# Point d'entrée du module
# ---------------------------------------------------------------------------

def run(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Construit toutes les variables analytiques et retourne la table consolidée.
    """
    blocs = [
        ("menage",       build_menage(df_raw)),
        ("cm",           build_cm(df_raw)),
        ("dechets",      build_dechets(df_raw)),
        ("consequences", build_consequences(df_raw)),
    ]

    df_final = pd.concat([b for _, b in blocs], axis=1)

    # Réinitialiser l'index proprement
    df_final = df_final.reset_index(drop=True)

    logger.info(f"Table consolidée : {df_final.shape[0]} lignes × {df_final.shape[1]} colonnes.")
    return df_final
