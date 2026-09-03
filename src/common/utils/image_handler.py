"""
Image Handler for Forest Guard AI Service

Handles image chunk reception, caching, assembly, and file saving.
Images are Base64 encoded and need to be decoded before saving.
"""

import struct
import os
import hashlib
import base64
from pathlib import Path
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

from src.common.utils.logger import get_logger
from src.common.config.settings import StorageConfig, get_ingestion_settings, root_dir

logger = get_logger(__name__)


@dataclass
class ImageChunk:
    """Image chunk data"""
    chunk_index: int
    image_data: bytes
    chunk_size: int  # Size of image_data (not including chunk_index)
    
    @property
    def is_last_chunk(self) -> bool:
        """Check if this is the last chunk (chunk_size < 128)"""
        return self.chunk_size < 128


@dataclass
class ImageAssembly:
    """Image assembly state for a device"""
    imei: str
    chunks: Dict[int, ImageChunk]  # chunk_index -> ImageChunk
    total_size: Optional[int] = None
    is_complete: bool = False
    created_at: datetime = None
    
    def __post_init__(self):
        """Initialize created_at if not provided"""
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def add_chunk(self, chunk: ImageChunk) -> bool:
        """
        Add a chunk to the assembly
        
        Args:
            chunk: Image chunk to add
            
        Returns:
            True if image is now complete, False otherwise
        """
        self.chunks[chunk.chunk_index] = chunk
        
        # Check if this is the last chunk
        if chunk.is_last_chunk:
            # Calculate total size from all chunks
            self.total_size = sum(c.chunk_size for c in self.chunks.values())
            self.is_complete = True
            logger.info(
                f"Image assembly complete for IMEI={self.imei}: "
                f"{len(self.chunks)} chunks, total_size={self.total_size} bytes"
            )
            return True
        
        return False
    
    def assemble_image(self) -> Optional[bytes]:
        """
        Assemble image from all chunks (in order)
        
        Returns:
            Complete image data, or None if incomplete
        """
        if not self.is_complete:
            return None
        
        # Sort chunks by index
        sorted_chunks = sorted(self.chunks.items())
        
        # Concatenate image data
        image_data = bytearray()
        for chunk_index, chunk in sorted_chunks:
            image_data.extend(chunk.image_data)
        
        return bytes(image_data)
    
    def get_missing_chunks(self) -> list[int]:
        """
        Get list of missing chunk indices (if any)
        
        Returns:
            List of missing chunk indices
        """
        if not self.chunks:
            return []
        
        max_index = max(self.chunks.keys())
        missing = []
        
        for i in range(1, max_index + 1):
            if i not in self.chunks:
                missing.append(i)
        
        return missing


