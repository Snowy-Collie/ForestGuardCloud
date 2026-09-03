#!/usr/bin/env python3
"""
Offline batch AI reprocessing utility for ForestGuard AI.
Scans the database, runs XGBoost (AI-1) and Keras CNN (AI-2) classifiers on pending records,
and updates scores and final risk levels.
"""

import os
import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.common.config.settings import get_ai_settings, root_dir
from src.common.database.connection import get_connection_manager
from src.ai_service.inference.xgboost_classifier import XGBoostClassifier
from src.ai_service.inference.cnn_classifier import CNNClassifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("batch_reprocess")


def reprocess():
    settings = get_ai_settings()
    db_manager = get_connection_manager()
    
    logger.info("Initializing models for batch reprocessing...")
    try:
        xgboost_model = XGBoostClassifier()
    except Exception as e:
        logger.error(f"Failed to load XGBoost model: {e}")
        return
        
    try:
        cnn_model = CNNClassifier()
    except Exception as e:
        logger.error(f"Failed to load CNN model: {e}")
        cnn_model = None
        
    threshold = settings.thresholds.ai1_risk_threshold
    alert_threshold = settings.thresholds.ai2_alert_threshold
    
    # 1. Reprocess AI-1 (XGBoost) for records where AI-1 is NULL
    logger.info("Fetching records with missing AI-1 scores...")
    try:
        with db_manager.get_cursor() as cursor:
            cursor.execute("""
                SELECT id, tvoc, eco2, nh3, h2s, temperature, humidity 
                FROM data_upload 
                WHERE "AI-1" IS NULL
            """)
            pending_ai1 = cursor.fetchall()
            
        logger.info(f"Found {len(pending_ai1)} records pending AI-1 calculation.")
        
        for record in pending_ai1:
            rec_id = record['id']
            # Prepare data dictionary expected by feature pipeline
            data = {
                'tvoc': record['tvoc'],
                'eco2': record['eco2'],
                'nh3': record['nh3'],
                'h2s': record['h2s'],
                'temperature': record['temperature'],
                'humidity': record['humidity']
            }
            
            try:
                ai1_score = xgboost_model.predict(data)
                
                # Calculate simple initial risk level
                risk = "green"
                if ai1_score >= 0.9:
                    risk = "red"
                elif ai1_score >= threshold:
                    risk = "yellow"
                elif ai1_score >= 0.3:
                    risk = "yellow"
                
                with db_manager.get_cursor() as cursor:
                    cursor.execute("""
                        UPDATE data_upload 
                        SET "AI-1" = %s, final_risk_level = %s 
                        WHERE id = %s
                    """, (ai1_score, risk, rec_id))
                    
                logger.info(f"Updated record {rec_id}: AI-1={ai1_score:.4f}, risk={risk}")
            except Exception as e:
                logger.error(f"Error processing AI-1 for record {rec_id}: {e}")
                
    except Exception as e:
        logger.error(f"Database error during AI-1 batch reprocessing: {e}")

    # 2. Reprocess AI-2 (CNN) for records where AI-1 > threshold and AI-2 is NULL
    if cnn_model is None:
        logger.warning("CNN model not available. Skipping AI-2 processing.")
        return
        
    logger.info(f"Fetching records with AI-1 > {threshold} and missing AI-2 scores...")
    try:
        with db_manager.get_cursor() as cursor:
            cursor.execute("""
                SELECT id, "AI-1" as ai1, picture_path 
                FROM data_upload 
                WHERE "AI-1" >= %s AND "AI-2" IS NULL AND picture_path IS NOT NULL
            """, (threshold,))
            pending_ai2 = cursor.fetchall()
            
        logger.info(f"Found {len(pending_ai2)} records pending AI-2 image verification.")
        
        for record in pending_ai2:
            rec_id = record['id']
            ai1_score = float(record['ai1'])
            pic_path = record['picture_path']
            
            # Resolve image path relative to project root
            full_pic_path = pic_path
            if not os.path.isabs(full_pic_path):
                full_pic_path = os.path.join(root_dir, full_pic_path)
                
            if not os.path.exists(full_pic_path):
                logger.warning(f"Image for record {rec_id} not found at {full_pic_path}. Skipping.")
                continue
                
            try:
                ai2_score = cnn_model.predict(full_pic_path)
                
                # Re-evaluate final risk level
                if ai1_score >= 0.9:
                    risk = "red"
                elif ai1_score >= threshold:
                    if ai2_score >= alert_threshold:
                        risk = "red"
                    else:
                        risk = "yellow"
                else:
                    risk = "green"
                    
                with db_manager.get_cursor() as cursor:
                    cursor.execute("""
                        UPDATE data_upload 
                        SET "AI-2" = %s, final_risk_level = %s 
                        WHERE id = %s
                    """, (ai2_score, risk, rec_id))
                    
                logger.info(f"Updated record {rec_id}: AI-2={ai2_score:.4f}, risk={risk}")
            except Exception as e:
                logger.error(f"Error processing AI-2 for record {rec_id}: {e}")
                
    except Exception as e:
        logger.error(f"Database error during AI-2 batch reprocessing: {e}")

    logger.info("Batch reprocessing run completed.")


if __name__ == "__main__":
    reprocess()
