"""Multimedia processing module for multimodal AI interactions.

This module handles image processing for multimodal AI interactions,
including validation, compression, and base64 encoding of images.
"""

import asyncio
import base64
import io
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from .const import SUPPORTED_IMAGE_TYPES, SUPPORTED_IMAGE_EXTENSIONS


@dataclass
class ImageAttachment:
    """Represents an image attachment in a message."""

    image_id: str  # Unique ID
    data: str  # Base64 encoded image data
    mime_type: str  # e.g., "image/jpeg"
    original_size: int  # Original file size in bytes
    compressed_size: int  # Compressed size in bytes
    width: int  # Image width in pixels
    height: int  # Image height in pixels
    compression_ratio: float  # Compression ratio (0-1)


class MultimediaProcessor:
    """Handles image processing for multimodal AI interactions."""

    def __init__(
        self,
        max_image_size: int = 5 * 1024 * 1024,
        max_images_per_message: int = 3,
        compression_quality: int = 80,
        max_dimension: int = 2048,
    ):
        """Initialize the multimedia processor.

        Args:
            max_image_size: Maximum allowed image size in bytes (default 5MB)
            max_images_per_message: Maximum number of images per message (default 3)
            compression_quality: JPEG compression quality 1-100 (default 80)
            max_dimension: Maximum width/height in pixels (default 2048)
        """
        self.max_image_size = max_image_size
        self.max_images_per_message = max_images_per_message
        self.compression_quality = compression_quality
        self.max_dimension = max_dimension
        self.image_counter = 0

    async def validate_image(self, file_data: bytes, mime_type: str) -> Dict:
        """Validate an uploaded image.

        Args:
            file_data: Raw image bytes
            mime_type: MIME type of the image

        Returns:
            Dict with keys:
                - valid (bool): Whether the image is valid
                - error (str): Error message if invalid
                - width (int): Image width (if valid)
                - height (int): Image height (if valid)
        """
        # Check MIME type
        if mime_type not in SUPPORTED_IMAGE_TYPES:
            return {
                "valid": False,
                "error": f"Unsupported image type: {mime_type}. Supported: {SUPPORTED_IMAGE_TYPES}",
            }

        # Check file size
        if len(file_data) > self.max_image_size:
            max_mb = self.max_image_size / (1024 * 1024)
            return {
                "valid": False,
                "error": f"Image too large: {len(file_data) / (1024*1024):.1f}MB. Maximum: {max_mb:.0f}MB",
            }

        # Try to open image and get dimensions
        try:
            from PIL import Image
        except ImportError:
            return {
                "valid": False,
                "error": "Pillow library not installed. Please install it to use image processing features.",
            }

        try:
            image = Image.open(io.BytesIO(file_data))
            width, height = image.size

            # Check dimensions
            if width > self.max_dimension or height > self.max_dimension:
                return {
                    "valid": False,
                    "error": f"Image too large: {width}x{height}. Maximum dimension: {self.max_dimension}",
                }

            return {"valid": True, "width": width, "height": height}
        except Exception as e:
            return {"valid": False, "error": f"Invalid image file: {str(e)}"}

    async def compress_image(self, file_data: bytes) -> bytes:
        """Compress an image while maintaining quality.

        Args:
            file_data: Raw image bytes

        Returns:
            Compressed image bytes as JPEG
        """
        from PIL import Image

        def _compress():
            image = Image.open(io.BytesIO(file_data))

            # Convert to RGB if necessary (for JPEG compatibility)
            if image.mode in ("RGBA", "P", "LA"):
                # Create white background for transparent images
                background = Image.new("RGB", image.size, (255, 255, 255))
                if image.mode == "P":
                    image = image.convert("RGBA")
                background.paste(image, mask=image.split()[-1] if image.mode in ("RGBA", "LA") else None)
                image = background
            elif image.mode != "RGB":
                image = image.convert("RGB")

            # Resize if too large
            width, height = image.size
            if width > self.max_dimension or height > self.max_dimension:
                ratio = self.max_dimension / max(width, height)
                width = int(width * ratio)
                height = int(height * ratio)
                image = image.resize((width, height), Image.LANCZOS)

            # Compress
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=self.compression_quality, optimize=True)
            return output.getvalue()

        return await asyncio.get_event_loop().run_in_executor(None, _compress)

    async def encode_to_base64(self, file_data: bytes) -> str:
        """Encode image data to base64.

        Args:
            file_data: Raw image bytes

        Returns:
            Base64 encoded string
        """
        return base64.b64encode(file_data).decode("utf-8")

    async def process_image_upload(
        self, file_data: bytes, mime_type: str
    ) -> Dict:
        """Process an uploaded image: validate, compress, and encode.

        Args:
            file_data: Raw image bytes
            mime_type: MIME type of the image

        Returns:
            Dict with keys:
                - success (bool): Whether processing succeeded
                - image (ImageAttachment): The processed image attachment (if successful)
                - error (str): Error message if failed
        """
        # Validate
        validation = await self.validate_image(file_data, mime_type)
        if not validation["valid"]:
            return {"success": False, "error": validation["error"]}

        # Compress
        compressed_data = await self.compress_image(file_data)

        # Encode
        base64_data = await self.encode_to_base64(compressed_data)

        # Create attachment
        self.image_counter += 1
        attachment = ImageAttachment(
            image_id=f"img_{self.image_counter}_{int(time.time())}",
            data=base64_data,
            mime_type="image/jpeg",  # Always convert to JPEG
            original_size=len(file_data),
            compressed_size=len(compressed_data),
            width=validation["width"],
            height=validation["height"],
            compression_ratio=len(compressed_data) / len(file_data) if len(file_data) > 0 else 0,
        )

        return {"success": True, "image": attachment}

    @staticmethod
    def format_multimodal_message(text: str, images: List[ImageAttachment]) -> List[Dict]:
        """Format a message with images for multimodal AI models.

        Args:
            text: The text content of the message
            images: List of ImageAttachment objects

        Returns:
            Message content array compatible with OpenAI, Anthropic, etc.
        """
        content = [{"type": "text", "text": text}]

        for image in images:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{image.mime_type};base64,{image.data}",
                        "detail": "auto",  # AI will decide resolution
                    },
                }
            )

        return content

    @staticmethod
    def get_supported_models() -> List[str]:
        """Get list of AI models that support multimodal input.

        Returns:
            List of model IDs that support image input
        """
        return [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-2.0-flash",
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "claude-3-opus",
            "claude-3-sonnet",
            "claude-3-haiku",
            "claude-3.5-sonnet",
        ]

    def can_process_images(self) -> bool:
        """Check if image processing is enabled based on current settings.

        Returns:
            True if images can be processed, False otherwise
        """
        return (
            self.max_image_size > 0
            and self.max_images_per_message > 0
            and 1 <= self.compression_quality <= 100
        )

    def get_settings(self) -> Dict:
        """Get current processor settings.

        Returns:
            Dict containing current settings
        """
        return {
            "max_image_size": self.max_image_size,
            "max_images_per_message": self.max_images_per_message,
            "compression_quality": self.compression_quality,
            "max_dimension": self.max_dimension,
            "can_process": self.can_process_images(),
        }
