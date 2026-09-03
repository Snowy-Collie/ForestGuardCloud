"""
Unified configuration management for ForestGuard AI components.
Supports loading from a component-specific YAML file and overriding with environment variables.
"""
import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Resolve root workspace directory (ForestGuard-AI/)
# Path(__file__) is at: src/common/config/settings.py
# resolve().parents[3] goes up to ForestGuard-AI/
root_dir = Path(__file__).resolve().parents[3]

# Load environment variables from .env file if present
load_dotenv(dotenv_path=root_dir / ".env")
load_dotenv(dotenv_path=root_dir / "config" / ".env")

@dataclass
class ServerConfig:
    """Server host/port configuration"""
    host: str = "0.0.0.0"
    port: int = 20000

@dataclass
class DatabaseConfig:
    """PostgreSQL database configuration"""
    host: str = "a-postgresql.wezhike.ca"
    port: int = 5432
    database: str = "fap"
    user: str = "fap"
    password: str = ""

@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    file: Optional[str] = None
    console: bool = True
    max_bytes: int = 10485760  # 10MB
    backup_count: int = 5

@dataclass
class StorageConfig:
    """Centralized storage configuration"""
    data_storage_dir: str = "./data_storage"

    @property
    def image_path(self) -> str:
        return os.path.join(self.data_storage_dir, "images")

    @property
    def log_path(self) -> str:
        return os.path.join(self.data_storage_dir, "logs")

@dataclass
class AIConfig:
    """AI Worker configuration"""
    worker_url: str = "http://localhost:8001/process"
    callback_url: str = "http://localhost:8000/api/ai_callback"

@dataclass
class ModelsConfig:
    """AI Models configuration"""
    xgboost_model_path: str = "src/ai_service/models/ai1_model.json"
    cnn_model_path: str = "src/ai_service/models/forest_fire_ai2_weights.h5"

@dataclass
class ThresholdsConfig:
    """AI Decision thresholds"""
    ai1_risk_threshold: float = 0.6
    ai2_alert_threshold: float = 0.8

