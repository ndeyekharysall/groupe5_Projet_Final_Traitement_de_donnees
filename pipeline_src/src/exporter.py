# =============================================================================
# exporter.py — Export de la table finale en CSV et Stata .dta
# =============================================================================

import os
import logging
import numpy as np
import pandas as pd
import pyreadstat

from config import OUTPUT_DIR, VARS_ABSENTES

logger = logging.getLogger(__name__)


def _prepare_for_stata(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prépare la table pour l'export Stata :
    - Raccourcit les noms de colonnes > 32 caractères (limite Stata)
    - Convertit les colonnes catégorielles str en str (Stata les stocke comme strL)
    - Remplace les NaN par des valeurs Stata-compatibles selon le type
    """
    df = df.copy()

    # Raccourcir noms trop longs pour Stata (limite = 32 caractères)
    rename_map = {}
    seen = set()
    for col in df.columns:
        if len(col) > 32:
            short = col[:29]
            # Éviter doublons
            suffix = 1
            candidate = short
            while candidate in seen:
                candidate = short[:27] + f"_{suffix:02d}"
                suffix += 1
            rename_map[col] = candidate
            seen.add(candidate)
        else:
            seen.add(col)
    if rename_map:
        logger.warning(f"Noms raccourcis pour Stata : {rename_map}")
        df = df.rename(columns=rename_map)

    # Convertir object → str propre (Stata tolère les chaînes)
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).replace({"nan": "", "None": "", "NaT": ""})

    return df, rename_map


def export_csv(df: pd.DataFrame, filename: str = "dataset_dechets.csv"):
    """Export CSV UTF-8 avec BOM pour compatibilité Excel."""
    path = os.path.join(OUTPUT_DIR, filename)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    logger.info(f"CSV exporté : {path} ({df.shape[0]} lignes × {df.shape[1]} colonnes)")
    return path


def export_dta(df: pd.DataFrame, filename: str = "dataset_dechets.dta"):
    """Export Stata .dta avec labels de variables."""
    path = os.path.join(OUTPUT_DIR, filename)
    df_stata, rename_map = _prepare_for_stata(df)

    # Construire les labels de variables (variable_labels)
    variable_labels = {
        # --- Ménage ---
        "commune_code":             "Code commune (valeur brute)",
        "quartier":                 "Quartier de l'enquête",
        "region":                   "Région (non collectée)",
        "departement":              "Département (non collecté)",
        "milieu_residence":         "Milieu de résidence (non collecté)",
        "nb_enfants_0_4":           "Nombre d'enfants 0-4 ans",
        "nb_enfants_5_15":          "Nombre d'enfants 5-15 ans",
        "nb_adultes_H":             "Nombre d'adultes hommes (15+)",
        "nb_adultes_F":             "Nombre d'adultes femmes (15+)",
        "taille_menage":            "Taille totale du ménage",
        "statut_occupation":        "Statut d'occupation du logement",
        "type_habitat":             "Type de logement / habitat",
        "proxy_niveau_vie":         "Score proxy niveau de vie (0-3)",
        "proxy_niveau_vie_label":   "Label proxy niveau de vie",
        # --- CM ---
        "cm_sexe":                  "Sexe du chef de ménage",
        "cm_age":                   "Âge du chef de ménage (années)",
        "cm_tranche_age":           "Tranche d'âge du CM",
        "repondant_statut":         "Statut du répondant dans le ménage",
        "repondant_est_cm":         "Le répondant est-il le CM ?",
        "cm_branche_etudes":        "Type d'enseignement suivi (CM)",
        "cm_niveau_etudes":         "Niveau d'instruction du CM",
        "cm_alpha_francais":        "CM alphabétisé en français",
        "cm_alpha_anglais":         "CM alphabétisé en anglais",
        "cm_alpha_arabe":           "CM alphabétisé en arabe",
        "cm_alpha_lng_nat":         "CM alphabétisé en langue nationale",
        "cm_est_alphabetise":       "CM alphabétisé (au moins une langue)",
        "cm_situation_matrimoniale":"Situation matrimoniale CM (non collectée)",
        "cm_statut_emploi":         "Statut d'emploi CM (non collecté)",
        "cm_secteur_emploi":        "Secteur d'emploi CM (non collecté)",
        "cm_revenu":                "Revenu CM (non collecté)",
        # --- Déchets ---
        "sources_dechets_liste":    "Sources de déchets (liste textuelle)",
        "nb_sources_dechets":       "Nombre de sources de déchets",
        "natures_dechets_liste":    "Natures des déchets (liste textuelle)",
        "nb_natures_dechets":       "Nombre de natures de déchets",
        "mode_stockage":            "Mode principal de stockage des déchets",
        "stockage_couvert":         "Récipient de stockage couvert ?",
        "place_stockage":           "Emplacement du stockage",
        "capacite_stockage_suffisante": "Capacité de stockage suffisante ?",
        "tri_avant_evacuation":     "Tri des déchets avant évacuation ?",
        "revente_dechets":          "Revente de déchets pratiquée ?",
        "types_revendus_liste":     "Types de déchets revendus",
        "raison_non_revente":       "Raison de non-revente des déchets",
        "proportion_traitee_soi":   "Proportion des déchets traités par le ménage",
        "traitement_enfouissement": "Pratique d'enfouissement",
        "traitement_incineration":  "Pratique d'incinération",
        "traitement_recyclage":     "Pratique de recyclage",
        "traitement_compostage":    "Pratique de compostage",
        "au_moins_un_traitement":   "Au moins un traitement pratiqué",
        "acces_benne_tasseuse":     "Accès bennes tasseuses (service public)",
        "benne_service_principal":  "Benne = service d'évacuation principal",
        "benne_point_distance":     "Distance au point de collecte",
        "benne_point_nettoyage":    "Point de collecte nettoyé régulièrement",
        "benne_heure_convient":     "Heure de passage de la benne convient",
        "benne_frequence":          "Fréquence de passage de la benne",
        "satisfaction_benne":       "Satisfaction globale service benne",
        "service_alternatif_type":  "Type de service alternatif utilisé",
        "service_alternatif_raison":"Raison de préférence service alternatif",
        "a_service_alternatif":     "A accès à un service alternatif",
        "service_evacuation_payant":"Service d'évacuation payant ?",
        "montant_evacuation_tranche":"Tranche montant évacuation",
        "frequence_paiement":       "Fréquence de paiement du service",
        "montant_mensuel_evacuation_fcfa": "Montant mensuel évacuation (proxy FCFA)",
        "responsable_evacuation":   "Responsable évacuation dans le ménage",
        "existence_bacs_quartier":  "Existence bacs à ordures dans le quartier",
        "satisfaction_bacs_quartier":"Satisfaction disposition bacs quartier",
        "corbeilles_rue_presentes": "Corbeilles de rue présentes",
        "satisfaction_corbeilles_disposition": "Satisfaction disposition corbeilles",
        "satisfaction_corbeilles_qualite": "Satisfaction qualité corbeilles",
        "acces_depotoire_normalise":"Accès à un dépotoire normalisé",
        "depot_sauvage_rue":        "Dépôts sauvages dans la rue (fréquence)",
        "eaux_usees_rue":           "Eaux usées versées dans la rue (fréquence)",
        "depot_sauvage_observe":    "Dépôts sauvages observés dans le quartier",
        "dernier_depot_sauvage":    "Dernier dépôt sauvage observé",
        "contact_autorites_depot":  "Contact autorités pour dépôts sauvages",
        "satisfaction_reaction_autorites":"Satisfaction temps de réaction autorités",
        "nuisibles_liste":          "Nuisibles attirés (liste)",
        "nb_nuisibles":             "Nombre de types de nuisibles",
        "service_balayage_rues":    "Service de balayage des rues",
        "satisfaction_balayage":    "Satisfaction service balayage",
        "operations_nettoyage_quartier": "Opérations de nettoyage (set setal)",
        "place_publique_presence":  "Place publique à proximité",
        "place_publique_gestionnaire": "Gestionnaire place publique",
        "place_publique_salubrite": "État de salubrité place publique",
        "marche_present":           "Marché à proximité",
        "marche_gestionnaire":      "Gestionnaire du marché",
        "marche_gestion_qualite":   "Qualité gestion ordures marché",
        "connait_UCG":              "Connaissance de l'UCG",
        "campagne_sensibilisation": "Campagne de sensibilisation reçue",
        "satisfaction_sensibilisation":"Satisfaction campagne sensibilisation",
        "duree_quartier_sup_1mois": "Durée dans le quartier (>1 mois ?)",
        # --- Conséquences ---
        "maladies_declarees_liste": "Maladies déclarées (liste)",
        "nb_maladies_declarees":    "Nombre de types de maladies déclarées",
        "aucune_maladie":           "Aucune maladie déclarée (0/1)",
        "nb_types_maladies_menage": "Nombre total de types de maladies (IV_count)",
        "maladie_potentiellement_liee_dechets": "Maladie potentiellement liée aux déchets",
        "perception_risque_sanitaire": "Perception risque sanitaire (non collectée)",
        "suggestions_amelioration": "Suggestions d'amélioration (texte libre)",
    }

    # Appliquer le rename_map aux labels aussi
    if rename_map:
        inv_rename = {v: k for k, v in rename_map.items()}
        variable_labels = {
            rename_map.get(k, k): v for k, v in variable_labels.items()
        }

    try:
        pyreadstat.write_dta(
            df_stata,
            path,
            column_labels=list(variable_labels.values()) if len(variable_labels) == len(df_stata.columns) else None,
            file_label="Enquête déchets ménagers — données traitées",
        )
        logger.info(f"Stata .dta exporté : {path}")
    except Exception as e:
        logger.warning(f"Export DTA avec labels échoué ({e}) — export sans labels.")
        pyreadstat.write_dta(df_stata, path, file_label="Enquête déchets ménagers — données traitées")

    return path


def run(df_final: pd.DataFrame):
    """Exporte la table finale en CSV et DTA."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    csv_path = export_csv(df_final)
    dta_path = export_dta(df_final)
    return csv_path, dta_path
