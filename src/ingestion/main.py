#!/usr/bin/env python3
"""
Main entry point for Forest Guard Ingestion Service

Initializes configuration, logging, database connection, and starts TCP server.
"""

import sys
import signal
import logging
from pathlib import Path

# Add project root to path if running directly
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.common.config.settings import get_ingestion_settings
from src.common.utils.logger import setup_logger, get_logger
from src.common.database.connection import get_connection_manager, close_connection_manager
from src.ingestion.server.tcp_server import TCPServer

logger = get_logger(__name__)


def main():
    """Main function"""
    try:
        # Setup basic logging first (before loading config)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        temp_logger = logging.getLogger(__name__)
        
        # Load configuration
        temp_logger.info("Loading ingestion configuration...")
        settings = get_ingestion_settings()
        
        # Setup proper logging with config
        setup_logger(settings.logging)
        logger.info(f"Logging configured: level={settings.logging.level}")
        
        logger.info(f"Configuration loaded: TCP port={settings.server.port}")
        
        # Initialize database connection
        logger.info("Initializing database connection...")
        try:
            db_manager = get_connection_manager()
            if db_manager.health_check():
                logger.info("Database connection healthy")
            else:
                logger.error("Database health check failed - service will continue but database operations may fail")
        except Exception as e:
            logger.error(f"Database connection error: {e} - service will continue but database operations may fail")
        
        # Create and start TCP server
        logger.info("Starting TCP server...")
        server = TCPServer(config=settings.server)
        
        # Setup signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            server.stop()
            close_connection_manager()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start server (blocking)
        server.start()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1
    finally:
        logger.info("Shutting down...")
        close_connection_manager()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
