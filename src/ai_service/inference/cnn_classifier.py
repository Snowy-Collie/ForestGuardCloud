"""
Keras CNN Classifier for ForestGuard AI.
Loads Keras MobileNetV2 model and performs image classification for fire detection.
"""

import os
import numpy as np
from PIL import Image
import tensorflow as tf
import logging
from typing import Optional

from src.common.config.settings import get_ai_settings, root_dir

logger = logging.getLogger(__name__)

class CNNClassifier:
    """Inference class for wildfire camera anomaly verification"""
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize the classifier.
        Loads .h5 model file from model_path or config.
        """
        if model_path is None:
            settings = get_ai_settings()
            model_path = settings.models.cnn_model_path
            
        # Ensure path is absolute relative to project root if it is relative
        if not os.path.isabs(model_path):
            model_path = os.path.join(root_dir, model_path)
            
        self.model_path = model_path
        
        logger.info(f"Loading Keras CNN model from: {self.model_path}")
        if not os.path.exists(self.model_path):
            logger.warning(f"CNN model weights not found at {self.model_path}. Falling back to pre-trained MobileNetV2 model.")
            # Fallback to standard pre-trained MobileNetV2 model structure for testing/verification
            self.model = tf.keras.applications.MobileNetV2(weights='imagenet')
        else:
            try:
                self.model = tf.keras.models.load_model(self.model_path)
                logger.info("Keras model loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load Keras model from {self.model_path}: {e}")
                logger.info("Attempting to load weights into MobileNetV2 architecture...")
                try:
                    # If it's a weights-only file, create MobileNetV2 and load weights
                    self.model = tf.keras.applications.MobileNetV2(weights=None, classes=2)
                    self.model.load_weights(self.model_path)
                    logger.info("Successfully loaded weights into MobileNetV2 architecture.")
                except Exception as ex:
                    logger.error(f"Failed to load weights: {ex}. Falling back to pre-trained MobileNetV2.")
                    self.model = tf.keras.applications.MobileNetV2(weights='imagenet')

    def preprocess_image(self, image_path: str) -> np.ndarray:
        """
        Preprocess image to match ImageNet/MobileNetV2 input standards:
        - Resize to 256x256
        - Center crop to 224x224
        - Normalize by ImageNet mean/std
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found at path: {image_path}")
            
        img = Image.open(image_path).convert('RGB')
        
        # Resize
        img = img.resize((256, 256))
        
        # Center crop to 224
        width, height = img.size
        left = (width - 224) / 2
        top = (height - 224) / 2
        right = (width + 224) / 2
        bottom = (height + 224) / 2
        img = img.crop((left, top, right, bottom))
        
        # Convert to float array [0, 1]
        img_array = np.array(img, dtype=np.float32) / 255.0
        
        # Normalize with ImageNet stats
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        img_array = (img_array - mean) / std
        
        # Add batch dimension
        img_array = np.expand_dims(img_array, axis=0)
        return img_array

    def predict(self, image_path: str) -> float:
        """
        Run classification on the image.
        
        Returns:
            The fire risk probability (float score between 0 and 1).
        """
        img_array = self.preprocess_image(image_path)
        
        # Run prediction
        preds = self.model.predict(img_array, verbose=0)
        
        # Parse prediction score
        if preds.shape[1] > 1:
            # If it has multiple classes, return risk probability (index 1 is standard for anomaly/fire)
            confidence = float(preds[0][1])
        else:
            # Sigmoid binary classification output (1 class)
            confidence = float(preds[0][0])
            
        return confidence
