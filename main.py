import time
import os
from pipeline.utils.logger import log_info, log_error
from pipeline.extraire_enrichissement import run_pipeline as run_enrich
from pipeline.transformation import run as run_fusion
from pipeline.clean_pipeline import run as run_clean
from pipeline.load_mongo import run as run_load
from pipeline.utils.reporting import generate_pipeline_report,save_pipeline_metrics
from pipeline.test_post_insertion import run as run_test_integration
from pipeline.utils.s3_utils import save_logs_s3
from pipeline.mongo_replica_log_monitor import send_replica_lag_metrics 
from config import S3_BUCKET, pipeline_name

def main():
    start = time.time()
    step_stats = {
        "enrich": {"input": 0, "output": 0},
        "fusion": {"input": 0, "output": 0},
        "clean": {"input": 0, "output": 0},
        "load": {"inserted": 0, "rejected": 0}
        }  
    doc_validity_map = {}  # pour reporting par doc si besoin

    try:
        log_info("DEBUT de la pipeline data")

        # --- Étape 1 : Enrichissement ---
        log_info("Étape 1 : Enrichissement")
        enriched_docs = run_enrich()
        step_stats["enrich"]["output"] = len(enriched_docs)
        log_info(f"✔ Enrichissement terminé ({len(enriched_docs)} docs) en {time.time()-start:.2f}s")

        # --- Étape 2 : Fusion / Transformation ---
        log_info("Étape 2 : Fusion / Transformation")
        fused_docs = run_fusion()
        step_stats["fusion"]["input"] = len(enriched_docs)
        step_stats["fusion"]["output"] = len(fused_docs)
        log_info(f"✔ Fusion terminée ({len(fused_docs)} docs) en {time.time()-start:.2f}s")

        # --- Étape 3 : Nettoyage ---
        log_info("Étape 3 : Nettoyage")
        cleaned_docs = run_clean()
        step_stats["clean"]["input"] = len(fused_docs)
        step_stats["clean"]["output"] = len(cleaned_docs)
        log_info(f"✔ Nettoyage terminé ({len(cleaned_docs)} docs) en {time.time()-start:.2f}s")

        # --- Étape 4 : Chargement MongoDB ---
        log_info("Étape 4 : Chargement MongoDB")
        try:
            load_report = run_load()
            step_stats["load"]["inserted"] = load_report["total_valid"]
            step_stats["load"]["rejected"] = load_report["total_rejected"]

            log_info(
                f"✔ Chargement MongoDB terminé "
                f"({load_report['total_valid']} docs, {load_report['total_rejected']} rejetés) "
                f"en {time.time() - start:.2f}s"
            )

        except Exception as e:
            log_error(f"✖ Erreur chargement MongoDB : {e}")

        # --- Étape 5 : Rapport pipeline ---
        log_info("[Rapport] Génération du rapport pipeline")
        try:
            report_path = generate_pipeline_report(doc_validity_map)
            log_info(f"✔ Rapport pipeline généré : {report_path.resolve()}")
        except Exception as e:
            log_error(f"✖ Erreur génération rapport : {e}")

         # --- Étape 5 : Rapport pipeline ---
        log_info("[Post-Integration] Execustion test post-integration")
        try:
            run_test_integration()
            log_info(f"✔  test post-integration effectueé  ")    
        except Exception as e:
            log_error(f"✖ Erreur test post-integration : {e}")

        # --- Étape 7 : Calcul et sauvegarde des metrics ---
        total_docs = step_stats["clean"]["output"]
        rejected_docs = step_stats["load"]["rejected"]
        error_rate = rejected_docs / total_docs if total_docs > 0 else 0
        duration = round(time.time() - start, 2)

        save_pipeline_metrics(
            total_docs=total_docs,
            rejected_docs=rejected_docs,
            error_rate=error_rate,
            duration=duration,
            source=pipeline_name
        )
        # --- Étape 6 : Monitoring Replica Lag MongoDB ---
        log_info("[MongoDB] Vérification du Replica Lag")
        try:
            
            send_replica_lag_metrics()
            log_info("✔ Replica Lag envoyé à CloudWatch")
        except Exception as e:
            log_error(f"✖ Erreur monitoring Replica Lag : {e}")

        # --- Sauvegarde logs ---
        log_file = "pipeline.log"
        if os.path.exists(log_file):
            try:
                save_logs_s3(S3_BUCKET)
                log_info("✔ Logs pipeline sauvegardés sur S3")
            except Exception as e:
                log_error(f"✖ Erreur upload logs S3 : {e}")
        else:
            log_error("✖ Fichier pipeline.log introuvable, upload ignoré")

        log_info("PIPELINE terminée avec succès")
        # Pause juste avant que le script se termine
        time.sleep(2) 

    except Exception as e:
        log_error(f"✖ Erreur générale pipeline : {e}")

 


if __name__ == "__main__":
    main()