@dataclass
class Settings:
    """Application settings"""
    server: ServerConfig = field(default_factory=ServerConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    models: ModelsConfig = field(default_factory=ModelsConfig)
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)

    @classmethod
    def load_from_file(cls, config_filename: str) -> 'Settings':
        """
        Load configuration from a specific YAML file.
        
        Args:
            config_filename: The name of the config file under config/ (e.g. 'ingestion.yaml')
        """
        # Try to find config under root/config/ or src/common/config/ or current directory
        possible_paths = [
            root_dir / "config" / config_filename,
            Path(__file__).resolve().parents[2] / "config" / config_filename,
            Path(config_filename)
        ]
        
        config_path = None
        for p in possible_paths:
            if p.exists():
                config_path = p
                break
                
        config_data = {}
        if config_path:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}
                
        # Override with environment variables
        config_data = cls._apply_env_overrides(config_data)
        
        return cls._from_dict(config_data)

    @classmethod
    def _apply_env_overrides(cls, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variables to override yaml settings"""
        # Server
        if 'server' not in config_data:
            config_data['server'] = {}
        if 'TCP_PORT' in os.environ:
            config_data['server']['port'] = int(os.environ['TCP_PORT'])
        if 'TCP_HOST' in os.environ:
            config_data['server']['host'] = os.environ['TCP_HOST']
        if 'WEB_PORT' in os.environ:
            config_data['server']['port'] = int(os.environ['WEB_PORT'])
        if 'WEB_HOST' in os.environ:
            config_data['server']['host'] = os.environ['WEB_HOST']
        if 'AI_PORT' in os.environ:
            config_data['server']['port'] = int(os.environ['AI_PORT'])
        if 'AI_HOST' in os.environ:
            config_data['server']['host'] = os.environ['AI_HOST']

        # Database
        if 'database' not in config_data:
            config_data['database'] = {}
        if 'DB_HOST' in os.environ:
            config_data['database']['host'] = os.environ['DB_HOST']
        if 'DB_PORT' in os.environ:
            config_data['database']['port'] = int(os.environ['DB_PORT'])
        if 'DB_NAME' in os.environ:
            config_data['database']['database'] = os.environ['DB_NAME']
        if 'DB_USER' in os.environ:
            config_data['database']['user'] = os.environ['DB_USER']
        if 'DB_PASSWORD' in os.environ:
            config_data['database']['password'] = os.environ['DB_PASSWORD']

        # Storage
        if 'storage' not in config_data:
            config_data['storage'] = {}
        if 'DATA_STORAGE_DIR' in os.environ:
            config_data['storage']['data_storage_dir'] = os.environ['DATA_STORAGE_DIR']

        # Logging
        if 'logging' not in config_data:
            config_data['logging'] = {}
        if 'LOG_LEVEL' in os.environ:
            config_data['logging']['level'] = os.environ['LOG_LEVEL']

        # AI Client Callbacks
        if 'ai' not in config_data:
            config_data['ai'] = {}
        if 'AI_WORKER_URL' in os.environ:
            config_data['ai']['worker_url'] = os.environ['AI_WORKER_URL']
        if 'AI_CALLBACK_URL' in os.environ:
            config_data['ai']['callback_url'] = os.environ['AI_CALLBACK_URL']

        return config_data

    @classmethod
    def _from_dict(cls, config_data: Dict[str, Any]) -> 'Settings':
        server_data = config_data.get('server', {})
        database_data = config_data.get('database', {})
        logging_data = config_data.get('logging', {})
        storage_data = config_data.get('storage', {})
        ai_data = config_data.get('ai', {})
        models_data = config_data.get('models', {})
        thresholds_data = config_data.get('thresholds', {})

        return cls(
            server=ServerConfig(
                host=server_data.get('host', '0.0.0.0'),
                port=server_data.get('port', 20000)
            ),
            database=DatabaseConfig(
                host=database_data.get('host', 'a-postgresql.wezhike.ca'),
                port=database_data.get('port', 5432),
                database=database_data.get('database', 'fap'),
                user=database_data.get('user', 'fap'),
                password=database_data.get('password', '')
            ),
            logging=LoggingConfig(
                level=logging_data.get('level', 'INFO'),
                file=logging_data.get('file'),
                console=logging_data.get('console', True),
                max_bytes=logging_data.get('max_bytes', 10485760),
                backup_count=logging_data.get('backup_count', 5)
            ),
            storage=StorageConfig(
                data_storage_dir=storage_data.get('data_storage_dir', './data_storage')
            ),
            ai=AIConfig(
                worker_url=ai_data.get('worker_url', 'http://localhost:8001/process'),
                callback_url=ai_data.get('callback_url', 'http://localhost:8000/api/ai_callback')
            ),
            models=ModelsConfig(
                xgboost_model_path=models_data.get('xgboost_model_path', 'src/ai_service/models/ai1_model.json'),
                cnn_model_path=models_data.get('cnn_model_path', 'src/ai_service/models/forest_fire_ai2_weights.h5')
            ),
            thresholds=ThresholdsConfig(
                ai1_risk_threshold=thresholds_data.get('ai1_risk_threshold', 0.6),
                ai2_alert_threshold=thresholds_data.get('ai2_alert_threshold', 0.8)
            )
        )

    def validate(self) -> None:
        """Validate critical configuration fields"""
        if not (1 <= self.server.port <= 65535):
            raise ValueError(f"Invalid server port: {self.server.port}")
        
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.logging.level.upper() not in valid_log_levels:
            raise ValueError(f"Invalid log level: {self.logging.level}")

# Singleton references for each component
_ingestion_settings: Optional[Settings] = None
_ai_settings: Optional[Settings] = None
_web_settings: Optional[Settings] = None

def get_ingestion_settings() -> Settings:
    global _ingestion_settings
    if _ingestion_settings is None:
        _ingestion_settings = Settings.load_from_file("ingestion.yaml")
        _ingestion_settings.validate()
    return _ingestion_settings

def get_ai_settings() -> Settings:
    global _ai_settings
    if _ai_settings is None:
        _ai_settings = Settings.load_from_file("ai_service.yaml")
        _ai_settings.validate()
    return _ai_settings

def get_web_settings() -> Settings:
    global _web_settings
    if _web_settings is None:
        _web_settings = Settings.load_from_file("web_config.yaml")
        _web_settings.validate()
    return _web_settings
