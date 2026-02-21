"""Seedream 4.0 parameter handler"""

from typing import Dict, Any, Optional


def build_seedream_payload(prompt: str, **kwargs) -> Dict[str, Any]:
    """
    Build payload for Seedream 4.0 model.

    Parameters:
        prompt: Image description (max 5000 chars)
        size: Image size/aspect ratio
        resolution: Image resolution (1K, 2K, 4K) [default: 2K]
        images: Number of images (1-6) [default: 1]
        seed: Random seed for reproducibility

    Returns:
        API request payload
    """
    if len(prompt) > 5000:
        raise ValueError("Prompt must be 5000 characters or less")

    payload = {'prompt': prompt}

    # Image size
    size = kwargs.get('size')
    if size:
        payload['image_size'] = size

    # Resolution
    resolution = kwargs.get('resolution', '2K')
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
