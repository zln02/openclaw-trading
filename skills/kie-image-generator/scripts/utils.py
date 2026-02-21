#!/usr/bin/env python3
"""
Utility functions for Kie.ai image generation
"""

import os
import time
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, List
from dotenv import load_dotenv


# Credit conversion rate
CREDIT_TO_USD = 0.005  # 1 credit = $0.005

# Model catalog with pricing and metadata
MODELS = {
    # GPT-4O Image
    'gpt4o-image': {
        'name': 'GPT-4O Image',
        'model_id': None,  # Direct API
        'type': 'text-to-image',
        'estimated_credits': 50,
        'features': ['High quality', 'Text rendering', 'Creative styles'],
        'max_prompt': 4000,
    },
    # Flux Kontext
    'flux-kontext-pro': {
        'name': 'Flux Kontext Pro',
        'model_id': None,  # Direct API
        'type': 'text-to-image',
        'estimated_credits': 30,
        'features': ['Fast', 'Image editing', 'Reference support'],
        'max_prompt': 2000,
    },
    'flux-kontext-max': {
        'name': 'Flux Kontext Max',
        'model_id': None,  # Direct API
        'type': 'text-to-image',
        'estimated_credits': 60,
        'features': ['Highest quality', 'Image editing', 'Reference support'],
        'max_prompt': 2000,
    },
    # Nano Banana (Google)
    'nano-banana': {
        'name': 'Nano Banana',
        'model_id': 'google/nano-banana',
        'type': 'text-to-image',
        'estimated_credits': 20,
        'features': ['Fast', 'Cost effective'],
        'max_prompt': 2000,
    },
    'nano-banana-pro': {
        'name': 'Nano Banana Pro',
        'model_id': 'nano-banana-pro',
        'type': 'text-to-image',
        'estimated_credits': 40,
        'features': ['Higher quality', 'Resolution options'],
        'max_prompt': 2000,
    },
    'nano-banana-edit': {
        'name': 'Nano Banana Edit',
        'model_id': 'google/nano-banana-edit',
        'type': 'image-to-image',
        'estimated_credits': 25,
        'features': ['Image editing', 'Inpainting'],
        'max_prompt': 2000,
    },
    # Seedream (ByteDance)
    'seedream-v4': {
        'name': 'Seedream V4',
        'model_id': 'bytedance/seedream-v4-text-to-image',
        'type': 'text-to-image',
        'estimated_credits': 35,
        'features': ['High quality', '4K support', 'Multi-image'],
        'max_prompt': 2500,
    },
    'seedream-v4-edit': {
        'name': 'Seedream V4 Edit',
        'model_id': 'bytedance/seedream-v4-edit',
        'type': 'image-to-image',
        'estimated_credits': 40,
        'features': ['Image editing', 'Reference images'],
        'max_prompt': 2500,
    },
    # Imagen 4 (Google) - model IDs use "imagen4" without hyphen
    'imagen-4-ultra': {
        'name': 'Imagen 4 Ultra',
        'model_id': 'google/imagen4-ultra',
        'type': 'text-to-image',
        'estimated_credits': 100,
        'features': ['Highest quality', 'Photorealistic', 'Long prompts'],
        'max_prompt': 4096,
    },
    'imagen-4': {
        'name': 'Imagen 4',
        'model_id': 'google/imagen4',
        'type': 'text-to-image',
        'estimated_credits': 50,
        'features': ['High quality', 'Balanced', 'Good for most use cases'],
        'max_prompt': 4096,
    },
    'imagen-4-fast': {
        'name': 'Imagen 4 Fast',
        'model_id': 'google/imagen4-fast',
        'type': 'text-to-image',
        'estimated_credits': 25,
        'features': ['Fast generation', 'Cost effective'],
        'max_prompt': 4096,
    },
    # Ideogram
    'ideogram-v3': {
        'name': 'Ideogram V3',
        'model_id': 'ideogram/v3-text-to-image',
        'type': 'text-to-image',
        'estimated_credits': 40,
        'features': ['Text rendering', 'Design focused', 'Style presets'],
        'max_prompt': 2000,
    },
    'ideogram-character': {
        'name': 'Ideogram Character',
        'model_id': 'ideogram/character',
        'type': 'text-to-image',
        'estimated_credits': 45,
        'features': ['Character consistency', 'Reference images'],
        'max_prompt': 2000,
    },
}


