# Kie.ai Video API Documentation Reference

## Base URL
```
https://api.kie.ai
```

## Authentication
All requests require Bearer token:
```
Authorization: Bearer YOUR_API_KEY
```

## Unified Jobs API

Most video models use the unified Jobs API pattern:

### Create Task
```
POST /api/v1/jobs/createTask
```

Request body:
```json
{
  "model": "model-id",
  "callBackUrl": "optional-webhook-url",
  "input": {
    "prompt": "text description",
    // model-specific parameters
  }
}
```

Response:
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "taskId": "task_xxx"
  }
}
```

### Query Task Status
```
GET /api/v1/jobs/recordInfo?taskId={taskId}
```

Response:
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "taskId": "task_xxx",
    "model": "model-id",
    "state": "success|waiting|queuing|generating|fail",
    "resultJson": "{\"resultUrls\":[\"https://...\"]}",
    "failCode": "",
    "failMsg": "",
    "costTime": 0,
    "completeTime": 1698765432000,
    "createTime": 1698765400000
  }
}
```

### Get Account Credits
```
GET /api/v1/chat/credit
```

Response:
```json
{
  "code": 200,
  "msg": "success",
  "data": 1250
}
```

---

## Veo 3 API

### Generate Video
```
POST /api/v1/veo/generate
```

Parameters:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| prompt | string | Yes | Video description |
| model | enum | No | `veo3` or `veo3_fast` |
| imageUrls | array | No | 1-2 reference images |
| generationType | enum | No | TEXT_2_VIDEO, FIRST_AND_LAST_FRAMES_2_VIDEO, REFERENCE_2_VIDEO |
| aspectRatio | enum | No | 16:9, 9:16, Auto |
| seeds | integer | No | 10000-99999 |
| callBackUrl | string | No | Webhook URL |
| enableTranslation | boolean | No | Auto-translate prompt |
| watermark | string | No | Watermark text |

### Get Video Status
```
GET /api/v1/veo/record-info?taskId={taskId}
```

### Get 1080P Video
```
GET /api/v1/veo/get-1080p-video?taskId={taskId}
```

---

## Model-Specific Parameters

### Sora 2 (sora-2-text-to-video)
| Parameter | Type | Options |
|-----------|------|---------|
| prompt | string | max 10,000 chars |
| aspect_ratio | enum | landscape, portrait |
| n_frames | enum | "10", "15" |
| remove_watermark | boolean | - |

### Kling 2.6 (kling-2.6/text-to-video)
| Parameter | Type | Options |
|-----------|------|---------|
| prompt | string | max 1000 chars |
| sound | boolean | - |
| aspect_ratio | enum | 1:1, 16:9, 9:16 |
| duration | enum | "5", "10" |

### Wan 2.6 (wan/2-6-text-to-video)
| Parameter | Type | Options |
|-----------|------|---------|
| prompt | string | max 5000 chars |
| duration | enum | "5", "10", "15" |
| resolution | enum | 720p, 1080p |

### Hailuo (hailuo/02-image-to-video-standard)
| Parameter | Type | Options |
|-----------|------|---------|
| prompt | string | max 1500 chars |
| image_url | string | First frame |
| end_image_url | string | Last frame |
| duration | enum | "6", "10" |
| resolution | enum | 512P, 768P |
| prompt_optimizer | boolean | - |

### Seedance 1.5 (bytedance/seedance-1.5-pro)
| Parameter | Type | Options |
|-----------|------|---------|
| prompt | string | max 2500 chars |
| input_urls | array | 0-2 images |
| aspect_ratio | enum | 1:1, 4:3, 3:4, 16:9, 9:16, 21:9 |
| resolution | enum | 480p, 720p |
| duration | enum | 4, 8, 12 |
| fixed_lens | boolean | - |
| generate_audio | boolean | - |

---

## Error Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 401 | Unauthorized (invalid API key) |
| 402 | Insufficient credits |
| 404 | Not found |
| 422 | Validation error |
| 429 | Rate limited |
| 455 | Service unavailable |
| 500 | Server error |
| 501 | Generation failed |
| 505 | Feature disabled |

---

## Credit System

- 1 credit = $0.005 USD
- Credits are deducted upon task completion
- Use GET /api/v1/chat/credit to check balance

## Pricing Estimates

| Model | Est. Credits | Est. USD |
|-------|--------------|----------|
| Veo 3 Quality | 400 | $2.00 |
| Veo 3 Fast | 80 | $0.40 |
| Sora 2 T2V | 200 | $1.00 |
| Sora 2 Pro | 400 | $2.00 |
| Kling 2.6 T2V | 100 | $0.50 |
| Wan 2.6 T2V | 60 | $0.30 |
| Hailuo Standard | 60 | $0.30 |
| Seedance Pro | 80 | $0.40 |

*Prices are estimates and may vary based on parameters.*
