"""
Logging configuration for Forest Guard AI Service
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

from src.common.config.settings import LoggingConfig


def setup_logger(config: LoggingConfig) -> logging.Logger:
    """
    Setup application logger with file and console handlers
    
    Args:
        config: Logging configuration
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger('forestguard_service')
    logger.setLevel(getattr(logging, config.level.upper(), logging.INFO))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    if config.console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # File handler
    if config.file:
        log_path = Path(config.file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            config.file,
            maxBytes=config.max_bytes,
            backupCount=config.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get logger instance
    
    Args:
        name: Optional logger name (default: 'forestguard_service')
    
    Returns:
        Logger instance
    """
    if name:
        return logging.getLogger(f'forestguard_service.{name}')
    return logging.getLogger('forestguard_service')