def load_api_key(skill_dir: Optional[Path] = None) -> str:
    """
    Load Kie.ai API key from environment variable or .env file.

    Priority order:
    1. Environment variable KIEAI_API_KEY (set via auth-loader or shell)
    2. ~/.claude/auth/kiei-api.env (centralized auth management)
    3. Skill directory .env file (local fallback)

    Args:
        skill_dir: Path to skill directory (default: script's parent directory)

    Returns:
        API key string

    Raises:
        ValueError: If API key is not found or invalid
    """
    # 1. Check if KIEAI_API_KEY is already set in environment
    api_key = os.getenv('KIEAI_API_KEY', '').strip()
    if api_key and api_key != 'your_api_key_here':
        return api_key

    # 2. Try loading from centralized auth directory (~/.claude/auth/)
    auth_env = Path.home() / '.claude' / 'auth' / 'kiei-api.env'
    if auth_env.exists():
        load_dotenv(auth_env)
        api_key = os.getenv('KIEAI_API_KEY', '').strip()
        if api_key and api_key != 'your_api_key_here':
            return api_key

    # 3. Fallback to skill directory .env
    if skill_dir is None:
        skill_dir = Path(__file__).parent.parent

    env_file = skill_dir / '.env'
    env_example = skill_dir / '.env.example'

    if env_file.exists():
        load_dotenv(env_file)
    elif env_example.exists():
        print(f"⚠️  .env file not found. Creating from .env.example...")
        with open(env_file, 'w') as f:
            f.write(env_example.read_text())
        print(f"📝 Please edit {env_file} and add your Kie.ai API key")
        raise ValueError("API key not configured. Please edit .env file.")

    api_key = os.getenv('KIEAI_API_KEY', '').strip()

    if not api_key or api_key == 'your_api_key_here':
        raise ValueError(
            "KIEAI_API_KEY not found. Set it via:\n"
            "  1. Environment variable: export KIEAI_API_KEY=your_key\n"
            "  2. Auth loader: ~/.claude/auth/kiei-api.env\n"
            "  3. Skill .env file: " + str(env_file) + "\n"
            "Get your API key from https://kie.ai/dashboard/api-keys"
        )

    return api_key


def get_credits(api_key: str) -> Tuple[float, float]:
    """
    Get current account credits.

    Args:
        api_key: Kie.ai API key

    Returns:
        Tuple of (credits, usd_value)

    Raises:
        RuntimeError: If API request fails
    """
    url = "https://api.kie.ai/api/v1/chat/credit"
    headers = {'Authorization': f'Bearer {api_key}'}

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise RuntimeError(f"Failed to get credits: {response.status_code}")

    data = response.json()

    if data.get('code') != 200:
        raise RuntimeError(f"API error: {data.get('msg', 'Unknown error')}")

    credits = data.get('data', 0)
    return credits, credits * CREDIT_TO_USD


def print_credits(api_key: str) -> None:
    """Print current account credits."""
    credits, usd = get_credits(api_key)
    print(f"💰 Current Balance: {credits:,.1f} credits (${usd:.2f} USD)")


def print_models(filter_type: Optional[str] = None) -> None:
    """
    Print available models with pricing information.

    Args:
        filter_type: Optional filter for 'text-to-image' or 'image-to-image'
    """
    print("\n📸 Available Image Models\n")
    print(f"{'Model ID':<22} {'Name':<22} {'Type':<15} {'Est. Credits':<12} {'Est. USD':<10}")
    print("-" * 85)

    # Sort by type, then by credits
    sorted_models = sorted(
        MODELS.items(),
        key=lambda x: (x[1]['type'], x[1]['estimated_credits'])
    )

    for model_id, model in sorted_models:
        if filter_type and model['type'] != filter_type:
            continue

        name = model['name']
        mtype = model['type']
        credits = model['estimated_credits']
        usd = credits * CREDIT_TO_USD

        print(f"{model_id:<22} {name:<22} {mtype:<15} {credits:<12} ${usd:<9.2f}")

    print()
    print("💡 Credit costs are estimates. Actual costs may vary by parameters.")
    print("   1 credit = $0.005 USD")


