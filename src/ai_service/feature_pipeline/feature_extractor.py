"""
Feature extraction pipeline for ForestGuard AI.
Aligns and maps raw sensor telemetry to feature names expected by XGBoost classifier.
Can be shared with future offline training scripts.
"""

import pandas as pd
from typing import Dict, Any

def extract_features(data: Dict[str, Any]) -> pd.DataFrame:
    """
    Extract and map sensor telemetry to model features.
    
    Expected raw keys (database/sensor fields):
        - tvoc: TVOC in ppb
        - eco2: eCO2 in ppm
        - nh3: NH3 voltage/reading in mV (mapped to Raw H2)
        - h2s: H2S voltage/reading in mV (mapped to Raw Ethanol)
        - temperature: Temperature in Celsius
        - humidity: Humidity percentage
        
    Returns:
        Pandas DataFrame representing the aligned features.
    """
    # Extract values, default to 0.0 if missing, except Pressure which defaults to 1013.25
    tvoc = float(data.get('tvoc', 0.0) or 0.0)
    eco2 = float(data.get('eco2', 0.0) or 0.0)
    nh3 = float(data.get('nh3', 0.0) or 0.0)
    h2s = float(data.get('h2s', 0.0) or 0.0)
    temperature = float(data.get('temperature', 0.0) or 0.0)
    humidity = float(data.get('humidity', 0.0) or 0.0)
    
    features = {
        'TVOC_ppb': tvoc,
        'eCO2_ppm': eco2,
        'Raw H2': nh3,          # Map nh3 to Raw H2
        'Raw Ethanol': h2s,     # Map h2s to Raw Ethanol
        'Temperature_C': temperature,
        'Humidity_pct': humidity,
        'Pressure_hPa': 1013.25  # Constant value for missing Pressure
    }
    
    return pd.DataFrame([features])
