import os
import sys
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# Add project root to path if running directly
from pathlib import Path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.common.config.settings import get_web_settings, root_dir
from src.common.database.connection import get_connection_manager
from src.common.utils.image_handler import get_image_handler
from src.ingestion.ai_client import trigger_ai_worker

logger = logging.getLogger(__name__)

app = FastAPI(title="ForestGuard Web API Server")

# Load settings
settings = get_web_settings()
IMAGE_DIR = os.path.abspath(settings.storage.image_path)
if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

# Mount the static web_frontend folder
# This allows serving the frontend files at http://localhost:8000/static/
app.mount("/static", StaticFiles(directory=os.path.join(root_dir, "web_frontend")), name="static")

def datetime_handler(x):
    if isinstance(x, datetime):
        return x.isoformat()
    raise TypeError("Unknown type")

def get_latest_device_image(imei: str) -> Optional[str]:
    """Find the latest .jpg image for a given IMEI in the images directory"""
    try:
        if not os.path.exists(IMAGE_DIR):
            return None
        files = [f for f in os.listdir(IMAGE_DIR) if f.startswith(imei) and f.endswith(".jpg")]
        if not files:
            return None
        # Sort by filename (includes timestamp)
        files.sort(reverse=True) 
        return files[0]
    except Exception as e:
        logger.error(f"Error finding latest image for {imei}: {e}")
        return None

@app.get("/")
async def read_root():
    """Serve the Leaflet dashboard UI directly"""
    index_path = os.path.join(root_dir, "web_frontend", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="index.html not found in web_frontend")

@app.get("/api/data")
async def get_data(status: Optional[str] = None):
    """Retrieve telemetry records, optionally filtered by risk status"""
    db_manager = get_connection_manager()
    try:
        with db_manager.get_cursor() as cursor:
            # We fetch columns and support filtering by final_risk_level
            query = """
                SELECT id, device_imei, eco2, tvoc, nh3, h2s, smoke, temperature, humidity, 
                       latitude, longitude, "AI-1" as ai1, "AI-2" as ai2, 
                       final_risk_level, received_at, iccid, gps_altitude, 
                       gps_satellites, gps_fix_quality, rain_sensor, battery_voltage
                FROM data_upload 
            """
            params = []
            if status:
                query += ' WHERE final_risk_level = %s '
                params.append(status)
                
            query += " ORDER BY received_at DESC LIMIT 100"
            
            cursor.execute(query, params)
            records = cursor.fetchall()
            
            # Enhance records with latest image if picture_path is null
            for record in records:
                latest_image = get_latest_device_image(record['device_imei'])
                record['latest_image'] = latest_image
                
            return json.loads(json.dumps(records, default=datetime_handler))
    except Exception as e:
        logger.error(f"Error fetching telemetry: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/data", status_code=201)
