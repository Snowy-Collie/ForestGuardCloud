"""
XGBoost Classifier for ForestGuard AI.
Loads trained XGBoost classification model and runs predictions.
"""

import xgboost as xgb
import os
import logging
from typing import Optional, Dict, Any

from src.ai_service.feature_pipeline.feature_extractor import extract_features
from src.common.config.settings import get_ai_settings, root_dir

logger = logging.getLogger(__name__)

class XGBoostClassifier:
    """Inference class for wildfire sensor anomaly detection"""
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize the classifier.
        Loads model file from model_path or config.
        """
        if model_path is None:
            settings = get_ai_settings()
            model_path = settings.models.xgboost_model_path
            
        # Ensure path is absolute relative to project root if it is relative
        if not os.path.isabs(model_path):
            model_path = os.path.join(root_dir, model_path)
            
        self.model_path = model_path
        self.model = xgb.Booster()
        
        logger.info(f"Loading XGBoost model from: {self.model_path}")
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"XGBoost model file not found at {self.model_path}")
            
        self.model.load_model(self.model_path)
        logger.info("XGBoost Booster model loaded successfully.")

    def predict(self, data: Dict[str, Any]) -> float:
        """
        Run anomaly prediction for a dictionary of sensor data.
        
        Returns:
            The fire risk probability (float score between 0 and 1).
        """
        df = extract_features(data)
        dmat = xgb.DMatrix(df)
        prediction_proba = self.model.predict(dmat)
        score = float(prediction_proba[0])
        return score
