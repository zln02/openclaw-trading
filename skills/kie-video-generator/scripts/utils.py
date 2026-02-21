#!/usr/bin/env python3
"""
Utility functions for Kie.ai video generation
"""

import os
import time
import json
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from dotenv import load_dotenv


# Model configurations with estimated costs (in credits)
# 1 credit = $0.005 USD
MODELS = {
    # Google Veo 3
    'veo3': {
        'model_id': 'veo3',
        'name': 'Veo 3 Quality',
        'type': 'text-to-video',
        'supports_image': True,
        'endpoint': '/api/v1/veo/generate',
        'record_endpoint': '/api/v1/veo/record-info',
        'estimated_credits': 400,  # $2.00
        'description': 'Highest quality, 1080P capable',
    },
    'veo3-fast': {
        'model_id': 'veo3_fast',
        'name': 'Veo 3 Fast',
        'type': 'text-to-video',
        'supports_image': True,
        'endpoint': '/api/v1/veo/generate',
        'record_endpoint': '/api/v1/veo/record-info',
        'estimated_credits': 80,  # $0.40
        'description': 'Cost-efficient, good quality',
    },
    # Sora 2
    'sora-2-t2v': {
        'model_id': 'sora-2-text-to-video',
        'name': 'Sora 2 Text-to-Video',
        'type': 'text-to-video',
        'supports_image': False,
        'endpoint': '/api/v1/jobs/createTask',
        'record_endpoint': '/api/v1/jobs/recordInfo',
        'estimated_credits': 200,
        'description': 'OpenAI Sora 2 text-to-video',
    },
    'sora-2-pro-t2v': {
        'model_id': 'sora-2-pro-text-to-video',
        'name': 'Sora 2 Pro Text-to-Video',
        'type': 'text-to-video',
        'supports_image': False,
        'endpoint': '/api/v1/jobs/createTask',
        'record_endpoint': '/api/v1/jobs/recordInfo',
        'estimated_credits': 400,
        'description': 'OpenAI Sora 2 Pro quality',
    },
    'sora-2-i2v': {
        'model_id': 'sora-2-image-to-video',
        'name': 'Sora 2 Image-to-Video',
        'type': 'image-to-video',
        'supports_image': True,
        'endpoint': '/api/v1/jobs/createTask',
        'record_endpoint': '/api/v1/jobs/recordInfo',
        'estimated_credits': 300,
        'description': 'Animate images with Sora 2',
    },
    'sora-2-watermark-remover': {
        'model_id': 'sora-2-watermark-remover',
        'name': 'Sora 2 Watermark Remover',
        'type': 'utility',
        'supports_image': False,
        'endpoint': '/api/v1/jobs/createTask',
        'record_endpoint': '/api/v1/jobs/recordInfo',
        'estimated_credits': 100,
        'description': 'Remove watermarks from videos',
    },
    # Kling
    'kling-2.6-t2v': {
        'model_id': 'kling-2.6/text-to-video',
        'name': 'Kling 2.6 Text-to-Video',
        'type': 'text-to-video',
        'supports_image': False,
        'endpoint': '/api/v1/jobs/createTask',
        'record_endpoint': '/api/v1/jobs/recordInfo',
        'estimated_credits': 100,
        'description': 'Kling 2.6 with sound support',
    },
    'kling-2.6-i2v': {
        'model_id': 'kling-2.6/image-to-video',
        'name': 'Kling 2.6 Image-to-Video',
        'type': 'image-to-video',
        'supports_image': True,
        'endpoint': '/api/v1/jobs/createTask',
        'record_endpoint': '/api/v1/jobs/recordInfo',
        'estimated_credits': 120,
        'description': 'Animate images with Kling 2.6',
    },
    'kling-2.5-t2v': {
        'model_id': 'kling-2.5/text-to-video',
        'name': 'Kling 2.5 Text-to-Video',
        'type': 'text-to-video',
        'supports_image': False,
        'endpoint': '/api/v1/jobs/createTask',
        'record_endpoint': '/api/v1/jobs/recordInfo',
        'estimated_credits': 80,
        'description': 'Kling 2.5 generation',
    },
    'kling-2.1-master': {
        'model_id': 'kling/v2-1-master-text-to-video',
        'name': 'Kling 2.1 Master',
        'type': 'text-to-video',
        'supports_image': False,
        'endpoint': '/api/v1/jobs/createTask',
        'record_endpoint': '/api/v1/jobs/recordInfo',
        'estimated_credits': 160,
        'description': 'Kling V2.1 Master quality',
    },
    # Wan
    'wan-2.6-t2v': {
        'model_id': 'wan/2-6-text-to-video',
        'name': 'Wan 2.6 Text-to-Video',
        'type': 'text-to-video',
        'supports_image': False,
        'endpoint': '/api/v1/jobs/createTask',
        'record_endpoint': '/api/v1/jobs/recordInfo',
        'estimated_credits': 60,
        'description': 'Wan 2.6 up to 1080p, 15s',
    },
    'wan-2.5-t2v': {
        'model_id': 'wan/2-5-text-to-video',
        'name': 'Wan 2.5 Text-to-Video',
        'type': 'text-to-video',
        'supports_image': False,
        'endpoint': '/api/v1/jobs/createTask',
        'record_endpoint': '/api/v1/jobs/recordInfo',
        'estimated_credits': 50,
        'description': 'Wan 2.5 generation',
    },
    'wan-2.2-t2v': {
        'model_id': 'wan/2-2-text-to-video',
        'name': 'Wan 2.2 Text-to-Video',
        'type': 'text-to-video',
        'supports_image': False,
        'endpoint': '/api/v1/jobs/createTask',
        'record_endpoint': '/api/v1/jobs/recordInfo',
        'estimated_credits': 40,
        'description': 'Wan 2.2 generation',
    },
    'wan-2.2-i2v-turbo': {
        'model_id': 'wan/2-2-a14b-image-to-video-turbo',
        'name': 'Wan 2.2 I2V Turbo',
        'type': 'image-to-video',
        'supports_image': True,
        'endpoint': '/api/v1/jobs/createTask',
        'record_endpoint': '/api/v1/jobs/recordInfo',
        'estimated_credits': 30,
        'description': 'Wan 2.2 image animation (turbo)',
    },
    # Hailuo
    'hailuo-2.3-i2v-standard': {
        'model_id': 'hailuo/02-image-to-video-standard',
        'name': 'Hailuo 2.3 I2V Standard',
        'type': 'image-to-video',
        'supports_image': True,
        'endpoint': '/api/v1/jobs/createTask',
        'record_endpoint': '/api/v1/jobs/recordInfo',
        'estimated_credits': 60,
        'description': 'Hailuo standard image-to-video',
    },
    'hailuo-2.3-i2v-pro': {
        'model_id': 'hailuo/02-image-to-video-pro',
        'name': 'Hailuo 2.3 I2V Pro',
        'type': 'image-to-video',
        'supports_image': True,
        'endpoint': '/api/v1/jobs/createTask',
        'record_endpoint': '/api/v1/jobs/recordInfo',
        'estimated_credits': 100,
        'description': 'Hailuo pro image-to-video',
    },
    'hailuo-2.3-t2v-standard': {
        'model_id': 'hailuo/02-text-to-video-standard',
        'name': 'Hailuo 2.3 T2V Standard',
        'type': 'text-to-video',
        'supports_image': False,
        'endpoint': '/api/v1/jobs/createTask',
        'record_endpoint': '/api/v1/jobs/recordInfo',
        'estimated_credits': 60,
        'description': 'Hailuo standard text-to-video',
    },
    # Seedance
    'seedance-1.5-pro': {
        'model_id': 'bytedance/seedance-1.5-pro',
        'name': 'Seedance 1.5 Pro',
        'type': 'text-to-video',
        'supports_image': True,
        'endpoint': '/api/v1/jobs/createTask',
        'record_endpoint': '/api/v1/jobs/recordInfo',
        'estimated_credits': 80,
        'description': 'ByteDance Seedance 1.5 Pro',
    },
    # Grok
    'grok-imagine-t2v': {
        'model_id': 'grok-imagine/text-to-video',
        'name': 'Grok Imagine T2V',
        'type': 'text-to-video',
        'supports_image': False,
        'endpoint': '/api/v1/jobs/createTask',
        'record_endpoint': '/api/v1/jobs/recordInfo',
        'estimated_credits': 20,  # ~$0.10 for 6s
        'description': 'xAI Grok text-to-video',
    },
    'grok-imagine-i2v': {
        'model_id': 'grok-imagine/image-to-video',
        'name': 'Grok Imagine I2V',
        'type': 'image-to-video',
        'supports_image': True,
        'endpoint': '/api/v1/jobs/createTask',
        'record_endpoint': '/api/v1/jobs/recordInfo',
        'estimated_credits': 20,  # ~$0.10 for 6s
        'description': 'xAI Grok image-to-video',
    },
}