class ImageHandler:
    """Handler for image chunk processing and file management"""
    
    # Maximum number of incomplete assemblies to keep in memory
    MAX_INCOMPLETE_ASSEMBLIES = 100
    
    # Timeout for incomplete assemblies (seconds)
    ASSEMBLY_TIMEOUT = 300  # 5 minutes
    
    def __init__(self, storage_config: Optional[StorageConfig] = None):
        """
        Initialize image handler
        
        Args:
            storage_config: Storage configuration. If None, loads from settings
        """
        if storage_config is None:
            settings = get_ingestion_settings()
            storage_config = settings.storage
        
        self.storage_config = storage_config
        self.image_path = Path(storage_config.image_path)
        
        # Create image directory if it doesn't exist
        self.image_path.mkdir(parents=True, exist_ok=True)
        
        # Cache for incomplete image assemblies
        # Key: (imei, timestamp_hash) -> ImageAssembly
        self.assemblies: Dict[Tuple[str, str], ImageAssembly] = {}
        
        logger.info(f"Image handler initialized: image_path={self.image_path}")
    
    def parse_chunk(self, payload: bytes) -> Optional[ImageChunk]:
        """
        Parse image chunk from 0x33 command payload
        
        Structure:
        - Bytes 0-3: chunk_index (4 bytes, Big-Endian uint32)
        - Bytes 4+: image_data (128 bytes for normal chunks, <128 for last chunk)
        
        Args:
            payload: ZProtocol data payload (chunk_index + image_data)
            
        Returns:
            ImageChunk object, or None if parsing fails
        """
        if len(payload) < 4:
            logger.error(f"Image chunk payload too short: {len(payload)} bytes (minimum 4)")
            return None
        
        try:
            # Parse chunk_index (4 bytes, big-endian, as per device spec)
            chunk_index = struct.unpack('>I', payload[0:4])[0]
            
            # Extract image data (remaining bytes, expected <= 128 bytes)
            image_data = payload[4:]
            chunk_size = len(image_data)
            
            if chunk_size > 128:
                logger.warning(
                    f"Image chunk size exceeds 128 bytes: "
                    f"chunk_index={chunk_index}, chunk_size={chunk_size}, total_payload={len(payload)}"
                )
            
            return ImageChunk(
                chunk_index=chunk_index,
                image_data=image_data,
                chunk_size=chunk_size
            )
            
        except Exception as e:
            logger.error(f"Error parsing image chunk: {e}", exc_info=True)
            return None
    
    def process_chunk(
        self,
        chunk: ImageChunk,
        imei: str,
        iccid: Optional[str] = None
    ) -> Optional[str]:
        """
        Process an image chunk and save complete image if ready
        
        Args:
            chunk: Image chunk to process
            imei: Device IMEI
            iccid: Device ICCID (optional)
            
        Returns:
            Path to saved image file if image is complete, None otherwise
        """
        # Use IMEI as key (assuming one image per device at a time)
        # In case of multiple concurrent images, we could use a hash
        # For now, we'll use a simple approach: one assembly per IMEI
        assembly_key = (imei, "default")
        
        # Get or create assembly
        if assembly_key not in self.assemblies:
            self.assemblies[assembly_key] = ImageAssembly(imei=imei, chunks={})
        
        assembly = self.assemblies[assembly_key]
        
        # Add chunk
        is_complete = assembly.add_chunk(chunk)
        
        if is_complete:
            # Assemble complete image (Base64 encoded)
            image_data_base64 = assembly.assemble_image()
            
            if image_data_base64 is None:
                logger.error(f"Failed to assemble image for IMEI={imei}")
                return None
            
            # Decode Base64 to binary image data
            try:
                # Try to decode as ASCII string first (Base64 is ASCII)
                if isinstance(image_data_base64, bytes):
                    # Check if it's already binary (JPEG magic bytes) or Base64 string
                    if image_data_base64[:2] == b'\xff\xd8':  # JPEG magic bytes
                        image_data = image_data_base64
                        logger.debug("Image data is already binary (JPEG)")
                    else:
                        # Decode Base64 string
                        image_data_base64_str = image_data_base64.decode('ascii', errors='ignore')
                        image_data = base64.b64decode(image_data_base64_str)
                        logger.info(
                            f"Decoded Base64 image data: {len(image_data_base64)} bytes -> {len(image_data)} bytes"
                        )
                else:
                    # Already a string, decode directly
                    image_data = base64.b64decode(image_data_base64)
                    logger.info(f"Decoded Base64 image string: {len(image_data)} bytes")
            except Exception as e:
                logger.error(f"Failed to decode Base64 image data: {e}", exc_info=True)
                return None
            
            # Save image file (both binary and base64 for debugging)
            image_path = self.save_image(image_data, imei, iccid, image_data_base64)
            
            # Clean up assembly
            del self.assemblies[assembly_key]
            
            if image_path:
                logger.info(
                    f"Image saved successfully: IMEI={imei}, "
                    f"path={image_path}, size={len(image_data)} bytes"
                )
            
            return image_path
        else:
            logger.debug(
                f"Image chunk received: IMEI={imei}, "
                f"chunk_index={chunk.chunk_index}, "
                f"chunk_size={chunk.chunk_size}, "
                f"total_chunks={len(assembly.chunks)}"
            )
            return None
    
    def save_image(
        self,
        image_data: bytes,
        imei: str,
        iccid: Optional[str] = None,
        base64_data: Optional[bytes] = None
    ) -> Optional[str]:
        """
        Save image data to file (both binary and base64 for debugging)
        
        Args:
            image_data: Complete image data (binary)
            imei: Device IMEI
            iccid: Device ICCID (optional)
            base64_data: Original Base64 encoded data (for debugging)
            
        Returns:
            Relative path to saved image file, or None if save fails
        """
        try:
            # Generate filename: IMEI_timestamp_sequence.jpg
            # Use timestamp to ensure uniqueness
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Add hash suffix to ensure uniqueness even with same timestamp
            hash_suffix = hashlib.md5(image_data[:100]).hexdigest()[:8]
            
            filename = f"{imei}_{timestamp}_{hash_suffix}.jpg"
            file_path = self.image_path / filename
            
            # Save binary image data
            with open(file_path, 'wb') as f:
                f.write(image_data)
            
            # Also save Base64 data for debugging if provided
            if base64_data is not None:
                base64_filename = f"{imei}_{timestamp}_{hash_suffix}.base64.txt"
                base64_file_path = self.image_path / base64_filename
                
                try:
                    # Save as text file (Base64 is ASCII)
                    if isinstance(base64_data, bytes):
                        base64_str = base64_data.decode('ascii', errors='ignore')
                    else:
                        base64_str = str(base64_data)
                    
                    with open(base64_file_path, 'w', encoding='utf-8') as f:
                        f.write(base64_str)
                    
                    logger.info(
                        f"Base64 data saved for debugging: IMEI={imei}, "
                        f"filename={base64_filename}, "
                        f"size={len(base64_str)} bytes"
                    )
                except Exception as e:
                    logger.warning(f"Failed to save Base64 debug file: {e}")
            
            # Return relative path from project root (for database storage)
            try:
                relative_path = str(file_path.relative_to(root_dir))
            except ValueError:
                relative_path = str(file_path)
            
            logger.info(
                f"Image saved: IMEI={imei}, "
                f"filename={filename}, "
                f"size={len(image_data)} bytes"
            )
            
            return relative_path
            
        except Exception as e:
            logger.error(f"Error saving image for IMEI={imei}: {e}", exc_info=True)
            return None
    
    def cleanup_old_assemblies(self) -> None:
        """Clean up old incomplete assemblies"""
        current_time = datetime.now()
        keys_to_remove = []
        
        for key, assembly in self.assemblies.items():
            age = (current_time - assembly.created_at).total_seconds()
            if age > self.ASSEMBLY_TIMEOUT:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            logger.warning(
                f"Removing stale image assembly: IMEI={self.assemblies[key].imei}, "
                f"age={age:.1f}s"
            )
            del self.assemblies[key]
        
        # Also limit total number of assemblies
        if len(self.assemblies) > self.MAX_INCOMPLETE_ASSEMBLIES:
            # Remove oldest assemblies
            sorted_assemblies = sorted(
                self.assemblies.items(),
                key=lambda x: x[1].created_at
            )
            excess_count = len(self.assemblies) - self.MAX_INCOMPLETE_ASSEMBLIES
            
            for i in range(excess_count):
                key = sorted_assemblies[i][0]
                logger.warning(
                    f"Removing excess image assembly: IMEI={self.assemblies[key].imei}"
                )
                del self.assemblies[key]
    
    def get_assembly_status(self, imei: str) -> Optional[Dict]:
        """
        Get status of image assembly for a device
        
        Args:
            imei: Device IMEI
            
        Returns:
            Dictionary with assembly status, or None if no assembly exists
        """
        assembly_key = (imei, "default")
        
        if assembly_key not in self.assemblies:
            return None
        
        assembly = self.assemblies[assembly_key]
        
        return {
            'imei': imei,
            'chunk_count': len(assembly.chunks),
            'total_size': assembly.total_size,
            'is_complete': assembly.is_complete,
            'missing_chunks': assembly.get_missing_chunks(),
            'created_at': assembly.created_at.isoformat()
        }


# Global image handler instance
_image_handler: Optional[ImageHandler] = None


def get_image_handler(storage_config: Optional[StorageConfig] = None) -> ImageHandler:
    """
    Get global image handler instance
    
    Args:
        storage_config: Storage configuration. If None, uses settings
        
    Returns:
        ImageHandler instance
    """
    global _image_handler
    
    if _image_handler is None:
        _image_handler = ImageHandler(storage_config)
    
    return _image_handler
