#!/usr/bin/env python3
"""
Kie.ai Video Generation CLI

Generate videos using Kie.ai's diverse AI models with automatic
credit tracking and interactive model selection.
"""

import sys
import argparse
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from utils import (
    load_api_key,
    get_credits,
    print_credits,
    print_models,
    select_model_interactive,
    confirm_generation,
    submit_task,
    poll_task,
    download_video,
    generate_filename,
    MODELS,
    CREDIT_TO_USD
)


def build_payload(args, model_id: str) -> Dict[str, Any]:
    """Build request payload based on model and arguments."""
    model = MODELS.get(model_id)
    if not model:
        raise ValueError(f"Unknown model: {model_id}")

    payload = {'prompt': args.prompt}

    # Veo 3 specific
    if model_id in ['veo3', 'veo3-fast']:
        if args.image:
            payload['imageUrls'] = [args.image]
            if args.end_image:
                payload['imageUrls'].append(args.end_image)
                payload['generationType'] = 'FIRST_AND_LAST_FRAMES_2_VIDEO'
            else:
                payload['generationType'] = 'REFERENCE_2_VIDEO'
        else:
            payload['generationType'] = 'TEXT_2_VIDEO'

        if args.aspect_ratio:
            payload['aspectRatio'] = args.aspect_ratio
        if args.seed:
            payload['seeds'] = args.seed

    # Sora 2 specific
    elif 'sora-2' in model_id:
        if args.aspect_ratio:
            ar_map = {'16:9': 'landscape', '9:16': 'portrait'}
            payload['aspect_ratio'] = ar_map.get(args.aspect_ratio, args.aspect_ratio)
        if args.frames:
            payload['n_frames'] = str(args.frames)
        if args.remove_watermark:
            payload['remove_watermark'] = True

    # Kling specific
    elif 'kling' in model_id:
        if args.image:
            payload['image_urls'] = [args.image]
        if args.duration:
            payload['duration'] = str(args.duration)
        # aspect_ratio is required for Kling
        payload['aspect_ratio'] = args.aspect_ratio or '16:9'
        if args.sound:
            payload['sound'] = True
        else:
            payload['sound'] = False

    # Wan specific
    elif 'wan' in model_id:
        if args.image:
            payload['image_url'] = args.image
        if args.duration:
            payload['duration'] = str(args.duration)
        if args.resolution:
            payload['resolution'] = args.resolution

    # Hailuo specific
    elif 'hailuo' in model_id:
        if args.image:
            payload['image_url'] = args.image
        if args.end_image:
            payload['end_image_url'] = args.end_image
        if args.duration:
            payload['duration'] = str(args.duration)
        if args.resolution:
            res_map = {'512p': '512P', '768p': '768P'}
            payload['resolution'] = res_map.get(args.resolution.lower(), args.resolution)
        if args.prompt_optimizer:
            payload['prompt_optimizer'] = True

    # Seedance specific
    elif 'seedance' in model_id:
        if args.image:
            # Seedance 1.5 Pro uses input_urls, V1 series uses image_url
            if '1.5' in model_id or 'seedance-1' in model_id:
                payload['input_urls'] = [args.image]
            else:
                payload['image_url'] = args.image
        if args.duration:
            payload['duration'] = str(args.duration)
        if args.aspect_ratio:
            payload['aspect_ratio'] = args.aspect_ratio
        if args.resolution:
            payload['resolution'] = args.resolution
        if args.fixed_lens:
            payload['fixed_lens'] = True
        if args.generate_audio:
            payload['generate_audio'] = True

    # Grok specific
    elif 'grok' in model_id:
        if args.image:
            payload['image_urls'] = [args.image]
        # mode: fun, normal, spicy (default: normal)
        payload['mode'] = 'normal'

    return payload


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Generate videos using Kie.ai models',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --credits                           # Check available credits
  %(prog)s --list-models                       # List all models with pricing
  %(prog)s "a sunset over the ocean"           # Interactive model selection
  %(prog)s "cyberpunk city" --model veo3-fast  # Direct model selection
  %(prog)s "animate this" --model kling-2.6-i2v --image https://example.com/img.jpg
        """
    )

    # Positional
    parser.add_argument(
        'prompt',
        nargs='?',
        help='Text prompt for video generation'
    )

    # Info commands
    parser.add_argument(
        '--credits', '-c',
        action='store_true',
        help='Show current account credits'
    )
    parser.add_argument(
        '--list-models', '-l',
        action='store_true',
        help='List all available models with pricing'
    )

    # Model selection
    parser.add_argument(
        '--model', '-m',
        choices=list(MODELS.keys()),
        help='Model to use (interactive selection if not specified)'
    )

    # Image inputs
    parser.add_argument(
        '--image', '-i',
        help='Input image URL for image-to-video models'
    )
    parser.add_argument(
        '--end-image',
        help='End frame image URL (for transition videos)'
    )

    # Common parameters
    parser.add_argument(
        '--aspect-ratio', '-ar',
        help='Aspect ratio (e.g., 16:9, 9:16, 1:1)'
    )
    parser.add_argument(
        '--duration', '-d',
        type=int,
        help='Video duration in seconds'
    )
    parser.add_argument(
        '--resolution', '-r',
        help='Output resolution (e.g., 720p, 1080p)'
    )
    parser.add_argument(
        '--seed',
        type=int,
        help='Random seed for reproducibility'
    )

    # Model-specific options
    parser.add_argument(
        '--sound',
        action='store_true',
        help='Include sound (Kling models)'
    )
    parser.add_argument(
        '--frames',
        type=int,
        choices=[10, 15],
        help='Number of frames (Sora 2)'
    )
    parser.add_argument(
        '--remove-watermark',
        action='store_true',
        help='Remove watermark (Sora 2)'
    )
    parser.add_argument(
        '--fixed-lens',
        action='store_true',
        help='Fixed camera lens (Seedance)'
    )
    parser.add_argument(
        '--generate-audio',
        action='store_true',
        help='Generate audio (Seedance)'
    )
    parser.add_argument(
        '--prompt-optimizer',
        action='store_true',
        help='Use prompt optimizer (Hailuo)'
    )

    # Output options
    parser.add_argument(
        '--output', '-o',
        type=Path,
        default=Path.home() / 'Downloads' / 'videos',
        help='Output directory (default: ~/Downloads/videos/)'
    )
    parser.add_argument(
        '--filename', '-f',
        help='Output filename (without extension)'
    )

    # Flags
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompts'
    )
    parser.add_argument(
        '--no-download',
        action='store_true',
        help='Skip video download (print URL only)'
    )

    return parser.parse_args()


def main():
    """Main execution function."""
    args = parse_arguments()

    try:
        # Load API key
        api_key = load_api_key()

        # Handle info commands
        if args.credits:
            print_credits(api_key)
            return 0

        if args.list_models:
            print_models()
            return 0

        # Require prompt for generation
        if not args.prompt:
            print("❌ Error: Please provide a prompt or use --credits / --list-models")
            print("   Run with --help for usage information")
            return 1

        print("🎬 Kie.ai Video Generator")
        print(f"Prompt: {args.prompt}\n")

        # Get current credits
        credits, usd = get_credits(api_key)
        print(f"💰 Current Balance: {credits:,} credits (${usd:.2f})")

        # Model selection
        has_image = bool(args.image)

        if args.model:
            model_id = args.model
            # Validate image requirement
            model = MODELS[model_id]
            if model['type'] == 'image-to-video' and not has_image:
                print(f"\n⚠️  Model '{model_id}' requires an image input.")
                print("   Use --image <url> to provide an image.")
                return 1
        else:
            # Interactive selection
            model_id = select_model_interactive(args.prompt, has_image)
            if not model_id:
                print("\n👋 Generation cancelled.")
                return 0

        # Confirm generation
        if not args.yes:
            if not confirm_generation(model_id, credits):
                print("\n👋 Generation cancelled.")
                return 0

        # Build payload
        payload = build_payload(args, model_id)
        print(f"\n📋 Request payload: {payload}")

        # Submit task
        task_id = submit_task(api_key, model_id, payload)

        # Poll for completion
        video_url = poll_task(api_key, model_id, task_id)

        print(f"\n🎥 Video URL: {video_url}")

        # Download video
        if not args.no_download:
            filename = args.filename or generate_filename(model_id, args.prompt)
            output_path = download_video(video_url, args.output, filename)
            print(f"\n✨ Success! Video saved to: {output_path}")
        else:
            print("\n✨ Video generated successfully!")

        # Report updated credits
        new_credits, new_usd = get_credits(api_key)
        used = credits - new_credits
        print(f"\n💰 Credits used: {used} (${used * CREDIT_TO_USD:.2f})")
        print(f"   Remaining: {new_credits:,} credits (${new_usd:.2f})")

        return 0

    except KeyboardInterrupt:
        print("\n\n⚠️ Operation cancelled by user")
        return 130

    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
