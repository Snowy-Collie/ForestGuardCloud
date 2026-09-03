"""
Client Handler for TCP Server

Handles individual client connections, parses ZProtocol frames,
extracts device information (IMEI/ICCID), and stores data to database.
"""

import socket
import struct
import logging
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass

from src.ingestion.protocol.zprotocol import ZProtocolDecoder, ROLE_MASTER, ZProtocolMessage
from src.ingestion.protocol.message_parser import MessageParser
from src.common.database.models import DataModel
from src.common.database.connection import get_connection_manager
from src.common.utils.logger import get_logger
from src.common.utils.image_handler import get_image_handler, ImageHandler
from src.ingestion.ai_client import trigger_ai_worker

logger = get_logger(__name__)


@dataclass
class TCPFramePrefix:
    """Parsed TCP frame prefix (extracted from ZProtocol DATA)"""
    imei: str
    iccid: Optional[str]
    payload: bytes
    total_length: int  # Total ZProtocol DATA length


class ClientHandler:
    """Handler for individual client connections"""
    
    # Connection timeout (seconds)
    CONNECTION_TIMEOUT = 300  # 5 minutes
    
    # Receive buffer size
    RECV_BUFFER_SIZE = 4096
    
    def __init__(self, client_socket: socket.socket, client_address: Tuple[str, int]):
        """
        Initialize client handler
        
        Args:
            client_socket: Client socket
            client_address: Client address tuple (host, port)
        """
        self.client_socket = client_socket
        self.client_address = client_address
        self.zprotocol_decoder = ZProtocolDecoder(role=ROLE_MASTER)
        self.message_parser = MessageParser()
        self.data_model = DataModel()
        self.image_handler = get_image_handler()
        
        # Buffer for incomplete frames
        self.receive_buffer = bytearray()
        
        # Track last sensor data record ID for image association
        self.last_sensor_record_id: Optional[int] = None
        
        # Set socket timeout
        self.client_socket.settimeout(self.CONNECTION_TIMEOUT)
    
    def handle(self) -> None:
        """Handle client connection (main loop)"""
        try:
            while True:
                # Receive data
                try:
                    data = self.client_socket.recv(self.RECV_BUFFER_SIZE)
                except socket.timeout:
                    logger.warning(f"Client {self.client_address} timeout")
                    break
                except socket.error as e:
                    logger.error(f"Socket error for {self.client_address}: {e}")
                    break
                
                if not data:
                    # Client closed connection
                    logger.debug(f"Client {self.client_address} closed connection")
                    break
                
                # Add to buffer
                self.receive_buffer.extend(data)
                
                # Process complete frames
                self._process_buffer()
                
        except Exception as e:
            logger.error(f"Error handling client {self.client_address}: {e}", exc_info=True)
        finally:
            self._cleanup()
    
    def _process_buffer(self) -> None:
        """Process data in receive buffer, extracting and handling complete frames"""
        while len(self.receive_buffer) > 0:
            # According to PROTOCOL_LOG_ANALYSIS.md, actual format is:
            # [ZProtocol帧] where DATA contains [IMEI_LEN][IMEI][ICCID_LEN][ICCID][PAYLOAD_LEN][PAYLOAD]
            try:
                # Find ZProtocol frame start
                frame_start_idx = self.zprotocol_decoder.find_frame_start(
                    bytes(self.receive_buffer)
                )
                
                if frame_start_idx is None:
                    # No complete ZProtocol frame found, wait for more data
                    if len(self.receive_buffer) < 7:
                        break
                    # Try to skip some bytes to find frame start
                    self.receive_buffer = self.receive_buffer[1:]
                    continue
                
                # Skip any bytes before frame start
                if frame_start_idx > 0:
                    logger.warning(
                        f"Skipping {frame_start_idx} bytes before ZProtocol frame from {self.client_address}"
                    )
                    self.receive_buffer = self.receive_buffer[frame_start_idx:]
                    continue
                
                # Decode ZProtocol frame
                try:
                    zprotocol_message = self.zprotocol_decoder.decode(
                        bytes(self.receive_buffer)
                    )
                except ValueError as e:
                    logger.debug(f"ZProtocol decode failed from {self.client_address}: {e}")
                    self.receive_buffer = self.receive_buffer[1:]
                    continue
                
                # Calculate frame length
                if len(self.receive_buffer) < 5:
                    break
                data_len = self.receive_buffer[4]  # LEN field
                frame_length = 2 + 1 + 1 + 1 + data_len + 1 + 1
                
                # Remove consumed bytes from buffer
                self.receive_buffer = self.receive_buffer[frame_length:]
                
                # Now parse TCP frame prefix from ZProtocol DATA
                frame_prefix = self._parse_tcp_frame_prefix_from_data(
                    zprotocol_message.data
                )
                
                if frame_prefix is None:
                    logger.warning(
                        f"Failed to parse TCP frame prefix from ZProtocol DATA from {self.client_address}, "
                        f"Command=0x{zprotocol_message.command:02X}, "
                        f"DATA_LEN={len(zprotocol_message.data)}"
                    )
                    continue
                
                # Process the frame
                self._process_frame_with_zprotocol(zprotocol_message, frame_prefix)
                
            except Exception as e:
                logger.error(
                    f"Error processing buffer from {self.client_address}: {e}",
                    exc_info=True
                )
                if len(self.receive_buffer) > 0:
                    self.receive_buffer = self.receive_buffer[1:]
                else:
                    break
    
    def _parse_tcp_frame_prefix_from_data(self, data: bytes) -> Optional[TCPFramePrefix]:
        """
        Parse TCP frame prefix from ZProtocol DATA: [IMEI_LEN][IMEI][ICCID_LEN][ICCID][PAYLOAD_LEN][PAYLOAD]
        """
        if len(data) < 5:
            return None
        
        try:
            offset = 0
            
            # IMEI
            imei_len = data[offset]
            offset += 1
            if len(data) < offset + imei_len:
                return None
            imei = data[offset:offset+imei_len].decode('ascii')
            offset += imei_len
            
            # ICCID
            if len(data) < offset + 1:
                return None
            iccid_len = data[offset]
            offset += 1
            if len(data) < offset + iccid_len:
                return None
            iccid = data[offset:offset+iccid_len].decode('ascii')
            offset += iccid_len
            
            # PAYLOAD_LEN
            if len(data) < offset + 2:
                return None
            payload_len_bytes = data[offset:offset+2]
            payload_len_be = struct.unpack('>H', payload_len_bytes)[0]
            payload_len_le = struct.unpack('<H', payload_len_bytes)[0]
            
            if payload_len_be < 300:
                payload_len = payload_len_be
            else:
                payload_len = payload_len_le
            offset += 2
            
            if len(data) < offset + payload_len:
                return None
            
            payload = data[offset:offset+payload_len]
            
            return TCPFramePrefix(
                imei=imei,
                iccid=iccid,
                payload=payload,
                total_length=len(data)
            )
        except Exception as e:
            logger.debug(f"Error parsing TCP frame prefix from ZProtocol DATA: {e}")
            return None
    
    def _process_frame_with_zprotocol(
        self,
        zprotocol_message: ZProtocolMessage,
        frame_prefix: TCPFramePrefix
    ) -> None:
        """
        Process a complete frame (ZProtocol + TCP frame prefix)
        """
        try:
            logger.info(
                f"Processing frame from {self.client_address}: "
                f"Command=0x{zprotocol_message.command:02X}, "
                f"IMEI={frame_prefix.imei}, ICCID={frame_prefix.iccid}"
            )
            
            # Create a new ZProtocol message with the actual payload
            actual_zprotocol_message = ZProtocolMessage(
                role=zprotocol_message.role,
                id=zprotocol_message.id,
                command=zprotocol_message.command,
                data=frame_prefix.payload,
                broadcast=zprotocol_message.broadcast
            )
            
            # Parse message based on command
            parsed_message = self.message_parser.parse(actual_zprotocol_message)
            
            if parsed_message.get('error'):
                logger.warning(
                    f"Message parse error from {self.client_address}: {parsed_message['error']}. "
                    f"Command=0x{zprotocol_message.command:02X}, IMEI={frame_prefix.imei}"
                )
            
            # Handle different command types
            command = zprotocol_message.command
            
            if command == 0x31:
                self._handle_sensor_data(actual_zprotocol_message, frame_prefix)
            elif command == 0x33:
                self._handle_image_chunk(actual_zprotocol_message, frame_prefix)
            elif command == 0x35:
                self._handle_alarm_data(parsed_message, frame_prefix)
            elif command == 0x36:
                self._handle_gps_data(parsed_message, frame_prefix)
            elif command == 0x38:
                self._handle_query_command(parsed_message, frame_prefix)
            else:
                logger.info(
                    f"Unknown command 0x{command:02X} from {self.client_address}, "
                    f"IMEI={frame_prefix.imei}"
                )
                
        except Exception as e:
            logger.error(
                f"Error processing frame from {self.client_address}: {e}",
                exc_info=True
            )
    
    def _handle_sensor_data(
        self,
        zprotocol_message: ZProtocolMessage,
        frame_prefix: TCPFramePrefix
    ) -> None:
        """Handle sensor data and trigger AI"""
        try:
            record_id = self.data_model.insert_sensor_data_from_payload(
                payload=zprotocol_message.data,
                imei=frame_prefix.imei,
                iccid=frame_prefix.iccid
            )
            
            if record_id:
                self.last_sensor_record_id = record_id
                logger.info(f"Inserted sensor data: record_id={record_id}, IMEI={frame_prefix.imei}")
                
                # Trigger AI worker
                self._trigger_ai_for_record(record_id)
            else:
                logger.warning(f"Failed to insert sensor data: IMEI={frame_prefix.imei}")
        except Exception as e:
            logger.error(f"Error handling sensor data: {e}", exc_info=True)

    def _handle_image_chunk(
        self,
        zprotocol_message: ZProtocolMessage,
        frame_prefix: TCPFramePrefix
    ) -> None:
        """Handle image chunk and trigger AI if complete"""
        try:
            chunk = self.image_handler.parse_chunk(zprotocol_message.data)
            if chunk is None:
                return
            
            image_path = self.image_handler.process_chunk(
                chunk=chunk,
                imei=frame_prefix.imei,
                iccid=frame_prefix.iccid
            )
            
            if image_path:
                record_id = self.last_sensor_record_id
                if record_id:
                    success = self.data_model.update_image_path(record_id, image_path)
                    if success:
                        logger.info(f"Image path updated: record_id={record_id}, path={image_path}")
                        self._trigger_ai_for_record(record_id, image_path)
                    else:
                        # Fallback to new record if update fails
                        self.data_model.insert_image_record(frame_prefix.imei, image_path, frame_prefix.iccid)
                else:
                    self.data_model.insert_image_record(frame_prefix.imei, image_path, frame_prefix.iccid)
        except Exception as e:
            logger.error(f"Error handling image chunk: {e}", exc_info=True)

    def _trigger_ai_for_record(self, record_id: int, image_path: Optional[str] = None) -> None:
        """Helper to trigger AI worker for a record"""
        try:
            db_manager = get_connection_manager()
            with db_manager.get_cursor() as cursor:
                cursor.execute("SELECT * FROM data_upload WHERE id = %s", (record_id,))
                record = cursor.fetchone()
                if record:
                    exclude_keys = {'id', 'picture_path', 'AI-1', 'AI-2', 'final_risk_level', 'received_at'}
                    data = {k: (v.isoformat() if hasattr(v, 'isoformat') else v) 
                            for k, v in record.items() if k not in exclude_keys}
                    trigger_ai_worker(record_id, data, image_path)
        except Exception as e:
            logger.error(f"Failed to trigger AI worker for record {record_id}: {e}")

    def _handle_alarm_data(self, parsed_message: dict, frame_prefix: TCPFramePrefix) -> None:
        try:
            self.data_model.insert_alarm_data(parsed_message, frame_prefix.imei, frame_prefix.iccid)
        except Exception as e:
            logger.error(f"Error handling alarm data: {e}")

    def _handle_gps_data(self, parsed_message: dict, frame_prefix: TCPFramePrefix) -> None:
        logger.info(f"Received GPS data: IMEI={frame_prefix.imei}")

    def _handle_query_command(self, parsed_message: dict, frame_prefix: TCPFramePrefix) -> None:
        logger.info(f"Received query command: IMEI={frame_prefix.imei}")

    def _cleanup(self) -> None:
        """Clean up client connection"""
        try:
            if self.client_socket:
                self.client_socket.close()
        except Exception:
            pass
