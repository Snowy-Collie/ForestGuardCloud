"""
Simple TLV Protocol Implementation

This module implements the Simple TLV protocol for encoding and decoding
device messages. Compatible with the C implementation in c/z_protocol/simple_tlv.c

Protocol Structure (Little Endian):
    tag (1 byte)
    len (2 bytes, uint16)
    addr (2 bytes, uint16)
    encrypt_mode (1 byte)
    effective_data_len (2 bytes, uint16)
    cmd (2 bytes, uint16)
    crc (4 bytes, uint32)
    data[] (variable length)
"""

import struct
import base64
import zlib
from typing import Optional, Tuple, List
from dataclasses import dataclass


# CRC32 table (IEEE 802.3 polynomial: 0xEDB88320)
CRC32_TABLE = [
    0x00000000, 0x77073096, 0xee0e612c, 0x990951ba, 0x076dc419, 0x706af48f,
    0xe963a535, 0x9e6495a3, 0x0edb8832, 0x79dcb8a4, 0xe0d5e91e, 0x97d2d988,
    0x09b64c2b, 0x7eb17cbd, 0xe7b82d07, 0x90bf1d91, 0x1db71064, 0x6ab020f2,
    0xf3b97148, 0x84be41de, 0x1adad47d, 0x6ddde4eb, 0xf4d4b551, 0x83d385c7,
    0x136c9856, 0x646ba8c0, 0xfd62f97a, 0x8a65c9ec, 0x14015c4f, 0x63066cd9,
    0xfa0f3d63, 0x8d080df5, 0x3b6e20c8, 0x4c69105e, 0xd56041e4, 0xa2677172,
    0x3c03e4d1, 0x4b04d447, 0xd20d85fd, 0xa50ab56b, 0x35b5a8fa, 0x42b2986c,
    0xdbbbc9d6, 0xacbcf940, 0x32d86ce3, 0x45df5c75, 0xdcd60dcf, 0xabd13d59,
    0x26d930ac, 0x51de003a, 0xc8d75180, 0xbfd06116, 0x21b4f4b5, 0x56b3c423,
    0xcfba9599, 0xb8bda50f, 0x2802b89e, 0x5f058808, 0xc60cd9b2, 0xb10be924,
    0x2f6f7c87, 0x58684c11, 0xc1611dab, 0xb6662d3d, 0x76dc4190, 0x01db7106,
    0x98d220bc, 0xefd5102a, 0x71b18589, 0x06b6b51f, 0x9fbfe4a5, 0xe8b8d433,
    0x7807c9a2, 0x0f00f934, 0x9609a88e, 0xe10e9818, 0x7f6a0dbb, 0x086d3d2d,
    0x91646c97, 0xe6635c01, 0x6b6b51f4, 0x1c6c6162, 0x856530d8, 0xf262004e,
    0x6c0695ed, 0x1b01a57b, 0x8208f4c1, 0xf50fc457, 0x65b0d9c6, 0x12b7e950,
    0x8bbeb8ea, 0xfcb9887c, 0x62dd1ddf, 0x15da2d49, 0x8cd37cf3, 0xfbd44c65,
    0x4db26158, 0x3ab551ce, 0xa3bc0074, 0xd4bb30e2, 0x4adfa541, 0x3dd895d7,
    0xa4d1c46d, 0xd3d6f4fb, 0x4369e96a, 0x346ed9fc, 0xad678846, 0xda60b8d0,
    0x44042d73, 0x33031de5, 0xaa0a4c5f, 0xdd0d7cc9, 0x5005713c, 0x270241aa,
    0xbe0b1010, 0xc90c2086, 0x5768b525, 0x206f85b3, 0xb966d409, 0xce61e49f,
    0x5edef90e, 0x29d9c998, 0xb0d09822, 0xc7d7a8b4, 0x59b33d17, 0x2eb40d81,
    0xb7bd5c3b, 0xc0ba6cad, 0xedb88320, 0x9abfb3b6, 0x03b6e20c, 0x74b1d29a,
    0xead54739, 0x9dd277af, 0x04db2615, 0x73dc1683, 0xe3630b12, 0x94643b84,
    0x0d6d6a3e, 0x7a6a5aa8, 0xe40ecf0b, 0x9309ff9d, 0x0a00ae27, 0x7d079eb1,
    0xf00f9344, 0x8708a3d2, 0x1e01f268, 0x6906c2fe, 0xf762575d, 0x806567cb,
    0x196c3671, 0x6e6b06e7, 0xfed41b76, 0x89d32be0, 0x10da7a5a, 0x67dd4acc,
    0xf9b9df6f, 0x8ebeeff9, 0x17b7be43, 0x60b08ed5, 0xd6d6a3e8, 0xa1d1937e,
    0x38d8c2c4, 0x4fdff252, 0xd1bb67f1, 0xa6bc5767, 0x3fb506dd, 0x48b2364b,
    0xd80d2bda, 0xaf0a1b4c, 0x36034af6, 0x41047a60, 0xdf60efc3, 0xa867df55,
    0x316e8eef, 0x4669be79, 0xcb61b38c, 0xbc66831a, 0x256fd2a0, 0x5268e236,
    0xcc0c7795, 0xbb0b4703, 0x220216b9, 0x5505262f, 0xc5ba3bbe, 0xb2bd0b28,
    0x2bb45a92, 0x5cb36a04, 0xc2d7ffa7, 0xb5d0cf31, 0x2cd99e8b, 0x5bdeae1d,
    0x9b64c2b0, 0xec63f226, 0x756aa39c, 0x026d930a, 0x9c0906a9, 0xeb0e363f,
    0x72076785, 0x05005713, 0x95bf4a82, 0xe2b87a14, 0x7bb12bae, 0x0cb61b38,
    0x92d28e9b, 0xe5d5be0d, 0x7cdcefb7, 0x0bdbdf21, 0x86d3d2d4, 0xf1d4e242,
    0x68ddb3f8, 0x1fda836e, 0x81be16cd, 0xf6b9265b, 0x6fb077e1, 0x18b74777,
    0x88085ae6, 0xff0f6a70, 0x66063bca, 0x11010b5c, 0x8f659eff, 0xf862ae69,
    0x616bffd3, 0x166ccf45, 0xa00ae278, 0xd70dd2ee, 0x4e048354, 0x3903b3c2,
    0xa7672661, 0xd06016f7, 0x4969474d, 0x3e6e77db, 0xaed16a4a, 0xd9d65adc,
    0x40df0b66, 0x37d83bf0, 0xa9bcae53, 0xdebb9ec5, 0x47b2cf7f, 0x30b5ffe9,
    0xbdbdf21c, 0xcabac28a, 0x53b39330, 0x24b4a3a6, 0xbad03605, 0xcdd70693,
    0x54de5729, 0x23d967bf, 0xb3667a2e, 0xc4614ab8, 0x5d681b02, 0x2a6f2b94,
    0xb40bbe37, 0xc30c8ea1, 0x5a05df1b, 0x2d02ef8d
]


