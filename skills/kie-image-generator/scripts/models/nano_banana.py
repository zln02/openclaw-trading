"""Nano Banana (Gemini 2.5 Flash) parameter handler"""

from typing import Dict, Any


def build_nano_payload(prompt: str, **kwargs) -> Dict[str, Any]:
    """
    Build payload for Nano Banana (Gemini 2.5 Flash) model via Jobs API.

    Parameters:
        prompt: Image description (max 5000 chars)
        format: Output format (png, jpeg) [default: png]
        size: Image size (1:1, 9:16, 16:9, 3:4, 4:3, 3:2, 2:3, 5:4, 4:5, 21:9, auto) [default: 1:1]

    Returns:
        API request payload for Jobs API
    """
    if len(prompt) > 5000:
        raise ValueError("Prompt must be 5000 characters or less")

    payload = {'prompt': prompt}

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