def select_model_interactive(has_image: bool = False) -> Optional[str]:
    """
    Interactive model selection with cost display.

    Args:
        has_image: True if user provided reference image

    Returns:
        Selected model ID or None if cancelled
    """
    # Filter models based on context
    if has_image:
        available = {k: v for k, v in MODELS.items()}  # All models for image input
    else:
        available = {k: v for k, v in MODELS.items() if v['type'] == 'text-to-image'}

    # Sort by estimated credits (cheapest first)
    sorted_models = sorted(
        available.items(),
        key=lambda x: x[1]['estimated_credits']
    )

    print("\n📸 Select a Model:\n")
    print(f"{'#':<3} {'Model':<25} {'Type':<15} {'Credits':<10} {'USD':<8} {'Features'}")
    print("-" * 90)

    for i, (model_id, model) in enumerate(sorted_models, 1):
        credits = model['estimated_credits']
        usd = credits * CREDIT_TO_USD
        features = ', '.join(model.get('features', [])[:2])
        mtype = 'T2I' if model['type'] == 'text-to-image' else 'I2I'

        print(f"{i:<3} {model['name']:<25} {mtype:<15} ~{credits:<9} ${usd:<7.2f} {features}")

    print()
    try:
        choice = input("Enter number (or 'q' to quit): ").strip()

        if choice.lower() in ['q', 'quit', 'exit']:
            return None

        idx = int(choice) - 1
        if 0 <= idx < len(sorted_models):
            selected_id = sorted_models[idx][0]
            print(f"\n✅ Selected: {MODELS[selected_id]['name']}")
            return selected_id
        else:
            print("❌ Invalid selection")
            return None

    except ValueError:
        print("❌ Invalid input")
        return None
    except KeyboardInterrupt:
        return None


def confirm_generation(model_id: str, current_credits: float) -> bool:
    """
    Confirm generation with cost information.

    Args:
        model_id: Selected model ID
        current_credits: Current account credits

    Returns:
        True if user confirms, False otherwise
    """
    model = MODELS.get(model_id)
    if not model:
        return False

    est_credits = model['estimated_credits']
    est_usd = est_credits * CREDIT_TO_USD

    print(f"\n💰 Generation Cost Estimate:")
    print(f"   Model: {model['name']}")
    print(f"   Estimated: ~{est_credits} credits (${est_usd:.2f})")
    print(f"   Current balance: {current_credits:,.1f} credits")

    if current_credits < est_credits:
        print(f"   ⚠️  Warning: Insufficient credits!")
        return False

    remaining = current_credits - est_credits
    print(f"   After generation: ~{remaining:,.1f} credits")

    try:
        confirm = input("\nProceed? [Y/n]: ").strip().lower()
        return confirm in ['', 'y', 'yes']
    except KeyboardInterrupt:
        return False


def submit_task(
    api_key: str,
    endpoint: str,
    payload: Dict[str, Any],
    model_id: Optional[str] = None
) -> str:
    """
    Submit generation task to Kie.ai API.

    Args:
        api_key: Kie.ai API key
        endpoint: API endpoint (e.g., '/api/v1/gpt4o-image/generate')
        payload: Request payload
        model_id: Optional model ID for Jobs API (e.g., 'bytedance/seedream-v4-text-to-image')

    Returns:
        Task ID

    Raises:
        RuntimeError: If API request fails
    """
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    # Use Jobs API if model_id is provided
    if model_id:
        # Check if endpoint specifies v2 API
        if '/v2/' in endpoint:
            url = f"https://api.kie.ai{endpoint}"
        else:
            url = "https://api.kie.ai/api/v1/jobs/createTask"

        jobs_payload = {
            'model': model_id,
            'input': payload
        }
        print(f"🚀 Submitting task via Jobs API (model: {model_id})...")
        response = requests.post(url, headers=headers, json=jobs_payload)
    else:
        # Use direct endpoint
        url = f"https://api.kie.ai{endpoint}"
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        print(f"🚀 Submitting task to {endpoint}...")
        response = requests.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        raise RuntimeError(
            f"API request failed with status {response.status_code}: "
            f"{response.text}"
        )

    data = response.json()

    # Kie.ai response structure: { code: 200, msg: "success", data: { taskId: "..." } }
    if data.get('code') != 200:
        raise RuntimeError(f"API error: {data.get('msg', 'Unknown error')}")

    task_id = data.get('data', {}).get('taskId')
    if not task_id:
        raise RuntimeError("No taskId received from API")

    print(f"✅ Task submitted: {task_id}")
    return task_id


