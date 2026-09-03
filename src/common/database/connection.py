"""
Database connection management module

Provides PostgreSQL connection pool, retry mechanism, and health checks.
"""

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from typing import Optional, Dict, Any
import logging
import time
from contextlib import contextmanager

from src.common.config.settings import DatabaseConfig, get_ingestion_settings

logger = logging.getLogger(__name__)


class DatabaseConnectionManager:
    """PostgreSQL connection pool manager"""
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        """
        Initialize database connection manager
        
        Args:
            config: Database configuration. If None, loads from settings
        """
        if config is None:
            settings = get_ingestion_settings()
            config = settings.database
        
        self.config = config
        self.pool: Optional[pool.ThreadedConnectionPool] = None
        self.min_connections = 2
        self.max_connections = 10
        
    def create_pool(self) -> None:
        """Create connection pool"""
        if self.pool is not None:
            logger.warning("Connection pool already exists, closing existing pool")
            self.close_pool()
        
        try:
            logger.info(f"Creating connection pool to {self.config.host}:{self.config.port}/{self.config.database}")
            
            self.pool = pool.ThreadedConnectionPool(
                self.min_connections,
                self.max_connections,
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password,
                cursor_factory=RealDictCursor
            )
            
            logger.info("Connection pool created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
            raise
    
    def close_pool(self) -> None:
        """Close connection pool"""
        if self.pool is not None:
            self.pool.closeall()
            self.pool = None
            logger.info("Connection pool closed")
    
    def get_connection(self, retry_count: int = 3, retry_delay: float = 1.0):
        """
        Get connection from pool with retry mechanism
        
        Args:
            retry_count: Number of retry attempts
            retry_delay: Delay between retries in seconds
        
        Returns:
            Database connection
        
        Raises:
            psycopg2.Error: If connection fails after retries
        """
        if self.pool is None:
            self.create_pool()
        
        last_error = None
        for attempt in range(retry_count):
            try:
                conn = self.pool.getconn()
                if conn is None:
                    raise psycopg2.OperationalError("Failed to get connection from pool")
                
                # Verify connection is alive
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                
                return conn
                
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                last_error = e
                logger.warning(f"Connection attempt {attempt + 1}/{retry_count} failed: {e}")
                
                if attempt < retry_count - 1:
                    time.sleep(retry_delay)
                    # Try to recreate pool if connection failed
                    if attempt == retry_count - 2:
                        logger.info("Attempting to recreate connection pool...")
                        self.close_pool()
                        try:
                            self.create_pool()
                        except Exception as pool_error:
                            logger.error(f"Failed to recreate pool: {pool_error}")
        
        # All retries failed
        logger.error(f"Failed to get connection after {retry_count} attempts")
        raise psycopg2.OperationalError(f"Failed to get connection: {last_error}") from last_error
    
    def return_connection(self, conn) -> None:
        """
        Return connection to pool
        
        Args:
            conn: Database connection to return
        """
        if self.pool is not None and conn is not None:
            try:
                self.pool.putconn(conn)
            except Exception as e:
                logger.error(f"Error returning connection to pool: {e}")
                # Try to close the connection if returning fails
                try:
                    conn.close()
                except Exception:
                    pass
    
    def health_check(self) -> bool:
        """
        Check database connection health
        
        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            conn = self.get_connection(retry_count=1, retry_delay=0.5)
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                return True
            finally:
                self.return_connection(conn)
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    @contextmanager
    def get_cursor(self, commit: bool = True):
        """
        Context manager for database cursor
        
        Args:
            commit: Whether to commit transaction on success
        
        Yields:
            Database cursor
        
        Example:
            with db_manager.get_cursor() as cursor:
                cursor.execute("SELECT * FROM data_upload")
                result = cursor.fetchall()
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            yield cursor
            
            if commit:
                conn.commit()
            else:
                conn.rollback()
                
        except Exception as e:
            if conn is not None:
                conn.rollback()
            logger.error(f"Database operation failed: {e}")
            raise
        finally:
            if cursor is not None:
                cursor.close()
            if conn is not None:
                self.return_connection(conn)
    
    def __enter__(self):
        """Context manager entry"""
        self.create_pool()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close_pool()


# Global connection manager instance
_connection_manager: Optional[DatabaseConnectionManager] = None


def get_connection_manager(config: Optional[DatabaseConfig] = None) -> DatabaseConnectionManager:
    """
    Get global database connection manager instance
    
    Args:
        config: Database configuration. If None, uses settings
    
    Returns:
        DatabaseConnectionManager instance
    """
    global _connection_manager
    
    if _connection_manager is None:
        _connection_manager = DatabaseConnectionManager(config)
        _connection_manager.create_pool()
    
    return _connection_manager


def close_connection_manager() -> None:
    """Close global connection manager"""
    global _connection_manager
    
    if _connection_manager is not None:
        _connection_manager.close_pool()
        _connection_manager = None
