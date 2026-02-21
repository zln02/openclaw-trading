"""Nano Banana Pro (DeepSeed) parameter handler - Jobs API v1"""

from typing import Dict, Any, List, Optional


def build_nano_pro_payload(prompt: str, **kwargs) -> Dict[str, Any]:
    """
    Build payload for Nano Banana Pro model via Jobs API v1.

    Parameters:
        prompt: Image description (required)
        aspect_ratio: Aspect ratio (1:1, 3:2, 2:3, 4:3, 3:4, 16:9, 9:16, 21:9, 9:21) [default: 1:1]
        format: Output format (jpg, png, webp) [default: png]
        image_input: Reference image URLs (up to 4 images)

    Returns:
        API request payload for Jobs API v1
    """
    payload = {'prompt': prompt}

    # Aspect ratio
    aspect_ratio = kwargs.get('aspect_ratio') or kwargs.get('size') or kwargs.get('ratio')
    if aspect_ratio:
        valid_ratios = ['1:1', '3:2', '2:3', '4:3', '3:4', '16:9', '9:16', '21:9', '9:21']
        if aspect_ratio not in valid_ratios:
            raise ValueError(f"Invalid aspect_ratio. Must be one of: {', '.join(valid_ratios)}")
        payload['aspect_ratio'] = aspect_ratio

    # Output format (only if specified)
    fmt = kwargs.get('format') or kwargs.get('output_format')
    if fmt:
        valid_formats = ['jpg', 'png', 'webp']
        fmt_lower = fmt.lower()
        if fmt_lower not in valid_formats:
            raise ValueError(f"Invalid format. Must be one of: {', '.join(valid_formats)}")
        payload['output_format'] = fmt_lower

    # Reference images (optional, up to 4)
    image_input = kwargs.get('image_input') or kwargs.get('reference_images')
    if image_input:
        if isinstance(image_input, str):
            image_input = [image_input]
        if len(image_input) > 4:
            raise ValueError("Maximum 4 reference images allowed")
        payload['image_input'] = image_input

    return payload
