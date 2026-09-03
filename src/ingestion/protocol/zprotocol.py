"""
ZProtocol Implementation

This module implements the ZProtocol for encoding and decoding device messages.
Compatible with the C implementation in c/z_protocol/zprotocol.c

Protocol Structure:
    SOH_H (1 byte) - Start of Header High
    SOH_L (1 byte) - Start of Header Low
    ID (1 byte) - Message ID
    CMD (1 byte) - Command
    LEN (1 byte) - Data length (0-255)
    DATA[] (variable length, 0-255 bytes)
    LRC (1 byte) - Longitudinal Redundancy Check (XOR of all previous bytes)
    EOT (1 byte) - End of Transmission

For Master role (role=0):
    SOH_H = 0x98, SOH_L = 0xA0, EOT = 0xA1

For Slave role (role=1):
    SOH_H = 0x99, SOH_L = 0xA2, EOT = 0xA3

For Duplex role (role=2):
    Uses Master SOH/EOT for both send and receive
"""

from typing import Optional, Tuple
from dataclasses import dataclass


# Protocol constants
SOH_H = 0x98
SOH_L = 0xA0
EOT = 0xA1
SOH_HR = 0x99  # Slave reply SOH_H
SOH_LR = 0xA2  # Slave reply SOH_L
EOTR = 0xA3    # Slave reply EOT

# Role constants
ROLE_MASTER = 0
ROLE_SLAVE = 1
ROLE_DUPLEX = 2


@dataclass
class ZProtocolMessage:
    """ZProtocol message structure"""
    role: int = ROLE_MASTER  # 0=Master, 1=Slave, 2=Duplex
    id: int = 0
    command: int = 0
    data: bytes = b''
    broadcast: int = 0
    
    @property
    def source_length(self) -> int:
        """Get source data length"""
        return len(self.data)
    
    @property
    def destination_length(self) -> int:
        """Get destination buffer length (data + 7 protocol overhead)"""
        return len(self.data) + 7


class ZProtocolEncoder:
    """ZProtocol Encoder"""
    
    def __init__(self, role: int = ROLE_MASTER):
        """
        Initialize encoder
        
        Args:
            role: Role (0=Master, 1=Slave, 2=Duplex)
        """
        self.role = role
    
    def _get_soh_eot(self, is_reply: bool = False) -> Tuple[int, int, int]:
        """
        Get SOH and EOT bytes based on role
        
        Args:
            is_reply: True if this is a reply message (for Slave role)
        
        Returns:
            Tuple of (soh_h, soh_l, eot)
        """
        if self.role == ROLE_SLAVE and is_reply:
            return (SOH_HR, SOH_LR, EOTR)
        else:
            # Master or Duplex use Master SOH/EOT
            return (SOH_H, SOH_L, EOT)
    
    def encode(self, message: ZProtocolMessage) -> bytes:
        """
        Encode ZProtocol message to binary
        
        Args:
            message: ZProtocol message to encode
        
        Returns:
            Encoded binary data
        
        Raises:
            ValueError: If message is invalid
        """
        # Check data length limit (max 255 bytes)
        if message.source_length > 255:
            raise ValueError(f"Data too large: {message.source_length} bytes (max 255)")
        
        # Get SOH/EOT based on role
        is_reply = (message.role == ROLE_SLAVE)
        soh_h, soh_l, eot = self._get_soh_eot(is_reply)
        
        # Build protocol frame
        # Structure: SOH_H, SOH_L, ID, CMD, LEN, DATA, LRC, EOT
        frame = bytearray()
        
        # SOH_H, SOH_L
        frame.append(soh_h)
        frame.append(soh_l)
        
        # ID, CMD
        frame.append(message.id & 0xFF)
        frame.append(message.command & 0xFF)
        
        # LEN
        data_len = message.source_length & 0xFF
        frame.append(data_len)
        
        # DATA
        if data_len > 0:
            frame.extend(message.data)
        
        # Calculate LRC (XOR of all bytes so far: SOH_H, SOH_L, ID, CMD, LEN, DATA)
        lrc = 0
        for i in range(len(frame)):
            lrc ^= frame[i]
        
        # LRC
        frame.append(lrc)
        
        # EOT
        frame.append(eot)
        
        return bytes(frame)


