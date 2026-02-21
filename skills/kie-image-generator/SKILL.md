---
name: kie-image-generator
description: Generate images using Kie.ai's diverse AI models including GPT-4O Image, Flux Kontext, Nano Banana, Seedream, Imagen, and Ideogram. This skill should be used when the user requests AI-generated images, creative visuals, artwork creation, or image generation with specific styles. Supports 13+ models with full parameter control, automatic task polling, and usage tracking.
---

# Kie Image Generator

## Overview

Generate high-quality AI images using Kie.ai's comprehensive collection of image generation models. This skill provides access to 13+ state-of-the-art models including GPT-4O Image, Flux Kontext Pro/Max, Nano Banana, Nano Banana Pro (DeepSeed), Seedream 4.0, Imagen 4 variants, Ideogram V3, and Ideogram Character.

**Key Features:**
- 13+ AI image models with diverse capabilities
- Credit/cost tracking and usage reporting
- Interactive model selection with cost comparison
- Automatic task polling and download

## Quick Start

**Check account credits:**
```bash
python scripts/generate_image.py --credits
```

**List available models with pricing:**
```bash
python scripts/generate_image.py --list-models
```

**Interactive mode (select model with cost display):**
```bash
python scripts/generate_image.py "a beautiful sunset over mountains"
```

**Direct model selection:**
```bash
python scripts/generate_image.py "cyberpunk city" --model flux-kontext-pro
```

**Skip confirmation:**
```bash
python scripts/generate_image.py "abstract art" --model seedream-v4 -y
```

## Supported Models

### 1. GPT-4O Image (gpt4o-image)
- **Best for:** Text rendering, complex scenes, photorealistic images
- **Parameters:** `prompt`, `size` (1:1, 3:2, 2:3), `nVariants` (1-4)
- **Speed:** Medium (~20-30s)

### 2. Flux Kontext Pro (flux-kontext-pro)
- **Best for:** Fast creative generation, artistic styles
- **Parameters:** `prompt`, `image_ratio` (16:9, 21:9, 4:3, 1:1, 3:4, 9:16), `output_format` (jpeg, png)
- **Speed:** Fast (8x faster than GPT-Image)

### 3. Flux Kontext Max (flux-kontext-max)
- **Best for:** High precision, typography, consistency
- **Parameters:** Same as Flux Kontext Pro
- **Speed:** Medium

### 4. Nano Banana (nano-banana)
- **Best for:** Hyper-realistic, physics-aware visuals
- **Parameters:** `prompt`, `output_format` (PNG, JPEG), `image_size` (1:1, 9:16, 16:9, 3:4, 4:3, etc.)
- **Speed:** Fast (~10-20s)

### 5. Nano Banana Pro (nano-banana-pro) ✨ NEW
- **Best for:** 3K/4K images, text rendering, character consistency
- **Parameters:** `prompt`, `aspect_ratio` (1:1, 3:2, 16:9, etc.), `resolution` (sd, hd, 4k), `format` (jpg, png, webp), `image_input` (reference images)
- **Speed:** Fast
- **Pricing:** $0.04 (768px) / $0.11 (1024px)

### 6. Seedream 4.0 (seedream-v4)
- **Best for:** Fast generation, 2K-4K resolution
- **Parameters:** `prompt`, `image_size`, `image_resolution` (1K, 2K, 4K), `max_images` (1-6), `seed`
- **Speed:** Very fast (~1.8s for 2K)

### 7. Imagen 4 Ultra (imagen-4-ultra)
- **Best for:** Photorealistic, high-quality visuals
- **Parameters:** `prompt`, `negative_prompt`, `aspect_ratio` (1:1, 16:9, 9:16, 3:4, 4:3), `num_images` (1-4), `seed`
- **Speed:** Very fast (10x faster)

### 8. Imagen 4 (imagen-4)
- **Best for:** Balanced quality and speed
- **Parameters:** Same as Imagen 4 Ultra
- **Speed:** Fast

### 9. Imagen 4 Fast (imagen-4-fast)
- **Best for:** Quick iterations, drafts
- **Parameters:** Same as Imagen 4 Ultra
- **Speed:** Very fast

### 10. Ideogram V3 (ideogram-v3)
- **Best for:** Text rendering, typography
- **Parameters:** `prompt`, `rendering_speed` (TURBO, BALANCED, QUALITY), `style` (AUTO, GENERAL, REALISTIC, DESIGN), `image_size`, `num_images` (1-4), `expand_prompt`, `seed`, `negative_prompt`
- **Speed:** Variable (depends on rendering_speed)

### 11. Ideogram Character (ideogram-character)
- **Best for:** Character consistency, portraits
- **Parameters:** `prompt`, `reference_image_urls`, `rendering_speed`, `style` (AUTO, REALISTIC, FICTION), `num_images` (1-4), `expand_prompt`, `seed`
- **Speed:** Variable

## Workflow

### Step 1: Environment Setup

