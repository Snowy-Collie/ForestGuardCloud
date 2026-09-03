import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.common.config.settings import (
    get_ingestion_settings, 
    get_ai_settings, 
    get_web_settings
)

def test_settings_load():
    print("Testing Ingestion settings...")
    ing_settings = get_ingestion_settings()
    print(f"  TCP Host: {ing_settings.server.host}")
    print(f"  TCP Port: {ing_settings.server.port}")
    print(f"  Database Host: {ing_settings.database.host}")
    print(f"  Images storage dir: {ing_settings.storage.image_path}")
    print(f"  Logs storage path: {ing_settings.logging.file}")
    
    print("\nTesting AI settings...")
    ai_settings = get_ai_settings()
    print(f"  AI Port: {ai_settings.server.port}")
    print(f"  XGBoost Model path: {ai_settings.models.xgboost_model_path}")
    print(f"  CNN Model path: {ai_settings.models.cnn_model_path}")
    print(f"  AI-1 Risk Threshold: {ai_settings.thresholds.ai1_risk_threshold}")
    
    print("\nTesting Web settings...")
    web_settings = get_web_settings()
    print(f"  Web Port: {web_settings.server.port}")
    
    print("\nSettings load test completed successfully!")

if __name__ == "__main__":
    test_settings_load()
