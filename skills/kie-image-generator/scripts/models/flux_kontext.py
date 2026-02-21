"""Flux Kontext parameter handler"""

from typing import Dict, Any


def build_flux_payload(prompt: str, **kwargs) -> Dict[str, Any]:
    """
    Build payload for Flux Kontext Pro/Max models.

    Parameters:
        prompt: Image description
        ratio: Image ratio (16:9, 21:9, 4:3, 1:1, 3:4, 9:16, 16:21) [default: 1:1]
        format: Output format (jpeg, png) [default: png]

    Returns:
        API request payload
    """
    payload = {'prompt': prompt}

    # Image ratio
    ratio = kwargs.get('ratio', '1:1')
    if ratio:
        valid_ratios = ['16:9', '21:9', '4:3', '1:1', '3:4', '9:16', '16:21']
        if ratio not in valid_ratios:
            raise ValueError(f"Invalid ratio. Must be one of: {', '.join(valid_ratios)}")
        payload['image_ratio'] = ratio

    # Output format
    fmt = kwargs.get('format', 'png')
    if fmt:
        valid_formats = ['jpeg', 'png']
        if fmt.lower() not in valid_formats:
            raise ValueError(f"Invalid format. Must be one of: {', '.join(valid_formats)}")
        payload['output_format'] = fmt.lower()

    return payload