Ensure `.env` file exists in the skill directory with Kie.ai API key:
```bash
KIEAI_API_KEY=your_api_key_here
```

If `.env` doesn't exist, the script will create it from `.env.example` and prompt for API key.

### Step 2: Generate Image

Run the generation script with desired parameters:

```bash
# Basic generation
python scripts/generate_image.py "prompt"

# With model selection
python scripts/generate_image.py "prompt" --model MODEL_ID

# With advanced parameters
python scripts/generate_image.py "prompt" \
  --model gpt4o-image \
  --size "3:2" \
  --variants 2 \
  --output ~/Downloads/images/
```

### Step 3: Task Polling

The script automatically:
1. Submits generation task to Kie.ai
2. Polls for completion (every 2 seconds)
3. Downloads completed image
4. Saves to output directory with timestamped filename

## Advanced Usage

### Model-Specific Parameters

Each model has a dedicated module in `scripts/models/` with full parameter support:

**GPT-4O Image:**
```bash
python scripts/generate_image.py "sunset" \
  --model gpt4o-image \
  --size "16:9" \
  --variants 4
```

**Flux Kontext:**
```bash
python scripts/generate_image.py "abstract art" \
  --model flux-kontext-pro \
  --ratio "21:9" \
  --format jpeg
```

**Nano Banana Pro:**
```bash
python scripts/generate_image.py "cinematic poster cool banana hero" \
  --model nano-banana-pro \
  --aspect-ratio "16:9" \
  --resolution 4k \
  --format png
```

**Seedream 4.0:**
```bash
python scripts/generate_image.py "landscape" \
  --model seedream-v4 \
  --resolution 4K \
  --images 4 \
  --seed 12345
```

**Imagen 4:**
```bash
python scripts/generate_image.py "portrait" \
  --model imagen-4-ultra \
  --aspect-ratio "3:4" \
  --negative "blurry, low quality" \
  --seed 67890
```

**Ideogram V3:**
```bash
python scripts/generate_image.py "logo design" \
  --model ideogram-v3 \
  --rendering QUALITY \
  --style DESIGN \
  --expand-prompt
```

### Batch Generation

Generate multiple variations:
```bash
# 4 variants of same prompt
python scripts/generate_image.py "cyberpunk city" --variants 4

# Multiple prompts
for prompt in "sunset" "moonrise" "starfield"; do
  python scripts/generate_image.py "$prompt" --model imagen-4-fast
done
```

## Resources

### scripts/
- `generate_image.py` - Main generation script with CLI interface
- `models/` - Model-specific parameter handlers
  - `gpt4o.py` - GPT-4O Image parameters
  - `flux_kontext.py` - Flux Kontext Pro/Max parameters
  - `nano_banana.py` - Nano Banana parameters
  - `seedream.py` - Seedream 4.0 parameters
  - `imagen.py` - Imagen 4 variants parameters
  - `ideogram.py` - Ideogram V3/Character parameters
- `utils.py` - Common utilities (polling, download, env loading)

### references/
- `api_docs.md` - Comprehensive Kie.ai API documentation

## Error Handling

The script handles common errors:
- **Missing API key:** Prompts to create .env file
- **Invalid model:** Lists available models
- **Generation timeout:** Retries or reports timeout (max 2 minutes)
- **API errors:** Displays error message and suggests solutions

## Output Format

Generated images are saved with descriptive filenames:
```
~/Downloads/images/gpt4o-image_sunset_20250113_203045.png
~/Downloads/images/flux-kontext-pro_cyberpunk_20250113_203125.jpg
```

Format: `{model}_{prompt-slug}_{timestamp}.{ext}`

## Credit System

Kie.ai uses a credit-based pricing system:
- **1 credit = $0.005 USD**
- Credits are deducted upon task completion
- Use `--credits` to check current balance

### Estimated Credit Costs

| Model | Est. Credits | Est. USD |
|-------|-------------|----------|
| Nano Banana | ~20 | $0.10 |
| Imagen 4 Fast | ~25 | $0.12 |
| Nano Banana Edit | ~25 | $0.12 |
| Flux Kontext Pro | ~30 | $0.15 |
| Seedream V4 | ~35 | $0.18 |
| Nano Banana Pro | ~40 | $0.20 |
| Ideogram V3 | ~40 | $0.20 |
| Seedream V4 Edit | ~40 | $0.20 |
| Ideogram Character | ~45 | $0.23 |
| GPT-4O Image | ~50 | $0.25 |
| Imagen 4 | ~50 | $0.25 |
| Flux Kontext Max | ~60 | $0.30 |
| Imagen 4 Ultra | ~100 | $0.50 |

*Prices are estimates and may vary based on parameters.*

## Usage Tracking

After each generation, the script reports:
```
💰 Credits used: 45.0 ($0.23)
   Remaining: 837.5 credits ($4.19)
```

This helps track spending and plan budget for generation tasks
