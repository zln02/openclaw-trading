---
name: kie-video-generator
description: Generate AI videos using Kie.ai's diverse video generation models including Veo 3, Sora 2, Kling, Wan, Hailuo, Seedance, and more. Supports text-to-video, image-to-video, and video extension with automatic usage tracking and model comparison.
---

# Kie Video Generator

## Overview

Generate high-quality AI videos using Kie.ai's comprehensive collection of video generation models. This skill provides access to 15+ state-of-the-art models including Google Veo 3/3.1, OpenAI Sora 2, Kling 2.5/2.6, Wan 2.2/2.5/2.6, Hailuo, ByteDance Seedance, and more.

**Features:**
- Text-to-video and image-to-video generation
- Automatic credit usage tracking and reporting
- Model cost comparison before generation
- Interactive model selection
- Video extension capabilities

## Quick Start

```bash
# Check available credits
python scripts/generate_video.py --credits

# List all available models with pricing
python scripts/generate_video.py --list-models

# Generate video with interactive model selection
python scripts/generate_video.py "a serene sunset over the ocean"

# Generate with specific model
python scripts/generate_video.py "cyberpunk city at night" --model veo3

# Image-to-video generation
python scripts/generate_video.py "make this image come alive" --model kling-2.6-i2v --image https://example.com/image.jpg
```

## Supported Models

### Google Veo 3 / 3.1
| Model ID | Type | Duration | Resolution | Est. Cost |
|----------|------|----------|------------|-----------|
| `veo3` | Text/Image to Video | 8s | 1080P | $2.00 |
| `veo3-fast` | Text/Image to Video | 8s | 1080P | $0.40 |

**Parameters:** `prompt`, `imageUrls` (1-2), `aspectRatio` (16:9, 9:16, Auto), `seeds`, `enableTranslation`, `watermark`

### OpenAI Sora 2
| Model ID | Type | Frames | Resolution | Est. Cost |
|----------|------|--------|------------|-----------|
| `sora-2-t2v` | Text to Video | 10/15 | landscape/portrait | ~$1.00 |
| `sora-2-pro-t2v` | Pro Text to Video | 10/15 | landscape/portrait | ~$2.00 |
| `sora-2-i2v` | Image to Video | - | - | ~$1.50 |
| `sora-2-watermark-remover` | Remove Watermark | - | - | ~$0.50 |

**Parameters:** `prompt`, `aspect_ratio`, `n_frames`, `remove_watermark`, `character_id_list`

### Kling 2.5 / 2.6
| Model ID | Type | Duration | Resolution | Est. Cost |
|----------|------|----------|------------|-----------|
| `kling-2.6-t2v` | Text to Video | 5/10s | 1:1, 16:9, 9:16 | ~$0.50 |
| `kling-2.6-i2v` | Image to Video | 5/10s | - | ~$0.60 |
| `kling-2.5-t2v` | Text to Video | 5/10s | - | ~$0.40 |
| `kling-2.1-master` | Master Text to Video | - | - | ~$0.80 |

**Parameters:** `prompt`, `image_urls`, `sound`, `aspect_ratio`, `duration`

### Wan 2.2 / 2.5 / 2.6
| Model ID | Type | Duration | Resolution | Est. Cost |
|----------|------|----------|------------|-----------|
| `wan-2.6-t2v` | Text to Video | 5/10/15s | 720p/1080p | ~$0.30 |
| `wan-2.5-t2v` | Text to Video | - | - | ~$0.25 |
| `wan-2.2-t2v` | Text to Video | - | - | ~$0.20 |
| `wan-2.2-animate` | Animate | - | - | ~$0.30 |

**Parameters:** `prompt`, `duration`, `resolution`

### Hailuo 2.3
| Model ID | Type | Duration | Resolution | Est. Cost |
|----------|------|----------|------------|-----------|
| `hailuo-2.3-i2v-standard` | Image to Video (Standard) | 6/10s | 512P/768P | ~$0.30 |
| `hailuo-2.3-i2v-pro` | Image to Video (Pro) | 6/10s | 512P/768P | ~$0.50 |
| `hailuo-2.3-t2v-standard` | Text to Video (Standard) | - | - | ~$0.30 |

**Parameters:** `prompt`, `image_url`, `end_image_url`, `duration`, `resolution`, `prompt_optimizer`

