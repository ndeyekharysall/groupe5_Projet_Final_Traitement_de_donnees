# =============================================================================
# config.py — Configuration centrale du pipeline déchets ménagers
# =============================================================================
# Ce fichier centralise TOUS les mappings de labels et paramètres.
# Pour une nouvelle édition de l'enquête, seuls les mappings doivent être mis
# à jour ici si les codes changent. La logique du pipeline reste intacte.
# =============================================================================

import os

# ---------------------------------------------------------------------------
# CHEMINS
# ---------------------------------------------------------------------------
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_DIR   = os.path.join(BASE_DIR, "input")
OUTPUT_DIR  = os.path.join(BASE_DIR, "output")

# Nom du fichier source (seule chose à changer entre éditions si le nom change)
INPUT_FILE  = "Base.dta"

# ---------------------------------------------------------------------------
# MAPPINGS DE LABELS — Module I : Ménage & Chef de Ménage
# ---------------------------------------------------------------------------

SEXE = {1: "Homme", 2: "Femme"}

STATUT_REPONDANT = {
    "1": "Chef de ménage",
    "2": "Conjoint(e) du CM",
    "3": "Fils/Fille du CM",
    "4": "Père/Mère du CM",
    "5": "Frère/Sœur du CM",
    "6": "Autre parent du CM",
    "7": "Employé(e) de maison",
    "8": "Autre personne non apparentée",
    "9": "Beau-fils/Belle-fille",
    "10": "Petit-fils/Petite-fille",
    "other": "Autre",
}

STATUT_OCCUPATION = {1: "Locataire", 2: "Propriétaire", 3: "Logé par un tiers"}

TYPE_LOGEMENT = {
    "1": "Villa / Maison individuelle",
    "2": "Appartement",
    "3": "Chambre(s) en bande",
    "4": "Baraque / Habitat précaire",
    "other": "Autre",
}

TYPE_ENSEIGNEMENT_CM = {
    "1": "Aucun",
    "2": "Franco-arabe",
    "3": "Français",
    "4": "Coranique / Daara",
    "5": "Autre",
    "other": "Autre",
}

NIVEAU_INSTRUCTION_CM = {
    1: "Primaire",
    2: "Secondaire",
    3: "Supérieur",
    4: "Ne sait pas",
}

ALPHA_CM = {1: "Oui", 2: "Non", 3: "Ne sait pas"}

# ---------------------------------------------------------------------------
# MAPPINGS — Module II : Déchets Ménagers
# ---------------------------------------------------------------------------

MODE_STOCKAGE = {
    "1": "Poubelle avec couvercle",
    "2": "Poubelle sans couvercle",
    "3": "Sac plastique",
    "4": "Carton / Caisse",
    "5": "Coin de la cour / à même le sol",
    "other": "Autre",
}

PLACE_STOCKAGE = {
    "1": "Dans la maison / chambre",
    "2": "Dans la cour",
    "3": "Devant la maison / entrée",
    "4": "Autre endroit extérieur",
    "other": "Autre",
}

PROPORTION_TRAITEE = {
    1: "La totalité",
    2: "Une partie",
    3: "Aucune partie",
}

TRAITEMENT_PRATIQUE = {
    1: "Oui (totalité)",
    2: "Oui (partie)",
    3: "Non",
}

# II_13 : accès bennes tasseuses (valeur numérique comme fréquence/type)
ACCES_BENNE = {
    1: "Oui — service utilisé",
    2: "Non",
    3: "Oui — mais pas utilisé",
    4: "Occasionnellement",
    5: "Rarement",
    6: "Ne sait pas",
}

SERVICE_COLLECTE_ALTERNATIF = {
    "1": "Charrette / collecteur informel",
    "2": "Dépôt dans bac à ordures public",
    "3": "Dépôt sauvage",
    "other": "Autre",
}

RAISON_SERVICE_ALTERNATIF = {
    "1": "Plus pratique / accessible",
    "2": "Moins cher / gratuit",
    "3": "Plus rapide / fréquent",
    "4": "Seul service disponible",
    "other": "Autre",
}

SATISFACTION_COLLECTE = {
    1: "Très bon",
    2: "Bon",
    3: "Mauvais",
    4: "Très mauvais",
}

MONTANT_EVACUATION = {
    1: "Moins de 200 FCFA",
    2: "Entre 200 et 400 FCFA",
    3: "Entre 401 et 1 000 FCFA",
    4: "Entre 1 001 et 2 000 FCFA",
    5: "Plus de 2 000 FCFA",
}

FREQUENCE_PAIEMENT = {
    1: "Par jour",
    2: "Par semaine",
    3: "Par mois",
    4: "Par an",
}

# Valeur médiane (FCFA) associée à chaque tranche de montant (pour proxy mensuel)
MONTANT_MEDIAN_FCFA = {1: 100, 2: 300, 3: 700, 4: 1500, 5: 2500}

# Facteur de conversion vers mensuel
FREQ_TO_MONTHLY = {1: 30, 2: 4.33, 3: 1, 4: 1 / 12}

# ---------------------------------------------------------------------------
# MAPPINGS — Module III : Infrastructure & Environnement Quartier
# ---------------------------------------------------------------------------

SATISFACTION_4PT = {
    1: "Très satisfait / Très bon",
    2: "Satisfait / Bon",
    3: "Pas satisfait / Mauvais",
    4: "Pas du tout satisfait / Très mauvais",
}

FREQUENCE_COMPORTEMENT = {
    1: "Oui, très souvent",
    2: "Oui, rarement",
    3: "Non, jamais",
}

GESTIONNAIRE_PLACE = {
    "1": "Mairie",
    "2": "UCG",
    "3": "Association de quartier",
    "4": "Opérateur privé",
    "5": "Aucun gestionnaire identifié",
    "6": "Autre entité publique",
    "other": "Autre",
}

# ---------------------------------------------------------------------------
# SEUILS DE CONTRÔLE QUALITÉ (QC)
# ---------------------------------------------------------------------------
QC_AGE_MIN          = 15    # âge minimum réaliste pour un CM (en années)
QC_AGE_MAX          = 110   # âge maximum réaliste
QC_TAILLE_MAX       = 50    # taille de ménage maximale réaliste
QC_DUREE_QUARTIER_MAX = 600 # durée max en mois (50 ans)
QC_MISSING_THRESH   = 0.50  # alerte QAQC si + de 50 % de valeurs manquantes sur une variable

# ---------------------------------------------------------------------------
# VARIABLES ABSENTES — NOTE DOCUMENTAIRE
# ---------------------------------------------------------------------------
VARS_ABSENTES = {
    "region":           "Non collectée directement. Seule la commune est disponible.",
    "departement":      "Non collectée directement. Seule la commune est disponible.",
    "milieu_residence": "Non collectée directement. À dériver d'une table de correspondance Commune→Milieu.",
    "depenses_menage":  "Non collectée. Proxy construit : voir variable 'proxy_niveau_vie'.",
    "actifs_menage":    "Non collectée. Inclus dans proxy via type de logement et statut d'occupation.",
    "revenu_CM":        "Non collectée. Proxy construit via statut d'emploi du répondant et montant payé déchets.",
}
