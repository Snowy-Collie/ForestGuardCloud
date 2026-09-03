import psycopg2
import logging
from src.common.config.settings import get_ingestion_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_and_add_columns():
    try:
        settings = get_ingestion_settings()
        db_cfg = settings.database
        conn = psycopg2.connect(
            host=db_cfg.host,
            port=db_cfg.port,
            database=db_cfg.database,
            user=db_cfg.user,
            password=db_cfg.password
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Check current columns
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'data_upload'
        """)
        columns = [row[0] for row in cursor.fetchall()]
        logger.info(f"Current columns in data_upload: {columns}")
        
        # New columns to add
        new_columns = [
            ("AI-1", "VARCHAR(255)"),
            ("AI-2", "VARCHAR(255)"),
            ("final_risk_level", "VARCHAR(255)")
        ]
        
        for col_name, col_type in new_columns:
            if col_name not in columns:
                logger.info(f"Adding column {col_name} to data_upload")
                try:
                    # Use double quotes for column names with hyphens
                    cursor.execute(f'ALTER TABLE data_upload ADD COLUMN "{col_name}" {col_type}')
                    logger.info(f"Successfully added {col_name}")
                except Exception as e:
                    logger.error(f"Failed to add {col_name}: {e}")
            else:
                logger.info(f"Column {col_name} already exists")
        
        cursor.close()
        conn.close()
        logger.info("Migration check completed")
    except Exception as e:
        logger.error(f"Migration error: {e}")

if __name__ == "__main__":
    check_and_add_columns()
