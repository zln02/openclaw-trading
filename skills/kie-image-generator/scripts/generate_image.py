#!/usr/bin/env python3
"""
Kie.ai Image Generation CLI

Generate images using Kie.ai's diverse AI models.
"""

import sys
import argparse
from pathlib import Path
from typing import Dict, Any

# Add parent directory to path for imports
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
    download_image,
    generate_filename,
    MODELS,
    CREDIT_TO_USD,
    GENERATION_ENDPOINTS,
    RECORD_INFO_ENDPOINTS,
    JOBS_API_MODELS
)
from models import (
    build_gpt4o_payload,
    build_flux_payload,
    build_nano_payload,
    build_nano_pro_payload,
    build_seedream_payload,
    build_imagen_payload,
    build_ideogram_payload
)
from models.seedream_edit import build_seedream_edit_payload
from models.nano_banana_edit import build_nano_edit_payload


AVAILABLE_MODELS = list(GENERATION_ENDPOINTS.keys())

MODEL_PAYLOAD_BUILDERS = {
    'gpt4o-image': build_gpt4o_payload,
    'flux-kontext-pro': build_flux_payload,
    'flux-kontext-max': build_flux_payload,
    'nano-banana': build_nano_payload,
    'nano-banana-pro': build_nano_pro_payload,
    'nano-banana-edit': build_nano_edit_payload,
    'seedream-v4': build_seedream_payload,
    'seedream-v4-edit': build_seedream_edit_payload,
    'imagen-4-ultra': build_imagen_payload,
    'imagen-4': build_imagen_payload,
    'imagen-4-fast': build_imagen_payload,
    'ideogram-v3': lambda prompt, **kw: build_ideogram_payload(prompt, 'ideogram-v3', **kw),
    'ideogram-character': lambda prompt, **kw: build_ideogram_payload(prompt, 'ideogram-character', **kw),
}


def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description='Generate images using Kie.ai models',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --credits                             # Check available credits
  %(prog)s --list-models                         # List all models with pricing
  %(prog)s "a beautiful sunset"                  # Interactive model selection
  %(prog)s "cyberpunk city" --model flux-kontext-pro
  %(prog)s "abstract art" --model seedream-v4 --resolution 4K
  %(prog)s "portrait" --model imagen-4-ultra --aspect-ratio 3:4
        """
    )

    # Positional argument (optional for info commands)
    parser.add_argument(
        'prompt',
        nargs='?',
        help='Image generation prompt'
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
        choices=AVAILABLE_MODELS,
        help='Model to use (interactive selection if not specified)'
    )

    # Skip confirmation
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompts'
    )

    # No download
    parser.add_argument(
        '--no-download',
        action='store_true',
        help='Skip image download (print URL only)'
    )

    parser.add_argument(
        '--output', '-o',
        type=Path,
        default=Path.home() / 'Downloads' / 'images',
        help='Output directory (default: ~/Downloads/images/)'
    )

    # Common parameters
    parser.add_argument('--size', help='Image size/aspect ratio')
    parser.add_argument('--ratio', help='Image ratio (Flux models)')
    parser.add_argument('--format', help='Output format')
    parser.add_argument('--resolution', help='Image resolution (Seedream)')
    parser.add_argument('--aspect-ratio', help='Aspect ratio (Imagen)')
    parser.add_argument('--rendering', help='Rendering speed (Ideogram)')
    parser.add_argument('--style', help='Style preset (Ideogram)')
    parser.add_argument('--variants', type=int, help='Number of variants (GPT-4O)')
    parser.add_argument('--images', type=int, help='Number of images')
    parser.add_argument('--num-images', type=int, help='Number of images (alias)')
    parser.add_argument('--seed', type=int, help='Random seed')
    parser.add_argument('--negative', help='Negative prompt')
    parser.add_argument('--negative-prompt', help='Negative prompt (alias)')
    parser.add_argument('--expand-prompt', action='store_true', help='Enable prompt enhancement')
    parser.add_argument('--reference', help='Reference image URL (Ideogram Character)')
    parser.add_argument('--reference-images', help='Reference image URLs (Ideogram Character)')

    return parser.parse_args()


def main():
    """Main execution function"""
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

        print("🎨 Kie.ai Image Generator")
        print(f"Prompt: {args.prompt}\n")

        # Get current credits
        credits, usd = get_credits(api_key)
        print(f"💰 Current Balance: {credits:,.1f} credits (${usd:.2f})")

        # Model selection
        has_image = bool(args.reference or args.reference_images)

        if args.model:
            model_id = args.model
            # Validate image requirement
            model = MODELS.get(model_id)
            if model and model.get('type') == 'image-to-image' and not has_image:
                print(f"\n⚠️  Model '{model_id}' requires an image input.")
                print("   Use --reference <url> to provide an image.")
                return 1
        else:
            # Interactive selection
            model_id = select_model_interactive(has_image)
            if not model_id:
                print("\n👋 Generation cancelled.")
                return 0

        # Confirm generation
        if not args.yes:
            if not confirm_generation(model_id, credits):
                print("\n👋 Generation cancelled.")
                return 0

        print(f"\nModel: {MODELS.get(model_id, {}).get('name', model_id)}")

        # Get endpoints for model
        generation_endpoint = GENERATION_ENDPOINTS.get(model_id)
        record_info_endpoint = RECORD_INFO_ENDPOINTS.get(model_id)

        if not generation_endpoint or not record_info_endpoint:
            raise ValueError(f"Unsupported model: {model_id}")

        # Build payload using model-specific builder
        payload_builder = MODEL_PAYLOAD_BUILDERS.get(model_id)
        if not payload_builder:
            raise ValueError(f"No payload builder for model: {model_id}")

        # Collect model parameters from args
        params = {}
        for param in ['size', 'ratio', 'format', 'resolution', 'aspect_ratio',
                      'rendering', 'style', 'variants', 'images', 'num_images',
                      'seed', 'negative', 'negative_prompt', 'expand_prompt',
                      'reference', 'reference_images']:
            value = getattr(args, param.replace('-', '_'), None)
            if value is not None:
                params[param.replace('-', '_')] = value

        # Map reference_images to image_urls for seedream-edit
        if 'reference_images' in params:
            params['image_urls'] = params['reference_images']

        # Build payload
        payload = payload_builder(args.prompt, **params)
        print(f"\n📋 Payload: {payload}\n")

        # Submit task (use Jobs API for certain models)
        jobs_model_id = JOBS_API_MODELS.get(model_id)
        task_id = submit_task(api_key, generation_endpoint, payload, model_id=jobs_model_id)

        # Poll for completion
        image_url = poll_task(
            api_key,
            record_info_endpoint,
            task_id,
            max_attempts=60,
            poll_interval=2
        )

        print(f"\n🖼️  Image URL: {image_url}")

        # Download image
        if not args.no_download:
            # Determine output file extension
            if 'jpeg' in image_url.lower() or payload.get('output_format', '').lower() == 'jpeg':
                extension = 'jpg'
            else:
                extension = 'png'

            # Generate filename
            filename = generate_filename(model_id, args.prompt, extension)

            # Download image
            output_path = download_image(image_url, args.output, filename)
            print(f"\n✨ Success! Image saved to: {output_path}")
        else:
            print("\n✨ Image generated successfully!")

        # Report updated credits
        new_credits, new_usd = get_credits(api_key)
        used = credits - new_credits
        print(f"\n💰 Credits used: {used:,.1f} (${used * CREDIT_TO_USD:.2f})")
        print(f"   Remaining: {new_credits:,.1f} credits (${new_usd:.2f})")

        return 0

    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
        return 130

    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
