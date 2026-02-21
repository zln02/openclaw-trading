"""GPT-4O Image parameter handler"""

from typing import Dict, Any


def build_gpt4o_payload(prompt: str, **kwargs) -> Dict[str, Any]:
    """
    Build payload for GPT-4O Image model.

    Parameters:
        prompt: Image description
        size: Aspect ratio (1:1, 3:2, 2:3) [default: 1:1]
        variants: Number of variants (1-4) [default: 1]

    Returns:
        API request payload
    """
    payload = {'prompt': prompt}

    # Size parameter
    size = kwargs.get('size', '1:1')
    if size:
        valid_sizes = ['1:1', '3:2', '2:3']
        if size not in valid_sizes:
            raise ValueError(f"Invalid size. Must be one of: {', '.join(valid_sizes)}")
        payload['size'] = size

    # Number of variants
    variants = kwargs.get('variants', 1)
    if variants:
        variants = int(variants)
        if not 1 <= variants <= 4:
            raise ValueError("variants must be between 1 and 4")
        payload['nVariants'] = variants

    return payload
