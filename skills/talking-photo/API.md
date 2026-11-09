# Lipsync v4 open API

Base origin: `https://lipsync.video` (configure the actual deployment origin with `LIPSYNC_API_BASE_URL`). All requests use HTTPS. Set `Content-Type: application/json` for API requests with JSON bodies, including upload URL and task creation requests. Send raw file bytes to signed storage PUT URLs according to their signing requirements; do not add the JSON content type to these uploads. The public task endpoints authenticate **only** with `L-api-key: <raw key>`; they do not use `Authorization: Bearer`. A missing, invalid, or revoked key returns HTTP 401. Never log or print the raw key. Product API Key management is separate and uses product login JWT Bearer, not `L-api-key`.

## Create

To upload local media first, call `POST /api/v1/lipsync/uploads` with `L-api-key` and a JSON body such as `{"files":[{"type":"image","file_name":"photo.jpg"},{"type":"audio","file_name":"voice.mp3"}]}`. Supply one or two files per request. For this skill, use images in JPG/JPEG, PNG or WebP and audio in MP3 or WAV format. The underlying upload API additionally accepts m4a and ogg, but these formats are outside this skill’s input requirements. No other request headers are required. The response contains a `files` array with `type`, `file_name`, `upload_url`, and `file_url` for each item. PUT the file bytes directly to its `upload_url` within 20 minutes, then pass the corresponding `file_url` to the task creation API. Each API key can request upload URLs once per 60 seconds; extra requests return HTTP 429 with `Retry-After: 60`. This limit applies to URL requests, not PUT operations to OSS.

`POST /api/v1/lipsync/tasks` with `Content-Type: application/json` and `L-api-key`:

```json
{
  "image_url": "https://example.com/portrait.jpg",
  "audio_url": "https://example.com/speech.mp3"
}
```

Both URLs must use HTTPS and a product-controlled media host accepted by the API. The API uses V4 and accepts audio up to 40 seconds. Only `image_url` and `audio_url` are accepted; remove `mode` from older integrations because extra fields produce HTTP 422. Subtitles are off. Product V4 pricing and entitlements apply; the server returns the actual charged credits. A 201 response looks like:

```json
{ "task_id": "<main_job_id>", "status": "processing", "cost_credit": 30 }
```

`cost_credit` is the actual charge; the sample number is illustrative. If a create request times out or its response is lost, its outcome is uncertain. Check existing tasks before retrying: another request may create and charge for a duplicate task.

## Query

`GET /api/v1/lipsync/tasks/{task_id}` with `L-api-key`. Query no faster than once per 3 seconds. The response is:

```json
{
  "task_id": "<main_job_id>",
  "status": "succeeded",
  "video_url": "https://cdn.example.com/result.mp4",
  "error": null
}
```

Public statuses are `processing`, `succeeded`, and `failed`. While processing, `video_url` is `null`. On failure, `error` contains a public code and short message. Task timeouts are handled by the offline task processor. A local client wait limit does not change server status. Unknown, unauthorized, or expired tasks return 404. Successful video results are queryable for 30 days after completion.

## Errors

Errors use the actual HTTP status and `{"error":{"code":"...","message":"..."}}`. Handle 400/422 invalid input or media, 401 missing/invalid/revoked key, 402 insufficient credits, 404 unavailable task, 429 rate or creation limit, and 500/503 server failure. For 429 honor `Retry-After` if present. Never expose internal responses as user-facing failures.

## API Key management

The signed-in product user can manage one active key at `GET`, `POST`, and `DELETE /api/v1/user/api-key`. These management endpoints require the product's JWT Bearer login, not the raw key. GET returns metadata or `{"data":null}`; POST with an empty body returns the raw key once (201); DELETE revokes it (204). The agent should direct users to the product UI for this step rather than handle their JWT or key in conversation.
