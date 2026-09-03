"""
TCP Server for Forest Guard AI Service

Handles incoming TCP connections from devices, processes ZProtocol messages,
and stores data to PostgreSQL database.
"""

import socket
import threading
import signal
import logging
from typing import Optional
from contextlib import contextmanager

from src.common.config.settings import ServerConfig, get_ingestion_settings
from src.ingestion.server.client_handler import ClientHandler
from src.common.utils.logger import get_logger

logger = get_logger(__name__)


class TCPServer:
    """TCP Server for receiving device data"""
    
    def __init__(self, config: Optional[ServerConfig] = None):
        """
        Initialize TCP server
        
        Args:
            config: Server configuration. If None, loads from settings
        """
        if config is None:
            settings = get_ingestion_settings()
            config = settings.server
        
        self.config = config
        self.socket: Optional[socket.socket] = None
        self.running = False
        self.client_threads: list[threading.Thread] = []
        self.shutdown_event = threading.Event()
    
    def start(self) -> None:
        """
        Start TCP server
        
        Raises:
            OSError: If server fails to start
        """
        if self.running:
            logger.warning("Server is already running")
            return
        
        try:
            # Create socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind to address
            self.socket.bind((self.config.host, self.config.port))
            self.socket.listen(10)  # Allow up to 10 pending connections
            
            self.running = True
            logger.info(f"TCP server started on {self.config.host}:{self.config.port}")
            
            # Start accepting connections
            self._accept_connections()
            
        except Exception as e:
            logger.error(f"Failed to start TCP server: {e}", exc_info=True)
            self.running = False
            raise
    
    def _accept_connections(self) -> None:
        """Accept incoming client connections"""
        while self.running and not self.shutdown_event.is_set():
            try:
                # Set socket timeout to allow periodic checking of shutdown event
                self.socket.settimeout(1.0)
                
                try:
                    client_socket, client_address = self.socket.accept()
                except socket.timeout:
                    # Timeout is expected, continue to check shutdown event
                    continue
                except OSError as e:
                    if self.running:
                        logger.error(f"Error accepting connection: {e}")
                    break
                
                # Create client handler thread
                client_handler = ClientHandler(client_socket, client_address)
                thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_handler,),
                    daemon=True
                )
                thread.start()
                self.client_threads.append(thread)
                
                logger.info(f"Client connected: {client_address}")
                
            except Exception as e:
                if self.running:
                    logger.error(f"Error in accept loop: {e}", exc_info=True)
    
    def _handle_client(self, client_handler: ClientHandler) -> None:
        """
        Handle client connection in separate thread
        
        Args:
            client_handler: Client handler instance
        """
        try:
            client_handler.handle()
        except Exception as e:
            logger.error(f"Error handling client {client_handler.client_address}: {e}", exc_info=True)
        finally:
            logger.info(f"Client disconnected: {client_handler.client_address}")
    
    def stop(self) -> None:
        """Stop TCP server gracefully"""
        if not self.running:
            return
        
        logger.info("Stopping TCP server...")
        self.running = False
        self.shutdown_event.set()
        
        # Close server socket
        if self.socket is not None:
            try:
                self.socket.close()
            except Exception as e:
                logger.error(f"Error closing server socket: {e}")
        
        # Wait for client threads to finish (with timeout)
        for thread in self.client_threads[:]:
            if thread.is_alive():
                thread.join(timeout=5.0)
                if thread.is_alive():
                    logger.warning(f"Client thread did not finish within timeout")
        
        self.client_threads.clear()
        logger.info("TCP server stopped")
    
    def is_running(self) -> bool:
        """Check if server is running"""
        return self.running


def run_server(config: Optional[ServerConfig] = None) -> None:
    """
    Run TCP server (blocking)
    
    Args:
        config: Server configuration. If None, loads from settings
    """
    server = TCPServer(config)
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        server.stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        server.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
    finally:
        server.stop()


if __name__ == "__main__":
    # Run server directly
    run_server()