# Credit to USD conversion
CREDIT_TO_USD = 0.005


def load_api_key(skill_dir: Optional[Path] = None) -> str:
    """
    Load Kie.ai API key from environment variable or .env file.

    Priority order:
    1. Environment variable KIEAI_API_KEY (set via auth-loader or shell)
    2. ~/.claude/auth/kiei-api.env (centralized auth management)
    3. Skill directory .env file (local fallback)
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

    if env_file.exists():
        load_dotenv(env_file)

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


def get_credits(api_key: str) -> Tuple[int, float]:
    """
    Get current account credits.

    Returns:
        Tuple of (credits, usd_value)
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
    usd_value = credits * CREDIT_TO_USD

    return credits, usd_value


def print_credits(api_key: str) -> Tuple[int, float]:
    """Print current account credits in a formatted way."""
    credits, usd = get_credits(api_key)

    print("\n💰 Kie.ai Account Balance")
    print("━" * 30)
    print(f"Available Credits: {credits:,}")
    print(f"Estimated Value: ${usd:.2f} USD")
    print("━" * 30)

    return credits, usd


def print_models():
    """Print all available models with estimated costs."""
    print("\n📹 Available Video Generation Models")
    print("━" * 70)
    print(f"{'ID':<25} {'Name':<30} {'Type':<15} {'~Cost':<10}")
    print("─" * 70)

    # Group by type
    t2v_models = {k: v for k, v in MODELS.items() if v['type'] == 'text-to-video'}
    i2v_models = {k: v for k, v in MODELS.items() if v['type'] == 'image-to-video'}
    other_models = {k: v for k, v in MODELS.items() if v['type'] not in ['text-to-video', 'image-to-video']}

    print("\n  🎬 Text-to-Video Models:")
    for model_id, info in sorted(t2v_models.items(), key=lambda x: x[1]['estimated_credits']):
        cost_usd = info['estimated_credits'] * CREDIT_TO_USD
        print(f"  {model_id:<23} {info['name']:<30} {'T2V':<15} ${cost_usd:.2f}")

    print("\n  🖼️  Image-to-Video Models:")
    for model_id, info in sorted(i2v_models.items(), key=lambda x: x[1]['estimated_credits']):
        cost_usd = info['estimated_credits'] * CREDIT_TO_USD
        print(f"  {model_id:<23} {info['name']:<30} {'I2V':<15} ${cost_usd:.2f}")

    if other_models:
        print("\n  🔧 Utility Models:")
        for model_id, info in sorted(other_models.items(), key=lambda x: x[1]['estimated_credits']):
            cost_usd = info['estimated_credits'] * CREDIT_TO_USD
            print(f"  {model_id:<23} {info['name']:<30} {info['type']:<15} ${cost_usd:.2f}")

    print("━" * 70)
    print("Note: Costs are estimates. Actual costs may vary by parameters.\n")


