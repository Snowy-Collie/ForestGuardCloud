"""
Database models and data insertion logic

Handles data mapping from protocol messages to database tables.
"""

import struct
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from dataclasses import dataclass

from src.common.database.connection import DatabaseConnectionManager, get_connection_manager

logger = logging.getLogger(__name__)


@dataclass
class ParsedSensorData:
    """Parsed sensor data from 0x31 command (v2.3 protocol)"""
    # Device identification (from TCP frame prefix)
    imei: str
    iccid: Optional[str] = None
    
    # Air quality data
    eco2: Optional[float] = None  # ppm
    ech2o: Optional[float] = None  # ppb
    tvoc: Optional[float] = None  # ppb
    pm25: Optional[float] = None  # µg/m³
    pm10: Optional[float] = None  # µg/m³
    temperature: Optional[float] = None  # °C
    humidity: Optional[float] = None  # %RH
    
    # GPS data
    latitude: Optional[float] = None  # degrees
    longitude: Optional[float] = None  # degrees
    gps_altitude: Optional[int] = None  # meters
    gps_satellites: Optional[int] = None  # count
    gps_fix_quality: Optional[int] = None  # 0=无效, 1=GPS, 2=DGPS
    timestamp: Optional[datetime] = None  # Unix timestamp -> datetime
    
    # Sensor physical values (v2.3 protocol)
    smoke: Optional[float] = None  # mV (sensor_values[0] / 1000.0)
    nh3: Optional[float] = None  # mV (sensor_values[1] / 1000.0)
    h2s: Optional[float] = None  # mV (sensor_values[2] / 1000.0)
    rain_sensor: Optional[float] = None  # mV (sensor_values[3])
    battery_voltage: Optional[float] = None  # V (sensor_values[4] / 1000.0)
    
    # Flags
    flags: int = 0  # Bit0=空气质量有效, Bit1=GPS有效