async def add_data(payload: dict):
    """
    Consolidated mock data insertion endpoint from the legacy Flask dashboard.
    Receives device telemetry via HTTP and inserts it into database.
    """
    required_fields = ['device_imei', 'latitude', 'longitude']
    for field in required_fields:
        if field not in payload:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    db_manager = get_connection_manager()
    try:
        with db_manager.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO data_upload (
                    device_imei, eco2, tvoc, nh3, h2s, smoke, 
                    temperature, humidity, longitude, latitude, 
                    received_at, generated_at, "AI-1", "AI-2", final_risk_level
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), %s, %s, %s)
                RETURNING id
            """, (
                payload.get('device_imei'), 
                payload.get('eco2'), 
                payload.get('tvoc'), 
                payload.get('nh3'), 
                payload.get('h2s'), 
                payload.get('smoke'),
                payload.get('temperature'), 
                payload.get('humidity'), 
                payload.get('longitude'), 
                payload.get('latitude'), 
                payload.get('ai1'), 
                payload.get('ai2'),
                payload.get('final_risk_level', 'green')
            ))
            result = cursor.fetchone()
            record_id = result['id'] if result else None
            return {"status": "success", "message": "New record added successfully", "id": record_id}
    except Exception as e:
        logger.error(f"Error adding mock data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/data/{record_id}")
async def update_record(record_id: int, payload: dict):
    """Manually update AI scores and risk level (PATCH support)"""
    ai1 = payload.get("ai1")
    ai2 = payload.get("ai2")
    risk = payload.get("final_risk_level")
    
    db_manager = get_connection_manager()
    try:
        with db_manager.get_cursor() as cursor:
            updates = []
            params = []
            if ai1 is not None:
                updates.append('"AI-1" = %s')
                params.append(ai1)
            if ai2 is not None:
                updates.append('"AI-2" = %s')
                params.append(ai2)
            if risk is not None:
                updates.append('final_risk_level = %s')
                params.append(risk)
                
            if not updates:
                return {"status": "ignored"}
                
            params.append(record_id)
            sql = f'UPDATE data_upload SET {", ".join(updates)} WHERE id = %s'
            cursor.execute(sql, params)
            
            return {"status": "success", "message": "Record updated successfully"}
    except Exception as e:
        logger.error(f"Error updating record {record_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/data/{record_id}")
async def update_record_put(record_id: int, payload: dict):
    """PUT compatibility endpoint for updating AI scores"""
    return await update_record(record_id, payload)

@app.delete("/api/data/{record_id}")
async def delete_record(record_id: int):
    """Consolidated delete endpoint from the Flask dashboard"""
    db_manager = get_connection_manager()
    try:
        with db_manager.get_cursor() as cursor:
            cursor.execute("DELETE FROM data_upload WHERE id = %s", (record_id,))
            return {"status": "success", "message": f"Record {record_id} deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting record {record_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ai/pending")
async def get_pending_tasks():
    """AI Service or client pulls this to get records that need AI processing"""
    db_manager = get_connection_manager()
    try:
        with db_manager.get_cursor() as cursor:
            cursor.execute("""
                SELECT id, device_imei, eco2, tvoc, nh3, h2s, temperature, humidity, picture_path
                FROM data_upload 
                WHERE "AI-1" IS NULL 
                ORDER BY received_at ASC LIMIT 10
            """)
            records = cursor.fetchall()
            return json.loads(json.dumps(records, default=datetime_handler))
    except Exception as e:
        logger.error(f"Error fetching pending tasks: {e}")
        return []

@app.get("/api/images/{filename}")
async def get_image(filename: str):
    """Download images for AI-2 analysis or UI display"""
    file_path = os.path.join(IMAGE_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="Image not found")

@app.post("/api/ai_callback")
async def ai_callback(payload: dict):
    """Callback endpoint for the decoupled AI inference service to post predictions"""
    record_id = payload.get("record_id")
    ai1 = payload.get("ai1")
    ai2 = payload.get("ai2")
    risk = payload.get("final_risk_level")
    
    db_manager = get_connection_manager()
    try:
        with db_manager.get_cursor() as cursor:
            cursor.execute("""
                UPDATE data_upload 
                SET "AI-1" = %s, "AI-2" = %s, final_risk_level = %s 
                WHERE id = %s
            """, (ai1, ai2, risk, record_id))
            return {"status": "success", "record_id": record_id}
    except Exception as e:
        logger.error(f"Error in AI callback for record {record_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/trigger_ai/{record_id}")
async def trigger_ai(record_id: int):
    """Manually trigger AI inference for a specific record"""
    db_manager = get_connection_manager()
    try:
        with db_manager.get_cursor() as cursor:
            cursor.execute("SELECT * FROM data_upload WHERE id = %s", (record_id,))
            record = cursor.fetchone()
            if not record:
                raise HTTPException(status_code=404, detail="Record not found")
            
            # Prepare telemetry dictionary for AI worker
            exclude_keys = {'id', 'picture_path', 'AI-1', 'AI-2', 'final_risk_level', 'received_at'}
            data = {k: (v.isoformat() if hasattr(v, 'isoformat') else v) 
                    for k, v in record.items() if k not in exclude_keys}
            
            # Determine image path: use db path if exists, otherwise fallback to latest for this imei
            image_path = record.get('picture_path')
            if not image_path:
                latest_image = get_latest_device_image(record['device_imei'])
                if latest_image:
                    image_path = os.path.join(IMAGE_DIR, latest_image)
            
            success = trigger_ai_worker(record_id, data, image_path)
            if success:
                return {"status": "success", "message": f"AI triggered for record {record_id}"}
            else:
                return {"status": "error", "message": f"Failed to trigger AI for record {record_id}"}
                
    except Exception as e:
        logger.error(f"Error manually triggering AI: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.server.host, port=settings.server.port)
