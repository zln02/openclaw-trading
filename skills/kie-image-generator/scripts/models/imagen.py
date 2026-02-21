"""Imagen 4 parameter handler"""

from typing import Dict, Any, Optional


def build_imagen_payload(prompt: str, **kwargs) -> Dict[str, Any]:
    """
    Build payload for Imagen 4 models (Ultra, Standard, Fast).

    Parameters:
        prompt: Image description
        negative_prompt: Elements to exclude
        aspect_ratio: Aspect ratio (1:1, 16:9, 9:16, 3:4, 4:3) [default: 1:1]
        num_images: Number of images (1-4) [default: 1]
        seed: Random seed for reproducibility

    Returns:
        API request payload
    """
    payload = {'prompt': prompt}

    # Negative prompt
    negative = kwargs.get('negative_prompt') or kwargs.get('negative')
    if negative:
        payload['negative_prompt'] = negative

    # Aspect ratio
    aspect_ratio = kwargs.get('aspect_ratio', '1:1')
    if aspect_ratio:
        valid_ratios = ['1:1', '16:9', '9:16', '3:4', '4:3']
        if aspect_ratio not in valid_ratios:
            raise ValueError(f"Invalid aspect_ratio. Must be one of: {', '.join(valid_ratios)}")
        payload['aspect_ratio'] = aspect_ratio

    # Number of images (API expects string)
    num_images = kwargs.get('num_images', 1)
    if num_images:
        num_images = int(num_images)
        if not 1 <= num_images <= 4:
            raise ValueError("num_images must be between 1 and 4")
        payload['num_images'] = str(num_images)

    # Seed
    seed = kwargs.get('seed')
    if seed is not None:
        payload['seed'] = int(seed)

    return payload