def select_model_interactive(prompt: str, has_image: bool = False) -> Optional[str]:
    """Interactive model selection with cost comparison."""
    print("\n📊 Select a model for generation:")
    print("━" * 60)

    # Filter models based on whether we have an image
    if has_image:
        available = {k: v for k, v in MODELS.items() if v['supports_image']}
        print("(Showing models that support image input)\n")
    else:
        available = {k: v for k, v in MODELS.items() if v['type'] == 'text-to-video'}
        print("(Showing text-to-video models)\n")

    # Sort by cost
    sorted_models = sorted(available.items(), key=lambda x: x[1]['estimated_credits'])

    for i, (model_id, info) in enumerate(sorted_models, 1):
        cost_usd = info['estimated_credits'] * CREDIT_TO_USD
        print(f"  [{i:2}] {model_id:<25} ${cost_usd:.2f}  - {info['description']}")

    print(f"\n  [0] Cancel")
    print("━" * 60)

    while True:
        try:
            choice = input("\nEnter number (or model ID): ").strip()

            if choice == '0':
                return None

            # Try as number
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(sorted_models):
                    return sorted_models[idx][0]

            # Try as model ID
            if choice in MODELS:
                return choice

            print("Invalid selection. Please try again.")

        except (ValueError, KeyboardInterrupt):
            return None


