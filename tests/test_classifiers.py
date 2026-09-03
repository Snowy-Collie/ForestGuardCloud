import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.ai_service.inference.xgboost_classifier import XGBoostClassifier
from src.ai_service.feature_pipeline.feature_extractor import extract_features

def test_classifiers():
    print("Verifying if XGBoost is importable and model file is loadable...")
    try:
        classifier = XGBoostClassifier()
        print("  XGBoost Classifier loaded successfully!")
        
        # Test mock prediction
        mock_data = {
            'tvoc': 50.0,
            'eco2': 400.0,
            'nh3': 100.0,
            'h2s': 200.0,
            'temperature': 25.0,
            'humidity': 55.0
        }
        score = classifier.predict(mock_data)
        print(f"  Mock prediction score: {score:.6f}")
        
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_classifiers()