class DataModel:
    """Database data model and insertion logic"""
    
    def __init__(self, db_manager: Optional[DatabaseConnectionManager] = None):
        """
        Initialize data model
        
        Args:
            db_manager: Database connection manager. If None, uses global instance
        """
        self.db_manager = db_manager or get_connection_manager()
    
    @staticmethod
    def parse_sensor_data_payload(
        payload: bytes,
        imei: str,
        iccid: Optional[str] = None
    ) -> ParsedSensorData:
        """
        Parse 0x31 command PAYLOAD (41 bytes) into structured data
        
        Args:
            payload: 41-byte payload from 0x31 command
            imei: Device IMEI (from TCP frame prefix)
            iccid: Device ICCID (from TCP frame prefix, optional)
        
        Returns:
            ParsedSensorData object
        
        Raises:
            ValueError: If payload length is incorrect
        """
        if len(payload) < 41:
            raise ValueError(f"Sensor data payload too short: {len(payload)} bytes (expected 41)")
        
        # Air quality data (0-13 bytes)
        eco2 = struct.unpack('<H', payload[0:2])[0]
        ech2o = struct.unpack('<H', payload[2:4])[0]
        tvoc = struct.unpack('<H', payload[4:6])[0]
        pm25 = struct.unpack('<H', payload[6:8])[0]
        pm10 = struct.unpack('<H', payload[8:10])[0]
        temperature_raw = struct.unpack('<h', payload[10:12])[0]  # int16
        temperature = temperature_raw / 10.0  # Always convert, 0 is valid temperature
        humidity_raw = struct.unpack('<H', payload[12:14])[0]  # uint16
        humidity = humidity_raw / 10.0  # Always convert, 0 is valid humidity
        
        # GPS data (14-29 bytes)
        latitude_raw = struct.unpack('<i', payload[14:18])[0]  # int32
        latitude = latitude_raw / 1e7 if latitude_raw != 0 else None  # ÷1e7, 0 means invalid
        longitude_raw = struct.unpack('<i', payload[18:22])[0]  # int32
        longitude = longitude_raw / 1e7 if longitude_raw != 0 else None  # ÷1e7, 0 means invalid
        gps_altitude = struct.unpack('<H', payload[22:24])[0]  # uint16
        gps_satellites = payload[24]  # uint8
        gps_fix_quality = payload[25]  # uint8
        timestamp_uint32 = struct.unpack('<I', payload[26:30])[0]  # uint32
        timestamp = datetime.fromtimestamp(timestamp_uint32, tz=timezone.utc) if timestamp_uint32 > 0 else None
        
        # Sensor physical values (30-39 bytes, v2.3 protocol)
        sensor_values = struct.unpack('<5H', payload[30:40])  # 5 × uint16
        smoke = sensor_values[0] / 1000.0  # mV × 1000 -> mV
        nh3 = sensor_values[1] / 1000.0  # mV × 1000 -> mV
        h2s = sensor_values[2] / 1000.0  # mV × 1000 -> mV
        rain_sensor = float(sensor_values[3])  # mV (direct)
        battery_voltage = sensor_values[4] / 1000.0  # mV -> V (真实电池电压，已补偿分压)
        
        # Flags (40 bytes)
        flags = payload[40]
        
        return ParsedSensorData(
            imei=imei,
            iccid=iccid,
            eco2=float(eco2),
            ech2o=float(ech2o),
            tvoc=float(tvoc),
            pm25=float(pm25),
            pm10=float(pm10),
            temperature=temperature,
            humidity=humidity,
            latitude=latitude,
            longitude=longitude,
            gps_altitude=int(gps_altitude),
            gps_satellites=int(gps_satellites),
            gps_fix_quality=int(gps_fix_quality),
            timestamp=timestamp,
            smoke=smoke,
            nh3=nh3,
            h2s=h2s,
            rain_sensor=rain_sensor,
            battery_voltage=battery_voltage,
            flags=flags
        )
    
    @staticmethod
    def calculate_upload_type(flags: int, has_image: bool = False) -> int:
        """
        Calculate upload_type bitmask from flags and data content
        
        Args:
            flags: Flags byte from sensor data (Bit0=空气质量有效, Bit1=GPS有效)
            has_image: Whether image data is included
        
        Returns:
            upload_type bitmask value
        """
        upload_type = 0
        
        # Bit0: 空气质量数据有效 -> 设置空气质量数据位
        if flags & 0x01:
            upload_type |= 0x01  # 空气质量数据（第一部分）
            upload_type |= 0x02  # 空气质量数据（第二部分）
        
        # Bit1: GPS 数据有效 -> 设置GPS数据位（Bit 3）
        if flags & 0x02:
            upload_type |= 0x08  # GPS 数据
        
        # 如果有图片数据
        if has_image:
            upload_type |= 0x04  # 图片数据（Bit 2）
        
        return upload_type
    
    def get_last_known_gps(self, imei: str) -> Dict[str, Any]:
        """
        Get the known GPS coordinates for a device.
        Uses the earliest recorded GPS as per user request: "使用最早一次這個設備的所在位置"
        
        Args:
            imei: Device IMEI
            
        Returns:
            Dictionary with GPS fields or empty dict if not found
        """
        try:
            # User requested "earliest" (最早一次): ORDER BY generated_at ASC
            sql = """
                SELECT latitude, longitude, gps_altitude, gps_satellites, gps_fix_quality
                FROM data_upload
                WHERE device_imei = %s 
                  AND latitude IS NOT NULL 
                  AND longitude IS NOT NULL
                  AND latitude != 0
                  AND longitude != 0
                ORDER BY generated_at ASC
                LIMIT 1
            """
            with self.db_manager.get_cursor() as cursor:
                cursor.execute(sql, (imei,))
                result = cursor.fetchone()
                if result:
                    return result
        except Exception as e:
            logger.error(f"Failed to get last known GPS for IMEI {imei}: {e}")
        return {}

    def insert_sensor_data(self, sensor_data: ParsedSensorData) -> Optional[int]:
        """
        Insert sensor data (0x31 command) into data_upload table
        
        Args:
            sensor_data: Parsed sensor data
        
        Returns:
            Inserted record ID, or None if failed
        """
        try:
            # Calculate upload_type from flags
            upload_type = self.calculate_upload_type(sensor_data.flags)
            
            # GPS fallback logic: If GPS is missing, use the earliest known position for this device
            if sensor_data.latitude is None or sensor_data.longitude is None:
                last_gps = self.get_last_known_gps(sensor_data.imei)
                if last_gps:
                    sensor_data.latitude = last_gps.get('latitude')
                    sensor_data.longitude = last_gps.get('longitude')
                    
                    # Fill other GPS fields if they are missing or zero
                    if not sensor_data.gps_altitude:
                        sensor_data.gps_altitude = last_gps.get('gps_altitude')
                    if not sensor_data.gps_satellites:
                        sensor_data.gps_satellites = last_gps.get('gps_satellites')
                    if not sensor_data.gps_fix_quality:
                        sensor_data.gps_fix_quality = last_gps.get('gps_fix_quality')
                    
                    # Ensure upload_type reflects that we now have GPS data
                    upload_type |= 0x08
                    logger.info(f"Using fallback GPS for IMEI {sensor_data.imei}: "
                                f"{sensor_data.latitude}, {sensor_data.longitude}")

            # Prepare SQL insert statement
            sql = """
                INSERT INTO data_upload (
                    device_imei, iccid,
                    upload_type, record_type,
                    eco2, ech2o, tvoc, pm25, pm10, temperature, humidity,
                    latitude, longitude, gps_altitude, gps_satellites, gps_fix_quality,
                    smoke, nh3, h2s, rain_sensor, battery_voltage,
                    generated_at, received_at,
                    error_flags, record_status
                ) VALUES (
                    %(imei)s, %(iccid)s,
                    %(upload_type)s, 0,
                    %(eco2)s, %(ech2o)s, %(tvoc)s, %(pm25)s, %(pm10)s, %(temperature)s, %(humidity)s,
                    %(latitude)s, %(longitude)s, %(gps_altitude)s, %(gps_satellites)s, %(gps_fix_quality)s,
                    %(smoke)s, %(nh3)s, %(h2s)s, %(rain_sensor)s, %(battery_voltage)s,
                    %(generated_at)s, NOW(),
                    0, 0
                )
                RETURNING id
            """
            
            # Prepare data dictionary
            # Note: All fields are included, NULL values are allowed
            # Flags are used for upload_type calculation, but data is stored regardless
            data = {
                'imei': sensor_data.imei,
                'iccid': sensor_data.iccid,
                'upload_type': upload_type,
                'eco2': sensor_data.eco2,
                'ech2o': sensor_data.ech2o,
                'tvoc': sensor_data.tvoc,
                'pm25': sensor_data.pm25,
                'pm10': sensor_data.pm10,
                'temperature': sensor_data.temperature,
                'humidity': sensor_data.humidity,
                'latitude': sensor_data.latitude,
                'longitude': sensor_data.longitude,
                'gps_altitude': sensor_data.gps_altitude,
                'gps_satellites': sensor_data.gps_satellites,
                'gps_fix_quality': sensor_data.gps_fix_quality,
                'smoke': sensor_data.smoke,
                'nh3': sensor_data.nh3,
                'h2s': sensor_data.h2s,
                'rain_sensor': sensor_data.rain_sensor,
                'battery_voltage': sensor_data.battery_voltage,
                'generated_at': sensor_data.timestamp,
            }
            
            # Execute insert
            with self.db_manager.get_cursor() as cursor:
                cursor.execute(sql, data)
                result = cursor.fetchone()
                record_id = result['id'] if result else None
                
                logger.info(f"Inserted sensor data: record_id={record_id}, imei={sensor_data.imei}")
                return record_id
                
        except Exception as e:
            logger.error(f"Failed to insert sensor data: {e}", exc_info=True)
            return None
    
    def insert_alarm_data(self, alarm_data: Dict[str, Any], imei: str, iccid: Optional[str] = None) -> Optional[int]:
        """
        Insert alarm data (0x35 command) into data_upload table.
        Uses GPS fallback if available.
        
        Args:
            alarm_data: Parsed alarm data dictionary
            imei: Device IMEI
            iccid: Device ICCID (optional)
        
        Returns:
            Inserted record ID, or None if failed
        """
        try:
            # GPS fallback for alarm records
            last_gps = self.get_last_known_gps(imei)
            
            sql = """
                INSERT INTO data_upload (
                    device_imei, iccid,
                    upload_type, record_type,
                    latitude, longitude, gps_altitude, gps_satellites, gps_fix_quality,
                    generated_at, received_at,
                    error_flags, record_status
                ) VALUES (
                    %(imei)s, %(iccid)s,
                    %(upload_type)s, 2,  -- record_type: 2 = alarm
                    %(latitude)s, %(longitude)s, %(gps_altitude)s, %(gps_satellites)s, %(gps_fix_quality)s,
                    NOW(), NOW(),
                    0, 0
                )
                RETURNING id
            """
            
            upload_type = 0
            if last_gps:
                upload_type |= 8 # GPS bit (Bit 3)
            
            data = {
                'imei': imei,
                'iccid': iccid,
                'upload_type': upload_type,
                'latitude': last_gps.get('latitude') if last_gps else None,
                'longitude': last_gps.get('longitude') if last_gps else None,
                'gps_altitude': last_gps.get('gps_altitude') if last_gps else None,
                'gps_satellites': last_gps.get('gps_satellites') if last_gps else None,
                'gps_fix_quality': last_gps.get('gps_fix_quality') if last_gps else None,
            }
            
            with self.db_manager.get_cursor() as cursor:
                cursor.execute(sql, data)
                result = cursor.fetchone()
                record_id = result['id'] if result else None
                
                logger.info(f"Inserted alarm data: record_id={record_id}, imei={imei}")
                return record_id
                
        except Exception as e:
            logger.error(f"Failed to insert alarm data: {e}", exc_info=True)
            return None
    
    def update_image_path(self, record_id: int, image_path: str) -> bool:
        """
        Update picture_path for a record (0x33 command)
        
        Args:
            record_id: Record ID to update
            image_path: Path to the image file
        
        Returns:
            True if update successful, False otherwise
        """
        try:
            sql = """
                UPDATE data_upload
                SET picture_path = %(image_path)s,
                    upload_type = upload_type | 4  -- Set image bit (Bit 2)
                WHERE id = %(record_id)s
            """
            
            data = {
                'image_path': image_path,
                'record_id': record_id
            }
            
            with self.db_manager.get_cursor() as cursor:
                cursor.execute(sql, data)
                if cursor.rowcount > 0:
                    logger.info(f"Updated image path: record_id={record_id}, path={image_path}")
                    return True
                else:
                    logger.warning(f"No record found to update: record_id={record_id}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to update image path: {e}", exc_info=True)
            return False

    def insert_image_record(self, imei: str, image_path: str, iccid: Optional[str] = None) -> Optional[int]:
        """
        Create a new record for an image that doesn't have a preceding sensor record.
        Uses GPS fallback if available.
        
        Args:
            imei: Device IMEI
            image_path: Path to the image file
            iccid: Device ICCID (optional)
            
        Returns:
            Inserted record ID, or None if failed
        """
        try:
            # GPS fallback for image records
            last_gps = self.get_last_known_gps(imei)
            
            sql = """
                INSERT INTO data_upload (
                    device_imei, iccid,
                    upload_type, record_type,
                    picture_path,
                    latitude, longitude, gps_altitude, gps_satellites, gps_fix_quality,
                    generated_at, received_at,
                    error_flags, record_status
                ) VALUES (
                    %(imei)s, %(iccid)s,
                    %(upload_type)s, 1, -- record_type: 1 = image
                    %(image_path)s,
                    %(latitude)s, %(longitude)s, %(gps_altitude)s, %(gps_satellites)s, %(gps_fix_quality)s,
                    NOW(), NOW(),
                    0, 0
                )
                RETURNING id
            """
            
            upload_type = 4 # Image bit (Bit 2)
            if last_gps:
                upload_type |= 8 # GPS bit (Bit 3)
            
            data = {
                'imei': imei,
                'iccid': iccid,
                'upload_type': upload_type,
                'image_path': image_path,
                'latitude': last_gps.get('latitude') if last_gps else None,
                'longitude': last_gps.get('longitude') if last_gps else None,
                'gps_altitude': last_gps.get('gps_altitude') if last_gps else None,
                'gps_satellites': last_gps.get('gps_satellites') if last_gps else None,
                'gps_fix_quality': last_gps.get('gps_fix_quality') if last_gps else None,
            }
            
            with self.db_manager.get_cursor() as cursor:
                cursor.execute(sql, data)
                result = cursor.fetchone()
                record_id = result['id'] if result else None
                
                logger.info(f"Inserted image record: record_id={record_id}, imei={imei}")
                return record_id
                
        except Exception as e:
            logger.error(f"Failed to insert image record: {e}", exc_info=True)
            return None
    
    def insert_sensor_data_from_payload(
        self,
        payload: bytes,
        imei: str,
        iccid: Optional[str] = None
    ) -> Optional[int]:
        """
        Parse and insert sensor data from raw payload (convenience method)
        
        Args:
            payload: 41-byte payload from 0x31 command
            imei: Device IMEI
            iccid: Device ICCID (optional)
        
        Returns:
            Inserted record ID, or None if failed
        """
        try:
            sensor_data = self.parse_sensor_data_payload(payload, imei, iccid)
            return self.insert_sensor_data(sensor_data)
        except Exception as e:
            logger.error(f"Failed to parse and insert sensor data: {e}", exc_info=True)
            return None