def crc32_calculate(partial_crc: int, buffer: bytes, length: int) -> int:
    """
    Calculate CRC32 checksum (compatible with C implementation)
    
    Args:
        partial_crc: Initial CRC value (usually 0)
        buffer: Data buffer
        length: Length of data
    
    Returns:
        CRC32 checksum
    """
    crc = partial_crc ^ 0xFFFFFFFF
    
    for i in range(length):
        crc = CRC32_TABLE[(crc ^ buffer[i]) & 0xFF] ^ (crc >> 8)
    
    return crc ^ 0xFFFFFFFF


@dataclass
class TLVMessage:
    """Simple TLV message structure"""
    tag: int = 0x41  # Default tag
    addr: int = 1    # Default address
    encrypt_mode: int = 0  # 0=no encryption, 1=DES, 2=AES
    cmd: int = 0
    data: bytes = b''
    
    @property
    def effective_data_len(self) -> int:
        """Get effective data length"""
        return len(self.data)
    
    @property
    def len(self) -> int:
        """Get total TLV length (excluding tag and len fields)"""
        # Header size: addr(2) + encrypt_mode(1) + effective_data_len(2) + cmd(2) + crc(4) = 11
        # Plus data length
        return 11 + len(self.data)


class TLVEncoder:
    """Simple TLV Protocol Encoder"""
    
    def __init__(self, des_key: Optional[bytes] = None, aes_key: Optional[bytes] = None):
        """
        Initialize encoder
        
        Args:
            des_key: Optional 16-byte DES key for encryption
            aes_key: Optional 16-byte AES key for encryption
        """
        self.des_key = des_key
        self.aes_key = aes_key
    
    def encode(self, message: TLVMessage) -> str:
        """
        Encode TLV message to Base64 string
        
        Args:
            message: TLV message to encode
        
        Returns:
            Base64 encoded string
        
        Raises:
            ValueError: If message is invalid
        """
        if message.cmd == 0:
            raise ValueError("Invalid command: cmd cannot be 0")
        
        if message.effective_data_len > 0xFFFF - 14:
            raise ValueError(f"Data too large: {message.effective_data_len}")
        
        # Build TLV structure
        # Structure: tag(1) + len(2) + addr(2) + encrypt_mode(1) + effective_data_len(2) + cmd(2) + crc(4) + data[]
        # tlv_struct_size = 14 bytes (excluding data)
        tlv_struct_size = 14
        
        # Calculate data length (for now, no encryption)
        data_len = message.effective_data_len
        
        # Calculate len field: tlv_struct_size + data_len - TLV_HEADER_SIZE
        # TLV_HEADER_SIZE = tag(1) + len(2) = 3
        tlv_len = tlv_struct_size + data_len - 3
        
        # Build TLV structure
        tlv_struct = bytearray()
        
        # tag (1 byte)
        tlv_struct.append(message.tag)
        
        # len (2 bytes, little endian)
        tlv_struct.extend(struct.pack('<H', tlv_len))
        
        # addr (2 bytes, little endian)
        tlv_struct.extend(struct.pack('<H', message.addr))
        
        # encrypt_mode (1 byte)
        tlv_struct.extend(bytes([message.encrypt_mode]))
        
        # effective_data_len (2 bytes, little endian)
        tlv_struct.extend(struct.pack('<H', message.effective_data_len))
        
        # cmd (2 bytes, little endian)
        tlv_struct.extend(struct.pack('<H', message.cmd))
        
        # crc (4 bytes, little endian) - will be calculated later
        tlv_struct.extend(struct.pack('<I', 0))
        
        # data
        tlv_struct.extend(message.data)
        
        # Calculate CRC32 (over entire structure with CRC=0)
        # Note: CRC is calculated over the entire structure including the CRC field (set to 0)
        crc = crc32_calculate(0, bytes(tlv_struct), len(tlv_struct))
        
        # Update CRC field
        # Offset calculation: tag(1) + len(2) + addr(2) + encrypt_mode(1) + effective_data_len(2) + cmd(2) = 10
        crc_offset = 10
        struct.pack_into('<I', tlv_struct, crc_offset, crc)
        
        # TODO: Implement encryption if encrypt_mode is set
        # Encryption support can be added using pycryptodome:
        # - DES/3DES: if encrypt_mode & 0x01
        # - AES-128: if encrypt_mode & 0x02
        # For now, we skip encryption as most devices use encrypt_mode=0
        
        # Base64 encode
        encoded = base64.b64encode(bytes(tlv_struct)).decode('ascii')
        
        return encoded


