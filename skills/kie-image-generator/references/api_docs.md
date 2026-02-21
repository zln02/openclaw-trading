# Kie.ai API Documentation Reference

Comprehensive reference for all Kie.ai image generation models.

## Base URL
```
https://api.kie.ai
```

## Authentication
All requests require `X-API-KEY` header:
```
X-API-KEY: your_api_key_here
```

## Workflow
1. **Submit Task**: POST to generation endpoint → receive `taskId`
2. **Poll Status**: GET record-info endpoint with `taskId` → wait for completion
3. **Download**: Extract image URL from completed response

## Response Format
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "taskId": "...",          // On task submission
    "status": "completed",    // On polling
    "imageUrl": "...",        // When completed
    "progress": 0-100         // During processing
  }
}
```

---

## GPT-4O Image

**Generation**: `POST /api/v1/gpt4o-image/generate`
**Record Info**: `GET /api/v1/gpt4o-image/record-info?taskId={taskId}`

**Parameters**:
```json
{
  "prompt": "string (required)",
  "size": "1:1 | 3:2 | 2:3 (default: 1:1)",
  "variants": "1-4 (default: 1)"
}
```

**Best For**: High-quality, creative images with OpenAI's DALL-E technology

---

## Flux Kontext Pro / Max

**Generation**: `POST /api/v1/flux/kontext/generate`
**Record Info**: `GET /api/v1/flux/kontext/record-info?taskId={taskId}`

**Parameters**:
```json
{
  "prompt": "string (required)",
  "ratio": "16:9 | 9:16 | 21:9 | 3:4 | 4:3 | 5:4 | 4:5 (default: 16:9)",
  "output_format": "jpeg | png (default: png)",
  "model": "flux-kontext-pro | flux-kontext-max"
}
```

**Best For**:
- **Pro**: Fast, professional results for general use
- **Max**: Maximum quality for detailed scenes

---

## Nano Banana (Gemini 2.5 Flash) - v1 API

**Generation**: `POST /api/v1/jobs/createTask` (model: `google/nano-banana`)
**Record Info**: `GET /api/v1/jobs/recordInfo?taskId={taskId}`

**Parameters**:
```json
{
  "prompt": "string (required)",
  "output_format": "png | jpeg (default: png)",
  "image_size": "1:1 | 9:16 | 16:9 | 3:4 | 4:3 | 3:2 | 2:3 | 5:4 | 4:5 | 21:9 | auto (default: 1:1)"
}
```

**Best For**: Google Gemini-powered fast generation with various aspect ratios

---

## Nano Banana Pro (DeepSeed) - v2 API

**Generation**: `POST /api/v2/jobs/createTask` (model: `nano-banana-pro`)
**Record Info**: `GET /api/v1/jobs/recordInfo?taskId={taskId}`

**Description**: DeepSeed's Nano Banana Pro delivers sharper 3K images, intelligent 4K scaling, improved text rendering, and enhanced character consistency.

**Pricing**: $0.04 (768px) / $0.11 (1024px)

**Request Body**:
```json
{
  "model": "nano-banana-pro",
  "callbackUrl": "string (optional)",
  "input": {
    "input_prompt": "string (required)",
    "input_image_input": ["url1", "url2"] (optional, max 4 reference images),
    "input_aspect_ratio": "1:1 | 3:2 | 2:3 | 4:3 | 3:4 | 16:9 | 9:16 | 21:9 | 9:21 (default: 1:1)",
    "input_resolution": "sd | hd | 4k (default: hd)",
    "input_output_format": "jpg | png | webp (default: webp)"
  }
}
```

**Parameters**:
| Parameter | Required | Description |
|-----------|----------|-------------|
| input_prompt | Yes | Image description |
| input_image_input | No | Reference image URLs (up to 4 images, PNG/JPEG/GIF/WebP, max 10MB) |
| input_aspect_ratio | No | Output aspect ratio |
| input_resolution | No | Output resolution (sd/hd/4k) |
| input_output_format | No | Output format (jpg/png/webp) |

**Request Example**:
```bash
curl -X POST "https://api.kie.ai/api/v2/jobs/createTask" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "nano-banana-pro",
    "input": {
      "input_prompt": "cinematic poster cool banana hero in shades leaps from sci-fi pod",
      "input_resolution": "hd",
      "input_output_format": "png"
    }
  }'
```

**Response Example**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "task_id": "task_xxxxxxx"
  }
}
```

