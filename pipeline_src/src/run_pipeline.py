#!/usr/bin/env python3
# =============================================================================
# run_pipeline.py — Orchestrateur principal
# =============================================================================
# Usage :
#   python run_pipeline.py
#
# Le pipeline attend un fichier .dta dans le dossier /input (configuré dans
# config.py). Il produit dans /output :
#   - dataset_dechets.csv         Table analytique finale
#   - dataset_dechets.dta         Table analytique finale (Stata)
#   - QAQC_rapport.xlsx           Rapport de contrôle qualité
#
# Pour une nouvelle édition de l'enquête :
#   1. Placer le nouveau fichier dans /input (même nom ou adapter INPUT_FILE)
#   2. Mettre à jour config.py si les codes ont changé
#   3. Relancer ce script
# =============================================================================

import os
import sys
import logging
import time
from datetime import datetime

# Ajouter le dossier src au path Python
sys.path.insert(0, os.path.dirname(__file__))

import loader
import builder
import qaqc
import exporter
from config import OUTPUT_DIR

# ---------------------------------------------------------------------------
# Configuration du logging
# ---------------------------------------------------------------------------
os.makedirs(OUTPUT_DIR, exist_ok=True)

log_file = os.path.join(OUTPUT_DIR, f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8"),
    ],
)
logger = logging.getLogger("pipeline")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run():
    start = time.time()
    logger.info("=" * 65)
    logger.info("  PIPELINE DÉCHETS MÉNAGERS — DÉMARRAGE")
    logger.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 65)

    qc_log = []

    # ---- Étape 1 : Chargement et nettoyage --------------------------------
    logger.info("\n[ÉTAPE 1/4] Chargement et contrôle qualité des données brutes...")
    df_raw, meta = loader.run(qc_log)
    logger.info(f"  → {df_raw.shape[0]} ménages chargés, {len(qc_log)} anomalies détectées.")

    # ---- Étape 2 : Construction des variables analytiques -----------------
    logger.info("\n[ÉTAPE 2/4] Construction des variables analytiques...")
    df_final = builder.run(df_raw)
    logger.info(f"  → Table finale : {df_final.shape[1]} variables analytiques.")

    # ---- Étape 3 : Export des données -------------------------------------
    logger.info("\n[ÉTAPE 3/4] Export CSV et Stata...")
    csv_path, dta_path = exporter.run(df_final)
    logger.info(f"  → CSV  : {csv_path}")
    logger.info(f"  → DTA  : {dta_path}")

    # ---- Étape 4 : Rapport QAQC -------------------------------------------
    logger.info("\n[ÉTAPE 4/4] Génération du rapport QAQC...")
    qaqc_path = os.path.join(OUTPUT_DIR, "QAQC_rapport.xlsx")
    qaqc.run(df_raw, df_final, qc_log, qaqc_path)
    logger.info(f"  → QAQC : {qaqc_path}")

    # ---- Résumé final -----------------------------------------------------
    elapsed = round(time.time() - start, 1)
    logger.info("\n" + "=" * 65)
    logger.info("  PIPELINE TERMINÉ AVEC SUCCÈS")
    logger.info(f"  Durée : {elapsed}s")
    logger.info(f"  Ménages traités   : {df_final.shape[0]}")
    logger.info(f"  Variables output  : {df_final.shape[1]}")
    logger.info(f"  Anomalies QC      : {len(qc_log)}")
    logger.info(f"  Fichiers produits : {csv_path}")
    logger.info(f"                      {dta_path}")
    logger.info(f"                      {qaqc_path}")
    logger.info("=" * 65)

    return df_final, qc_log


if __name__ == "__main__":
    run()