class ZProtocolDecoder:
    """ZProtocol Decoder"""
    
    def __init__(self, role: int = ROLE_MASTER):
        """
        Initialize decoder
        
        Args:
            role: Role (0=Master, 1=Slave, 2=Duplex)
        """
        self.role = role
    
    def _get_soh_eot(self, is_reply: bool = False) -> Tuple[int, int, int]:
        """
        Get SOH and EOT bytes based on role
        
        Args:
            is_reply: True if this is a reply message (for Master reading Slave reply)
        
        Returns:
            Tuple of (soh_h, soh_l, eot)
        """
        if self.role == ROLE_MASTER and is_reply:
            # Master reading Slave reply
            return (SOH_HR, SOH_LR, EOTR)
        else:
            # Slave or Duplex use Master SOH/EOT
            return (SOH_H, SOH_L, EOT)
    
    def decode(self, data: bytes, is_reply: bool = False) -> ZProtocolMessage:
        """
        Decode binary data to ZProtocol message
        
        Args:
            data: Binary data to decode
            is_reply: True if this is a reply message
        
        Returns:
            Decoded ZProtocol message
        
        Raises:
            ValueError: If decoding fails or LRC mismatch
        """
        if len(data) < 7:
            raise ValueError(f"Data too short: {len(data)} bytes (minimum 7)")
        
        # Get SOH/EOT based on role
        soh_h, soh_l, eot = self._get_soh_eot(is_reply)
        
        # Find frame start (SOH_H, SOH_L)
        start_idx = None
        for i in range(len(data) - 6):
            if data[i] == soh_h and data[i + 1] == soh_l:
                # Check if we have enough data for complete frame
                if i + 4 < len(data):
                    data_len = data[i + 4]
                    if i + data_len + 7 <= len(data):
                        # Check EOT
                        if data[i + data_len + 6] == eot:
                            start_idx = i
                            break
        
        if start_idx is None:
            raise ValueError("Frame not found: SOH_H/SOH_L/EOT mismatch")
        
        # Extract frame
        frame_start = data[start_idx:]
        data_len = frame_start[4]
        
        # Verify frame length
        if len(frame_start) < data_len + 7:
            raise ValueError(f"Frame incomplete: expected {data_len + 7} bytes, got {len(frame_start)}")
        
        # Verify LRC
        # LRC should be XOR of: SOH_H, SOH_L, ID, CMD, LEN, DATA
        lrc = 0
        for i in range(data_len + 5):  # SOH_H, SOH_L, ID, CMD, LEN, DATA
            lrc ^= frame_start[i]
        
        received_lrc = frame_start[data_len + 5]
        if lrc != received_lrc:
            raise ValueError(f"LRC mismatch: expected 0x{lrc:02X}, got 0x{received_lrc:02X}")
        
        # Extract fields
        msg_id = frame_start[2]
        cmd = frame_start[3]
        msg_data = frame_start[5:5 + data_len] if data_len > 0 else b''
        
        return ZProtocolMessage(
            role=self.role,
            id=msg_id,
            command=cmd,
            data=bytes(msg_data)
        )
    
    def find_frame_start(self, data: bytes, is_reply: bool = False) -> Optional[int]:
        """
        Find the start index of a valid frame in the data buffer
        
        Args:
            data: Binary data buffer
            is_reply: True if looking for reply frame
        
        Returns:
            Start index of frame, or None if not found
        """
        soh_h, soh_l, eot = self._get_soh_eot(is_reply)
        
        for i in range(len(data) - 6):
            if data[i] == soh_h and data[i + 1] == soh_l:
                if i + 4 < len(data):
                    data_len = data[i + 4]
                    if i + data_len + 7 <= len(data):
                        if data[i + data_len + 6] == eot:
                            return i
        
        return None


# Convenience functions
def encode_zprotocol(role: int, msg_id: int, command: int, data: bytes = b'') -> bytes:
    """
    Encode ZProtocol message (convenience function)
    
    Args:
        role: Role (0=Master, 1=Slave, 2=Duplex)
        msg_id: Message ID
        command: Command code
        data: Data payload (max 255 bytes)
    
    Returns:
        Encoded binary data
    """
    message = ZProtocolMessage(role=role, id=msg_id, command=command, data=data)
    encoder = ZProtocolEncoder(role=role)
    return encoder.encode(message)


def decode_zprotocol(data: bytes, role: int = ROLE_MASTER, is_reply: bool = False) -> ZProtocolMessage:
    """
    Decode ZProtocol message (convenience function)
    
    Args:
        data: Binary data to decode
        role: Role (0=Master, 1=Slave, 2=Duplex)
        is_reply: True if this is a reply message
    
    Returns:
        Decoded ZProtocol message
    """
    decoder = ZProtocolDecoder(role=role)
    return decoder.decode(data, is_reply=is_reply)
