"""
FastAPI Server for ForestGuard AI Service.
Exposes /process endpoint to perform inference using XGBoost and CNN models.
Runs inference asynchronously via background tasks and returns results to callback URL.
"""

import os
import sys
import logging
import requests
from typing import Optional, Dict, Any
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel

# Add project root to path if running directly
from pathlib import Path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.common.config.settings import get_ai_settings, root_dir
from src.common.utils.logger import setup_logger, get_logger
from src.ai_service.inference.xgboost_classifier import XGBoostClassifier
from src.ai_service.inference.cnn_classifier import CNNClassifier

# Initialize logger
logger = get_logger("ai_service")

app = FastAPI(title="ForestGuard AI Service")

# Global model classifiers
xgboost_model = None
cnn_model = None

class IngestionPayload(BaseModel):
    record_id: int
    callback_url: str
    data: Dict[str, Any]
    image_path: Optional[str] = None

@app.on_event("startup")
def startup_event():
    """Load models on service startup"""
    global xgboost_model, cnn_model
    settings = get_ai_settings()
    setup_logger(settings.logging)
    logger.info("Initializing models for AI inference service...")
    
    try:
        xgboost_model = XGBoostClassifier()
    except Exception as e:
        logger.error(f"Error loading XGBoost model: {e}", exc_info=True)
        
    try:
        cnn_model = CNNClassifier()
    except Exception as e:
        logger.error(f"Error loading CNN model: {e}", exc_info=True)

def process_inference_task(payload: IngestionPayload):
    """Background task to execute models and fire callback"""
    global xgboost_model, cnn_model
    settings = get_ai_settings()
    
    record_id = payload.record_id
    callback_url = payload.callback_url
    data = payload.data
    image_path = payload.image_path
    
    logger.info(f"Processing inference task for record_id={record_id}")
    
    ai1_score = None
    ai2_score = None
    final_risk_level = "green"
    
    try:
        # 1. Run XGBoost Inference (Sensor Data)
        if xgboost_model is not None:
            ai1_score = xgboost_model.predict(data)
            logger.info(f"XGBoost prediction for record_id={record_id}: {ai1_score}")
        else:
            logger.error("XGBoost model not loaded. Skipping AI-1 prediction.")
            
        # 2. Run CNN Inference if threshold met and image exists
        # If image_path is relative, make it absolute relative to project root
        if image_path and not os.path.isabs(image_path):
            image_path = os.path.join(root_dir, image_path)
            
        threshold = settings.thresholds.ai1_risk_threshold
        alert_threshold = settings.thresholds.ai2_alert_threshold
        
        if ai1_score is not None and ai1_score >= threshold:
            if image_path and os.path.exists(image_path):
                if cnn_model is not None:
                    try:
                        ai2_score = cnn_model.predict(image_path)
                        logger.info(f"CNN prediction for record_id={record_id}: {ai2_score}")
                    except Exception as e:
                        logger.error(f"Error executing CNN model on {image_path}: {e}", exc_info=True)
                else:
                    logger.error("CNN model not loaded. Skipping AI-2 prediction.")
            elif image_path:
                logger.warning(f"Image path provided but file not found: {image_path}")
                
        # 3. Calculate final risk level
        if ai1_score is not None:
            if ai1_score >= 0.9:
                final_risk_level = "red"
            elif ai1_score >= threshold:
                if ai2_score is not None and ai2_score >= alert_threshold:
                    final_risk_level = "red"
                else:
                    final_risk_level = "yellow"
            elif ai1_score >= 0.3:
                final_risk_level = "yellow"
            else:
                final_risk_level = "green"
                
        logger.info(f"Risk evaluation complete for record_id={record_id}: "
                    f"ai1={ai1_score}, ai2={ai2_score}, risk={final_risk_level}")
        
    except Exception as e:
        logger.error(f"Error during inference execution for record_id={record_id}: {e}", exc_info=True)
        # We still callback with whatever fields succeeded
        
    # 4. Trigger Web Backend Callback URL
    callback_payload = {
        "record_id": record_id,
        "ai1": ai1_score,
        "ai2": ai2_score,
        "final_risk_level": final_risk_level
    }
    
    try:
        logger.info(f"Sending callback to {callback_url} for record_id={record_id}")
        r = requests.post(callback_url, json=callback_payload, timeout=10)
        r.raise_for_status()
        logger.info(f"Callback successful: {r.status_code}")
    except Exception as e:
        logger.error(f"Failed to post AI callback back to web backend: {e}")

@app.post("/process")
async def process_record(payload: IngestionPayload, background_tasks: BackgroundTasks):
    """Receive record from ingestion, queue inference in background task"""
    if xgboost_model is None:
        raise HTTPException(status_code=503, detail="AI Service models not fully initialized")
        
    # Queue task
    background_tasks.add_task(process_inference_task, payload)
    return {"status": "queued", "record_id": payload.record_id}

if __name__ == "__main__":
    import uvicorn
    settings = get_ai_settings()
    uvicorn.run(app, host=settings.server.host, port=settings.server.port)