class TLVDecoder:
    """Simple TLV Protocol Decoder"""
    
    def __init__(self, des_key: Optional[bytes] = None, aes_key: Optional[bytes] = None):
        """
        Initialize decoder
        
        Args:
            des_key: Optional 16-byte DES key for decryption
            aes_key: Optional 16-byte AES key for decryption
        """
        self.des_key = des_key
        self.aes_key = aes_key
    
    def decode(self, encoded: str) -> TLVMessage:
        """
        Decode Base64 string to TLV message
        
        Args:
            encoded: Base64 encoded string
        
        Returns:
            Decoded TLV message
        
        Raises:
            ValueError: If decoding fails or CRC mismatch
        """
        # Base64 decode
        try:
            tlv_struct = base64.b64decode(encoded)
        except Exception as e:
            raise ValueError(f"Base64 decode failed: {e}")
        
        if len(tlv_struct) < 14:  # Minimum size: tag(1) + len(2) + addr(2) + encrypt(1) + eff_len(2) + cmd(2) + crc(4) = 14
            raise ValueError(f"TLV data too short: {len(tlv_struct)} bytes")
        
        # Parse TLV structure
        offset = 0
        
        # tag (1 byte)
        tag = tlv_struct[offset]
        offset += 1
        
        # len (2 bytes, little endian)
        tlv_len = struct.unpack('<H', tlv_struct[offset:offset+2])[0]
        offset += 2
        
        # Verify length
        expected_size = tlv_len + 3  # len field + tag + len fields
        if len(tlv_struct) < expected_size:
            raise ValueError(f"TLV length mismatch: expected {expected_size}, got {len(tlv_struct)}")
        
        # addr (2 bytes, little endian)
        addr = struct.unpack('<H', tlv_struct[offset:offset+2])[0]
        offset += 2
        
        # encrypt_mode (1 byte)
        encrypt_mode = tlv_struct[offset]
        offset += 1
        
        # effective_data_len (2 bytes, little endian)
        effective_data_len = struct.unpack('<H', tlv_struct[offset:offset+2])[0]
        offset += 2
        
        # cmd (2 bytes, little endian)
        cmd = struct.unpack('<H', tlv_struct[offset:offset+2])[0]
        offset += 2
        
        # crc (4 bytes, little endian)
        crc = struct.unpack('<I', tlv_struct[offset:offset+4])[0]
        offset += 4
        
        # data
        data = tlv_struct[offset:offset+effective_data_len]
        
        # Verify CRC32
        # Calculate CRC over structure with CRC field set to 0
        tlv_without_crc = bytearray(tlv_struct)
        struct.pack_into('<I', tlv_without_crc, 10, 0)  # Set CRC to 0 (offset 10)
        
        calculated_crc = crc32_calculate(0, bytes(tlv_without_crc), len(tlv_without_crc))
        
        if crc != calculated_crc:
            raise ValueError(f"CRC mismatch: expected 0x{crc:08X}, calculated 0x{calculated_crc:08X}")
        
        # TODO: Implement decryption if encrypt_mode is set
        # Decryption support can be added using pycryptodome:
        # - DES/3DES: if encrypt_mode & 0x01
        # - AES-128: if encrypt_mode & 0x02
        # For now, we skip decryption as most devices use encrypt_mode=0
        
        return TLVMessage(
            tag=tag,
            addr=addr,
            encrypt_mode=encrypt_mode,
            cmd=cmd,
            data=bytes(data)
        )


# Convenience functions
def encode_tlv(cmd: int, data: bytes, addr: int = 1, tag: int = 0x41, 
               encrypt_mode: int = 0) -> str:
    """
    Encode TLV message (convenience function)
    
    Args:
        cmd: Command code
        data: Data payload
        addr: Address (default: 1)
        tag: Tag (default: 0x41)
        encrypt_mode: Encryption mode (default: 0 = no encryption)
    
    Returns:
        Base64 encoded string
    """
    message = TLVMessage(cmd=cmd, data=data, addr=addr, tag=tag, encrypt_mode=encrypt_mode)
    encoder = TLVEncoder()
    return encoder.encode(message)


def decode_tlv(encoded: str) -> TLVMessage:
    """
    Decode TLV message (convenience function)
    
    Args:
        encoded: Base64 encoded string
    
    Returns:
        Decoded TLV message
    """
    decoder = TLVDecoder()
    return decoder.decode(encoded)

