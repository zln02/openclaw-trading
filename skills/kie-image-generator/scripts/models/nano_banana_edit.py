"""Nano Banana Edit (Gemini 2.5 Flash) parameter handler"""

from typing import Dict, Any, List

def build_nano_edit_payload(prompt: str, **kwargs) -> Dict[str, Any]:
    """
    Build payload for Nano Banana Edit model via Jobs API.

    Parameters:
        prompt: Image editing instruction (max 5000 chars)
        image_urls: List of input image URLs (required, up to 10 images)
        format: Output format (png, jpeg) [default: png]
        size: Image size (1:1, 9:16, 16:9, 3:4, 4:3, 3:2, 2:3, 5:4, 4:5, 21:9, auto) [default: 1:1]

    Returns:
        API request payload for Jobs API
    """
    if len(prompt) > 5000:
        raise ValueError("Prompt must be 5000 characters or less")

    # image_urls is required for edit model
    image_urls = kwargs.get('image_urls') or kwargs.get('image_url') or kwargs.get('reference') or kwargs.get('reference_images')
    if not image_urls:
        raise ValueError("image_urls parameter is required for nano-banana-edit model. Use --reference or --reference-images")

    # Convert single URL to list
    if isinstance(image_urls, str):
        image_urls = [image_urls]

    if len(image_urls) > 10:
        raise ValueError("Maximum 10 input images allowed")

    payload = {
        'prompt': prompt,
        'image_urls': image_urls
    }

    # Output format (lowercase for Jobs API)
    fmt = kwargs.get('format', 'png')
    if fmt:
        valid_formats = ['png', 'jpeg']
        fmt_lower = fmt.lower()
        if fmt_lower not in valid_formats:
            raise ValueError(f"Invalid format. Must be one of: {', '.join(valid_formats)}")
        payload['output_format'] = fmt_lower

    # Image size
    size = kwargs.get('size', '1:1')
    if size:
        valid_sizes = ['1:1', '9:16', '16:9', '3:4', '4:3', '3:2', '2:3', '5:4', '4:5', '21:9', 'auto']
        if size not in valid_sizes:
            raise ValueError(f"Invalid size. Must be one of: {', '.join(valid_sizes)}")
        payload['image_size'] = size

    return payload