def poll_task(
    api_key: str,
    record_info_endpoint: str,
    task_id: str,
    max_attempts: int = 60,
    poll_interval: int = 2
) -> str:
    """
    Poll task status until completion.

    Args:
        api_key: Kie.ai API key
        record_info_endpoint: Status check endpoint
        task_id: Task ID to poll
        max_attempts: Maximum polling attempts (default: 60)
        poll_interval: Seconds between polls (default: 2)

    Returns:
        Image URL

    Raises:
        RuntimeError: If polling fails or times out
    """
    url = f"https://api.kie.ai{record_info_endpoint}?taskId={task_id}"
    headers = {'Authorization': f'Bearer {api_key}'}

    print(f"⏳ Polling task status (max {max_attempts * poll_interval}s)...")

    for attempt in range(1, max_attempts + 1):
        time.sleep(poll_interval)

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"⚠️  Status check failed: {response.status_code}")
            continue

        data = response.json()
        task_data = data.get('data', {})

        # Check for Jobs API response format (has 'state' field)
        is_jobs_api = 'state' in task_data

        if is_jobs_api:
            # Jobs API format: state = "pending" | "processing" | "success" | "failed"
            state = task_data.get('state', '').lower()
            success_flag = 1 if state == 'success' else (2 if state == 'failed' else 0)
            status = state.upper()
            progress = 100 if state == 'success' else 0
        else:
            # Direct API format
            success_flag = task_data.get('successFlag')
            status = task_data.get('status')
            progress = task_data.get('progress', 0)

        # Convert progress to percentage if it's a float (0.0-1.0)
        if isinstance(progress, (int, float)):
            if 0 <= progress <= 1:
                progress_pct = f"{progress * 100:.2f}%"
            else:
                progress_pct = f"{progress}%"
        else:
            progress_pct = str(progress)

        # Determine task state from successFlag or status
        is_completed = (success_flag == 1) or (status == 'SUCCESS')
        is_failed = (success_flag == 2) or (status in ['FAILED', 'FAIL'])
        is_generating = (success_flag == 0) or (status in ['GENERATING', 'PENDING', 'PROCESSING', None])

        # Display status
        if is_generating:
            status_text = status or 'GENERATING'
        elif is_completed:
            status_text = 'SUCCESS'
        elif is_failed:
            status_text = 'FAILED'
        else:
            status_text = status or 'UNKNOWN'

        print(f"  [{attempt}/{max_attempts}] Status: {status_text} ({progress_pct})")

        # Handle completion
        if is_completed:
            # Extract image URL - try multiple possible field names
            img_url = None

            # Jobs API: Parse resultJson field
            if is_jobs_api and not img_url:
                import json
                result_json = task_data.get('resultJson', '{}')
                try:
                    result_data = json.loads(result_json) if isinstance(result_json, str) else result_json
                    result_urls = result_data.get('resultUrls', [])
                    if result_urls:
                        img_url = result_urls[0]
                except json.JSONDecodeError:
                    pass

            # Try direct fields at task_data level
            if not img_url:
                img_url = (
                    task_data.get('imgUrl') or
                    task_data.get('imageUrl') or
                    task_data.get('image_url') or
                    task_data.get('url')
                )

            # Try resultUrls array at task_data level
            if not img_url:
                result_urls = task_data.get('resultUrls', [])
                if result_urls:
                    img_url = result_urls[0]

            # Try images array
            if not img_url:
                images = task_data.get('images', [])
                if images:
                    img_url = images[0] if isinstance(images[0], str) else images[0].get('url')

            # Try response field variants
            if not img_url:
                response_data = task_data.get('response', {})

                # Try resultUrls array in response (GPT-4O)
                result_urls = (
                    response_data.get('resultUrls') or
                    response_data.get('result_urls') or
                    []
                )
                if result_urls:
                    img_url = result_urls[0]

                # Try resultImageUrl (Flux Kontext)
                if not img_url:
                    img_url = response_data.get('resultImageUrl')

                # Try other possible fields
                if not img_url:
                    img_url = (
                        response_data.get('imageUrl') or
                        response_data.get('image_url')
                    )

            # Try result field
            if not img_url:
                result = task_data.get('result', {})
                img_url = result.get('imageUrl') or result.get('imgUrl') or result.get('url')

            if not img_url:
                raise RuntimeError("No image URL in completed task. Response: " + str(task_data))

            print(f"✅ Task completed!")
            return img_url

        # Handle failure
        elif is_failed:
            error_msg = (
                task_data.get('errorMessage') or
                task_data.get('error') or
                task_data.get('failMsg') or  # Jobs API error field
                task_data.get('failureReason') or
                task_data.get('message') or
                'Unknown error'
            )
            fail_code = task_data.get('failCode', '')
            if fail_code:
                error_msg = f"[{fail_code}] {error_msg}"
            raise RuntimeError(f"Task failed: {error_msg}")

    raise RuntimeError(f"Task timed out after {max_attempts * poll_interval}s")