**Query Task Response**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "taskId": "task_12345678",
    "model": "nano-banana-pro",
    "state": "success",
    "resultJson": "{\"resultUrls\":[\"https://example.com/generated-image.jpg\"]}",
    "failCode": "",
    "failMsg": "",
    "costTime": 0,
    "completeTime": 1698765432000,
    "createTime": 1698765400000
  }
}
```

**State Values**:
| State | Description |
|-------|-------------|
| waiting | Waiting for generation |
| queuing | In queue |
| generating | Generating |
| success | Generation successful |
| fail | Generation failed |

**Best For**: High-quality 3K/4K images with improved text rendering and character consistency

---

## Seedream 4.0

**Generation**: `POST /api/v1/bytedance/seedream-v4-text-to-image`
**Record Info**: `GET /api/v1/bytedance/seedream-v4-text-to-image/record-info?taskId={taskId}`

**Parameters**:
```json
{
  "prompt": "string (required, max 5000 chars)",
  "image_size": "string (aspect ratio)",
  "image_resolution": "1K | 2K | 4K (default: 2K)",
  "max_images": "1-6 (default: 1)",
  "seed": "integer (optional, for reproducibility)"
}
```

**Best For**: High-resolution images with fine control, ByteDance technology

---

## Imagen 4 (Ultra / Standard / Fast)

**Generation**:
- `POST /api/v1/google/imagen-4-ultra`
- `POST /api/v1/google/imagen-4`
- `POST /api/v1/google/imagen-4-fast`

**Record Info**:
- `GET /api/v1/google/imagen-4-ultra/record-info?taskId={taskId}`
- `GET /api/v1/google/imagen-4/record-info?taskId={taskId}`
- `GET /api/v1/google/imagen-4-fast/record-info?taskId={taskId}`

**Parameters**:
```json
{
  "prompt": "string (required)",
  "negative_prompt": "string (optional)",
  "aspect_ratio": "1:1 | 16:9 | 9:16 | 3:4 | 4:3 (default: 1:1)",
  "num_images": "1-4 (default: 1)",
  "seed": "integer (optional)"
}
```

**Best For**:
- **Ultra**: Maximum photorealism and detail
- **Standard**: Balanced quality and speed
- **Fast**: Quick iterations with good quality

---

## Ideogram V3

**Generation**: `POST /api/v1/ideogram/v3-text-to-image`
**Record Info**: `GET /api/v1/ideogram/v3-text-to-image/record-info?taskId={taskId}`

**Parameters**:
```json
{
  "prompt": "string (required)",
  "rendering_speed": "TURBO | BALANCED | QUALITY (default: BALANCED)",
  "style": "AUTO | GENERAL | REALISTIC | DESIGN (default: AUTO)",
  "image_size": "string (aspect ratio)",
  "num_images": "1-4 (default: 1)",
  "expand_prompt": "boolean (MagicPrompt enhancement)",
  "seed": "integer (optional)",
  "negative_prompt": "string (optional)"
}
```

**Best For**: Text rendering in images, design work, versatile styles

---

## Ideogram Character

**Generation**: `POST /api/v1/ideogram/character`
**Record Info**: `GET /api/v1/ideogram/character/record-info?taskId={taskId}`

**Parameters**:
```json
{
  "prompt": "string (required)",
  "rendering_speed": "TURBO | BALANCED | QUALITY (default: BALANCED)",
  "style": "AUTO | REALISTIC | FICTION (default: AUTO)",
  "image_size": "string (aspect ratio)",
  "num_images": "1-4 (default: 1)",
  "expand_prompt": "boolean (MagicPrompt enhancement)",
  "seed": "integer (optional)",
  "negative_prompt": "string (optional)",
  "reference_image_urls": ["url1", "url2"] (optional, for character consistency)
}
```

**Best For**: Consistent character generation across multiple images

---

## Error Handling

**Common HTTP Status Codes**:
- `200`: Success
- `400`: Invalid parameters
- `401`: Invalid API key
- `404`: Endpoint not found
- `429`: Rate limit exceeded
- `500`: Server error

**Task Status Values**:
- `pending`: Task submitted, not yet processing
- `processing`: Generation in progress
- `completed`: Image ready
- `failed`: Generation failed

**Polling Best Practices**:
- Poll every 2 seconds
- Maximum 60 attempts (120 seconds total)
- Check `status` field in response
- Extract `imageUrl` when status is `completed`

---

## Rate Limits

Rate limits vary by model and subscription tier. Monitor response headers and implement exponential backoff on 429 errors.

---

## Output Formats

All models support PNG and JPEG output formats. Specify via `output_format` parameter where supported.

**Default Formats**:
- Most models: PNG
- Flux Kontext: Configurable (PNG/JPEG)
- Nano Banana: Configurable (PNG/JPEG)

---

## Examples

### Basic Generation
```bash
curl -X POST https://api.kie.ai/api/v1/gpt4o-image/generate \
  -H "X-API-KEY: your_key" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "sunset over mountains"}'
```

### Poll Status
```bash
curl https://api.kie.ai/api/v1/gpt4o-image/record-info?taskId=abc123 \
  -H "X-API-KEY: your_key"
```

### With Parameters
```bash
curl -X POST https://api.kie.ai/api/v1/ideogram/v3-text-to-image \
  -H "X-API-KEY: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "modern logo design",
    "rendering_speed": "QUALITY",
    "style": "DESIGN",
    "num_images": 2
  }'
```

---

## Additional Resources

- Official Documentation: https://docs.kie.ai
- Model Comparisons: https://kie.ai/features
- API Status: https://status.kie.ai