def confirm_generation(model_id: str, credits: int) -> bool:
    """Show cost estimate and ask for confirmation."""
    model = MODELS.get(model_id)
    if not model:
        return False

    est_credits = model['estimated_credits']
    est_usd = est_credits * CREDIT_TO_USD
    remaining = credits - est_credits
    remaining_usd = remaining * CREDIT_TO_USD

    print("\n📊 Cost Estimate")
    print("━" * 40)
    print(f"Model: {model['name']}")
    print(f"Estimated Cost: ~{est_credits} credits (${est_usd:.2f})")
    print(f"Current Balance: {credits:,} credits (${credits * CREDIT_TO_USD:.2f})")
    print(f"After Generation: ~{remaining:,} credits (${remaining_usd:.2f})")
    print("━" * 40)

    if remaining < 0:
        print("⚠️  Warning: You may not have enough credits!")

    response = input("\nProceed with generation? [y/N]: ").strip().lower()
    return response in ['y', 'yes']


def submit_task(
    api_key: str,
    model_id: str,
    payload: Dict[str, Any]
) -> str:
    """
    Submit video generation task.

    Returns:
        Task ID
    """
    model = MODELS.get(model_id)
    if not model:
        raise ValueError(f"Unknown model: {model_id}")

    endpoint = model['endpoint']
    url = f"https://api.kie.ai{endpoint}"

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    # For Jobs API, wrap with model ID
    if '/jobs/createTask' in endpoint:
        request_payload = {
            'model': model['model_id'],
            'input': payload
        }
    else:
        # Veo API uses different structure
        request_payload = payload
        if model_id in ['veo3', 'veo3-fast']:
            request_payload['model'] = model['model_id']

    print(f"\n🚀 Submitting task to {model['name']}...")

    response = requests.post(url, headers=headers, json=request_payload)

    if response.status_code != 200:
        raise RuntimeError(
            f"API request failed ({response.status_code}): {response.text}"
        )

    data = response.json()

    if data.get('code') != 200:
        raise RuntimeError(f"API error: {data.get('msg', 'Unknown error')}")

    task_id = data.get('data', {}).get('taskId') or data.get('data', {}).get('task_id')
    if not task_id:
        raise RuntimeError("No taskId in response")

    print(f"✅ Task submitted: {task_id}")
    return task_id


