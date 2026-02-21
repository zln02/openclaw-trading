"""Ideogram V3 and Character parameter handler"""

from typing import Dict, Any, Optional, List


def build_ideogram_payload(prompt: str, model: str, **kwargs) -> Dict[str, Any]:
    """
    Build payload for Ideogram V3 and Ideogram Character models.

    Parameters:
        prompt: Image description
        model: Model ID ('ideogram-v3' or 'ideogram-character')
        rendering: Rendering speed (TURBO, BALANCED, QUALITY) [default: BALANCED]
        style: Style preset (AUTO, GENERAL, REALISTIC, DESIGN, FICTION) [default: AUTO]
        size: Image size/aspect ratio
        num_images: Number of images (1-4) [default: 1]
        expand_prompt: Enable MagicPrompt enhancement [default: False]
        seed: Random seed for reproducibility
        negative_prompt: Elements to exclude
        reference_images: Reference image URLs (for ideogram-character)

    Returns:
        API request payload
    """
    payload = {'prompt': prompt}

    # Rendering speed
    rendering = kwargs.get('rendering', 'BALANCED')
    if rendering:
        valid_speeds = ['TURBO', 'BALANCED', 'QUALITY']
        rendering_upper = rendering.upper()
        if rendering_upper not in valid_speeds:
            raise ValueError(f"Invalid rendering. Must be one of: {', '.join(valid_speeds)}")
        payload['rendering_speed'] = rendering_upper

    # Style
    style = kwargs.get('style', 'AUTO')
    if style:
        if model == 'ideogram-v3':
            valid_styles = ['AUTO', 'GENERAL', 'REALISTIC', 'DESIGN']
        else:  # ideogram-character
            valid_styles = ['AUTO', 'REALISTIC', 'FICTION']

        style_upper = style.upper()
        if style_upper not in valid_styles:
            raise ValueError(f"Invalid style. Must be one of: {', '.join(valid_styles)}")
        payload['style'] = style_upper

    # Image size
    size = kwargs.get('size')
    if size:
        payload['image_size'] = size

    # Number of images (API expects string)
    num_images = kwargs.get('num_images', 1)
    if num_images:
        num_images = int(num_images)
        if not 1 <= num_images <= 4:
            raise ValueError("num_images must be between 1 and 4")
        payload['num_images'] = str(num_images)

    # Expand prompt (MagicPrompt)
    expand_prompt = kwargs.get('expand_prompt', False)
    if expand_prompt:
        payload['expand_prompt'] = bool(expand_prompt)

    # Seed
    seed = kwargs.get('seed')
    if seed is not None:
        payload['seed'] = int(seed)

    # Negative prompt
    negative = kwargs.get('negative_prompt') or kwargs.get('negative')
    if negative:
        payload['negative_prompt'] = negative

    # Reference images (for ideogram-character)
    if model == 'ideogram-character':
        reference_images = kwargs.get('reference_images') or kwargs.get('reference')
        if reference_images:
            if isinstance(reference_images, str):
                reference_images = [reference_images]
            payload['reference_image_urls'] = reference_images

    return payload
