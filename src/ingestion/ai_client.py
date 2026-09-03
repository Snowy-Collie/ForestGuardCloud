"""
AI Client for triggering decoupled AI workers
"""

import requests
import logging
from typing import Optional, Dict, Any
from src.common.config.settings import get_ingestion_settings

logger = logging.getLogger(__name__)

def trigger_ai_worker(record_id: int, data: Dict[str, Any], image_path: Optional[str] = None) -> bool:
    """
    Trigger the AI worker for processing
    
    Args:
        record_id: Database record ID
        data: Sensor data dictionary
        image_path: Path to the associated image (if any)
    
    Returns:
        True if triggered successfully, False otherwise
    """
    settings = get_ingestion_settings()
    worker_url = settings.ai.worker_url
    callback_url = settings.ai.callback_url
    
    payload = {
        "record_id": record_id,
        "callback_url": callback_url,
        "data": data,
        "image_path": image_path
    }
    
    try:
        logger.info(f"Triggering AI worker at {worker_url} for record_id={record_id}")
        response = requests.post(worker_url, json=payload, timeout=5)
        response.raise_for_status()
        logger.info(f"AI worker triggered successfully: {response.status_code}")
        return True
    except Exception as e:
        logger.error(f"Failed to trigger AI worker: {e}")
        return False
