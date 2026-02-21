"""Seedream V4 Edit parameter handler"""

from typing import Dict, Any, Optional, List

def build_seedream_edit_payload(prompt: str, **kwargs) -> Dict[str, Any]:
    """
    Build payload for Seedream V4 Edit model.

    Parameters:
        prompt: Image editing instruction (max 5000 chars)
        image_urls: List of input image URLs (required, up to 10 images)
        image_size: Image size/aspect ratio
        image_resolution: Image resolution (1K, 2K, 4K) [default: 1K]
        max_images: Number of output images (1-6) [default: 1]
        seed: Random seed for reproducibility

    Returns:
        API request payload
    """
    if len(prompt) > 5000:
        raise ValueError("Prompt must be 5000 characters or less")

    # image_urls is required for edit model
    image_urls = kwargs.get('image_urls') or kwargs.get('image_url')
    if not image_urls:
        raise ValueError("image_urls parameter is required for seedream-edit model")

    # Convert single URL to list
    if isinstance(image_urls, str):
        image_urls = [image_urls]

    if len(image_urls) > 10:
        raise ValueError("Maximum 10 input images allowed")

    payload = {
        'prompt': prompt,
        'image_urls': image_urls
    }

    # Image size
    size = kwargs.get('size')
    if size:
        payload['image_size'] = size

    # Resolution
    resolution = kwargs.get('resolution', '1K')
    if resolution:
        valid_resolutions = ['1K', '2K', '4K']
        if resolution.upper() not in valid_resolutions:
            raise ValueError(f"Invalid resolution. Must be one of: {', '.join(valid_resolutions)}")
        payload['image_resolution'] = resolution.upper()

    # Number of images
    images = kwargs.get('images', 1)
    if images:
        images = int(images)
        if not 1 <= images <= 6:
            raise ValueError("images must be between 1 and 6")
        payload['max_images'] = images

    # Seed
    seed = kwargs.get('seed')
    if seed is not None:
        payload['seed'] = int(seed)

    return payload