def download_image(
    image_url: str,
    output_dir: Path,
    filename: str
) -> Path:
    """
    Download image from URL.

    Args:
        image_url: Image URL
        output_dir: Output directory
        filename: Output filename

    Returns:
        Path to downloaded file

    Raises:
        RuntimeError: If download fails
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    print(f"⬇️  Downloading image...")
    response = requests.get(image_url, stream=True)

    if response.status_code != 200:
        raise RuntimeError(f"Download failed: {response.status_code}")

    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"💾 Saved to: {output_path}")
    return output_path


def slugify(text: str, max_length: int = 50) -> str:
    """
    Convert text to filesystem-safe slug.

    Args:
        text: Input text
        max_length: Maximum length

    Returns:
        Slugified string
    """
    import re

    # Convert to lowercase and replace spaces/special chars with hyphens
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    slug = re.sub(r'[-\s]+', '-', slug).strip('-')

    # Truncate to max_length
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip('-')

    return slug or 'image'


def generate_filename(
    model: str,
    prompt: str,
    extension: str = 'png'
) -> str:
    """
    Generate descriptive filename for output image.

    Args:
        model: Model ID
        prompt: Generation prompt
        extension: File extension

    Returns:
        Filename string
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    prompt_slug = slugify(prompt, max_length=30)

    return f"{model}_{prompt_slug}_{timestamp}.{extension}"


# Model endpoint mappings
GENERATION_ENDPOINTS = {
    'gpt4o-image': '/api/v1/gpt4o-image/generate',
    'flux-kontext-pro': '/api/v1/flux/kontext/generate',
    'flux-kontext-max': '/api/v1/flux/kontext/generate',
    'nano-banana': '/api/v1/jobs/createTask',  # Jobs API v1
    'nano-banana-pro': '/api/v1/jobs/createTask',  # Jobs API v1
    'nano-banana-edit': '/api/v1/jobs/createTask',  # Jobs API v1
    'seedream-v4': '/api/v1/jobs/createTask',  # Jobs API
    'seedream-v4-edit': '/api/v1/jobs/createTask',  # Jobs API
    'imagen-4-ultra': '/api/v1/jobs/createTask',  # Jobs API
    'imagen-4': '/api/v1/jobs/createTask',  # Jobs API
    'imagen-4-fast': '/api/v1/jobs/createTask',  # Jobs API
    'ideogram-v3': '/api/v1/jobs/createTask',  # Jobs API
    'ideogram-character': '/api/v1/jobs/createTask',  # Jobs API
}

RECORD_INFO_ENDPOINTS = {
    'gpt4o-image': '/api/v1/gpt4o-image/record-info',
    'flux-kontext-pro': '/api/v1/flux/kontext/record-info',
    'flux-kontext-max': '/api/v1/flux/kontext/record-info',
    'nano-banana': '/api/v1/jobs/recordInfo',  # Jobs API v1 status endpoint
    'nano-banana-pro': '/api/v1/jobs/recordInfo',  # Jobs API v1 status endpoint (shared)
    'nano-banana-edit': '/api/v1/jobs/recordInfo',  # Jobs API v1 status endpoint
    'seedream-v4': '/api/v1/jobs/recordInfo',  # Jobs API status endpoint
    'seedream-v4-edit': '/api/v1/jobs/recordInfo',  # Jobs API status endpoint
    'imagen-4-ultra': '/api/v1/jobs/recordInfo',  # Jobs API status endpoint
    'imagen-4': '/api/v1/jobs/recordInfo',  # Jobs API status endpoint
    'imagen-4-fast': '/api/v1/jobs/recordInfo',  # Jobs API status endpoint
    'ideogram-v3': '/api/v1/jobs/recordInfo',  # Jobs API status endpoint
    'ideogram-character': '/api/v1/jobs/recordInfo',  # Jobs API status endpoint
}

# Jobs API model IDs
JOBS_API_MODELS = {
    'nano-banana': 'google/nano-banana',
    'nano-banana-pro': 'nano-banana-pro',  # v2 API model
    'nano-banana-edit': 'google/nano-banana-edit',
    'seedream-v4': 'bytedance/seedream-v4-text-to-image',
    'seedream-v4-edit': 'bytedance/seedream-v4-edit',
    'imagen-4-ultra': 'google/imagen4-ultra',
    'imagen-4': 'google/imagen4',
    'imagen-4-fast': 'google/imagen4-fast',
    'ideogram-v3': 'ideogram/v3-text-to-image',
    'ideogram-character': 'ideogram/character',
}