### ByteDance Seedance 1.5
| Model ID | Type | Duration | Resolution | Est. Cost |
|----------|------|----------|------------|-----------|
| `seedance-1.5-pro` | Pro Video | 4/8/12s | 480p/720p | ~$0.40 |
| `seedance-v1-pro-t2v` | Pro Text to Video | - | - | ~$0.35 |
| `seedance-v1-lite-i2v` | Lite Image to Video | - | - | ~$0.20 |
| `seedance-v1-pro-i2v` | Pro Image to Video | - | - | ~$0.40 |
| `seedance-v1-pro-fast-i2v` | Pro Fast Image to Video | - | - | ~$0.30 |

**Parameters:** `prompt`, `input_urls`, `aspect_ratio`, `resolution`, `duration`, `fixed_lens`, `generate_audio`

### Grok Imagine
| Model ID | Type | Est. Cost |
|----------|------|-----------|
| `grok-imagine` | Text/Image to Video | ~$0.50 |

## Workflow

### Step 1: Check Credits

Always check your available credits before generating:

```bash
python scripts/generate_video.py --credits
```

Output:
```
💰 Kie.ai Account Balance
━━━━━━━━━━━━━━━━━━━━━━━━
Available Credits: 1,250
Estimated Value: $6.25 USD
```

### Step 2: Compare Models

View all available models with estimated costs:

```bash
python scripts/generate_video.py --list-models
```

### Step 3: Generate Video

**Interactive mode (recommended for first-time users):**
```bash
python scripts/generate_video.py "your prompt here"
```

The script will:
1. Display your current credits
2. Show available models with costs
3. Ask you to select a model
4. Confirm before generating
5. Poll for completion and download

**Direct mode (when you know the model):**
```bash
python scripts/generate_video.py "your prompt" --model veo3-fast
```

### Step 4: Image-to-Video

For models that support image input:

```bash
# Single image
python scripts/generate_video.py "animate this scene" \
  --model kling-2.6-i2v \
  --image https://example.com/image.jpg

# First and last frame (Veo 3, Hailuo)
python scripts/generate_video.py "transition between scenes" \
  --model veo3 \
  --image https://example.com/start.jpg \
  --end-image https://example.com/end.jpg
```

## Advanced Usage

### Model-Specific Parameters

**Veo 3:**
```bash
python scripts/generate_video.py "cinematic landscape" \
  --model veo3 \
  --aspect-ratio 16:9 \
  --seed 12345
```

**Kling 2.6:**
```bash
python scripts/generate_video.py "dancing robot" \
  --model kling-2.6-t2v \
  --duration 10 \
  --sound
```

**Wan 2.6:**
```bash
python scripts/generate_video.py "flowing water" \
  --model wan-2.6-t2v \
  --duration 15 \
  --resolution 1080p
```

**Seedance:**
```bash
python scripts/generate_video.py "product showcase" \
  --model seedance-1.5-pro \
  --duration 8 \
  --aspect-ratio 16:9 \
  --generate-audio
```

### Output Options

```bash
# Custom output directory
python scripts/generate_video.py "prompt" --output ~/Videos/ai/

# Custom filename
python scripts/generate_video.py "prompt" --filename my_video
```

## Environment Setup

Create `.env` file in the skill directory:

```bash
KIE_AI_API_KEY=your_api_key_here
```

Or use the centralized auth:
```bash
source ~/.claude/auth/kie-ai.env
```

## Cost Estimation

Before each generation, the script shows estimated cost:

```
📊 Cost Estimate
━━━━━━━━━━━━━━━━━━━━━━━━
Model: veo3-fast
Estimated Cost: ~80 credits ($0.40)
Current Balance: 1,250 credits ($6.25)
After Generation: ~1,170 credits ($5.85)

Proceed with generation? [y/N]:
```

## Error Handling

Common error codes:
- **401**: Invalid API key
- **402**: Insufficient credits
- **422**: Invalid parameters
- **429**: Rate limited (wait and retry)
- **501**: Generation failed (try different prompt/model)

## Resources

### scripts/
- `generate_video.py` - Main CLI with interactive model selection
- `utils.py` - API utilities, polling, credit checking
- `models/` - Model-specific parameter handlers

### references/
- `api_docs.md` - Complete API documentation
- `models.md` - Detailed model specifications
