"""
Message Parser for ZProtocol Data Payload

This module parses the data payload from ZProtocol frames into structured messages.
Works with the parsed ZProtocolMessage.data field.
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass
import re
from src.ingestion.protocol.zprotocol import ZProtocolMessage


@dataclass
class SensorData:
    """Parsed sensor data (Command 0x31)"""
    # Air quality data (14 bytes)
    air_quality: bytes  # Raw air quality data
    
    # GPS data (16 bytes)
    gps_data: bytes  # Raw GPS data
    
    # ADC sensor data (10 bytes)
    adc_data: bytes  # Raw ADC sensor data
    
    # Data validity flag (1 byte)
    validity_flag: int
    
    @property
    def total_length(self) -> int:
        """Total data length: 14 + 16 + 10 + 1 = 41 bytes"""
        return 41


@dataclass
class GPSData:
    """Parsed GPS/Position data (Command 0x36)"""
    # GPS data payload (variable length)
    gps_payload: bytes
    imei: Optional[str] = None  # Extracted from payload if available


@dataclass
class AlarmData:
    """Parsed alarm data (Command 0x35)"""
    # Alarm data payload (variable length)
    alarm_payload: bytes


@dataclass
class ImageChunk:
    """Parsed image chunk data (Command 0x33)"""
    # Image chunk data (binary, not Base64)
    chunk_data: bytes
    chunk_index: Optional[int] = None
    total_chunks: Optional[int] = None


@dataclass
class QueryCommand:
    """Parsed query command (Command 0x38)"""
    # Query command payload
    query_payload: bytes


class MessageParser:
    """Parser for ZProtocol message data payload"""
    
    def __init__(self):
        """Initialize message parser"""
        pass
    
    def parse(self, message: ZProtocolMessage) -> Dict[str, Any]:
        """
        Parse ZProtocol message data payload based on command code
        
        Args:
            message: ZProtocol message with parsed frame
        
        Returns:
            Dictionary with parsed data and metadata
        """
        result = {
            'command': message.command,
            'id': message.id,
            'role': message.role,
            'raw_data': message.data,
            'data_length': len(message.data),
            'parsed': None,
            'error': None
        }
        
        try:
            if message.command == 0x31:
                result['parsed'] = self.parse_sensor_data(message.data)
            elif message.command == 0x33:
                result['parsed'] = self.parse_image_chunk(message.data)
            elif message.command == 0x35:
                result['parsed'] = self.parse_alarm_data(message.data)
            elif message.command == 0x36:
                result['parsed'] = self.parse_gps_data(message.data)
            elif message.command == 0x38:
                result['parsed'] = self.parse_query_command(message.data)
            else:
                result['error'] = f"Unknown command: 0x{message.command:02X}"
                result['parsed'] = {'raw': message.data}
        except Exception as e:
            result['error'] = str(e)
            result['parsed'] = {'raw': message.data}
        
        return result
    
    def parse_sensor_data(self, data: bytes) -> SensorData:
        """
        Parse sensor data (Command 0x31)
        
        Expected structure (41 bytes total):
        - Air quality data: 14 bytes
        - GPS data: 16 bytes
        - ADC sensor data: 10 bytes
        - Validity flag: 1 byte
        
        Args:
            data: Data payload from ZProtocol frame
        
        Returns:
            Parsed SensorData object
        
        Raises:
            ValueError: If data length is incorrect
        """
        if len(data) < 41:
            raise ValueError(f"Sensor data too short: {len(data)} bytes (expected 41)")
        
        return SensorData(
            air_quality=data[0:14],
            gps_data=data[14:30],
            adc_data=data[30:40],
            validity_flag=data[40]
        )
    
    def parse_gps_data(self, data: bytes) -> GPSData:
        """
        Parse GPS/Position data (Command 0x36)
        
        From actual data observed:
        - Format: IMEI (15 digits) + separator + GPS NMEA data
        - Example: "866784062154499" + "8912230000575323639F" + "$GNGGA,..."
        - IMEI appears at the beginning, followed by additional data, then GPS NMEA
        
        Args:
            data: Data payload from ZProtocol frame
        
        Returns:
            Parsed GPSData object
        """
        # Try to extract IMEI from data
        imei = None
        try:
            if len(data) > 0:
                # Decode as ASCII to find IMEI pattern
                data_str = data.decode('ascii', errors='ignore')
                
                # Look for GPS NMEA sentence starting with $
                gps_start = data_str.find('$')
                
                if gps_start > 0:
                    # IMEI is typically 15 digits at the beginning
                    # Extract first part before GPS data
                    prefix = data_str[:gps_start]
                    
                    # Try to find IMEI (15 consecutive digits)
                    imei_match = re.search(r'\d{15}', prefix)
                    if imei_match:
                        imei = imei_match.group(0)
                    else:
                        # Fallback: take first 15 characters if all digits
                        digits_only = ''.join(c for c in prefix if c.isdigit())
                        if len(digits_only) >= 15:
                            imei = digits_only[:15]
        except Exception as e:
            # If parsing fails, just return raw data
            pass
        
        return GPSData(
            gps_payload=data,
            imei=imei
        )
    
    def parse_alarm_data(self, data: bytes) -> AlarmData:
        """
        Parse alarm data (Command 0x35)
        
        Args:
            data: Data payload from ZProtocol frame
        
        Returns:
            Parsed AlarmData object
        """
        return AlarmData(alarm_payload=data)
    
    def parse_image_chunk(self, data: bytes) -> ImageChunk:
        """
        Parse image chunk data (Command 0x33)
        
        Args:
            data: Data payload from ZProtocol frame
        
        Returns:
            Parsed ImageChunk object
        """
        # Image chunk parsing - may need chunk index/total info
        # This depends on the actual protocol implementation
        return ImageChunk(chunk_data=data)
    
    def parse_query_command(self, data: bytes) -> QueryCommand:
        """
        Parse query command (Command 0x38)
        
        Args:
            data: Data payload from ZProtocol frame
        
        Returns:
            Parsed QueryCommand object
        """
        return QueryCommand(query_payload=data)


# Convenience function
def parse_message(message: ZProtocolMessage) -> Dict[str, Any]:
    """
    Parse ZProtocol message (convenience function)
    
    Args:
        message: ZProtocol message to parse
    
    Returns:
        Dictionary with parsed data
    """
    parser = MessageParser()
    return parser.parse(message)