def poll_task(
    api_key: str,
    model_id: str,
    task_id: str,
    max_attempts: int = 180,
    poll_interval: int = 5
) -> str:
    """
    Poll task status until completion.

    Returns:
        Video URL
    """
    model = MODELS.get(model_id)
    if not model:
        raise ValueError(f"Unknown model: {model_id}")

    endpoint = model['record_endpoint']
    url = f"https://api.kie.ai{endpoint}?taskId={task_id}"
    headers = {'Authorization': f'Bearer {api_key}'}

    print(f"\n⏳ Waiting for video generation (max {max_attempts * poll_interval}s)...")

    for attempt in range(1, max_attempts + 1):
        time.sleep(poll_interval)

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"  ⚠️ Status check failed: {response.status_code}")
            continue

        data = response.json()
        task_data = data.get('data', {})

        # Determine status
        state = task_data.get('state', '').lower()
        status = task_data.get('status', '').upper()
        progress = task_data.get('progress', 0)

        # Normalize state
        if state in ['success', 'completed'] or status == 'SUCCESS':
            is_completed = True
            is_failed = False
        elif state in ['fail', 'failed'] or status == 'FAILED':
            is_completed = False
            is_failed = True
        else:
            is_completed = False
            is_failed = False

        # Progress display
        if isinstance(progress, float) and 0 <= progress <= 1:
            progress_pct = f"{progress * 100:.0f}%"
        else:
            progress_pct = f"{progress}%"

        state_display = state or status or 'processing'
        print(f"  [{attempt}/{max_attempts}] {state_display.upper()} ({progress_pct})")

        if is_completed:
            # Extract video URL
            video_url = None

            # Try resultJson (Jobs API)
            result_json = task_data.get('resultJson', '')
            if result_json:
                try:
                    result = json.loads(result_json) if isinstance(result_json, str) else result_json
                    urls = result.get('resultUrls', [])
                    if urls:
                        video_url = urls[0]
                except json.JSONDecodeError:
                    pass

            # Try direct fields
            if not video_url:
                video_url = (
                    task_data.get('videoUrl') or
                    task_data.get('video_url') or
                    task_data.get('resultUrl') or
                    task_data.get('url')
                )

            # Try response field (Veo)
            if not video_url:
                response_data = task_data.get('response', {})
                video_url = response_data.get('videoUrl') or response_data.get('resultUrl')

            if not video_url:
                raise RuntimeError(f"No video URL in response: {task_data}")

            print("✅ Video generation complete!")
            return video_url

        if is_failed:
            error_msg = (
                task_data.get('failMsg') or
                task_data.get('errorMessage') or
                task_data.get('error') or
                'Unknown error'
            )
            raise RuntimeError(f"Generation failed: {error_msg}")

    raise RuntimeError(f"Task timed out after {max_attempts * poll_interval}s")


def download_video(
    video_url: str,
    output_dir: Path,
    filename: str
) -> Path:
    """Download video from URL."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine extension
    if '.mp4' in video_url.lower():
        ext = 'mp4'
    elif '.webm' in video_url.lower():
        ext = 'webm'
    else:
        ext = 'mp4'

    output_path = output_dir / f"{filename}.{ext}"

    print(f"\n⬇️ Downloading video...")
    response = requests.get(video_url, stream=True)

    if response.status_code != 200:
        raise RuntimeError(f"Download failed: {response.status_code}")

    total_size = int(response.headers.get('content-length', 0))
    downloaded = 0

    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            downloaded += len(chunk)
            if total_size:
                pct = downloaded / total_size * 100
                print(f"\r  Progress: {pct:.1f}%", end='', flush=True)

    print(f"\n💾 Saved to: {output_path}")
    return output_path


def slugify(text: str, max_length: int = 30) -> str:
    """Convert text to filesystem-safe slug."""
    import re
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    slug = re.sub(r'[-\s]+', '-', slug).strip('-')
    return slug[:max_length].rstrip('-') or 'video'


def generate_filename(model_id: str, prompt: str) -> str:
    """Generate descriptive filename."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    prompt_slug = slugify(prompt)
    return f"{model_id}_{prompt_slug}_{timestamp}"
