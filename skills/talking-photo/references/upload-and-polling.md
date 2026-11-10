# Upload and polling examples

For installation and general usage, see the repository README. On Windows, save the key with `scripts/api-key.ps1 -Action Save` and read it from the encrypted skill-local file.

## Local-file upload and task creation (PowerShell)

Use a non-Python HTTP client for the complete API workflow. On Windows, the following PowerShell and curl example obtains both upload URLs in one request, uploads the bytes and creates the task. On other systems, use curl or another non-Python HTTPS client with the same headers and request bodies. It requires `curl.exe`. Run the example from the skill directory and set the two local paths. The key reader prefers `LIPSYNC_API_KEY`, then the encrypted file. Use the configured origin or the default origin; do not print signed URLs, which grant temporary upload access. Never send the API key to the storage URL.

```powershell
$origin = if ($env:LIPSYNC_API_BASE_URL) { $env:LIPSYNC_API_BASE_URL.TrimEnd('/') } else { 'https://lipsync.video' }
$imagePath = '<local-image-path>'
$audioPath = '<local-audio-path>'
$apiKey = & .\scripts\api-key.ps1 -Action Read
foreach ($path in @($imagePath, $audioPath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw 'Local file not found' }
}
$headers = @{ 'L-api-key' = $apiKey; 'User-Agent' = 'Lipsync-Talking-Photo/1.0'; 'Accept' = 'application/json' }
$files = @(
    @{ type = 'image'; file_name = [IO.Path]::GetFileName($imagePath) },
    @{ type = 'audio'; file_name = [IO.Path]::GetFileName($audioPath) }
)
$uploadBody = @{ files = $files } | ConvertTo-Json -Depth 4 -Compress
$uploads = Invoke-RestMethod -Method Post -Uri "$origin/api/v1/lipsync/uploads" -Headers $headers -ContentType 'application/json' -Body ([System.Text.Encoding]::UTF8.GetBytes($uploadBody))
$urls = @{}
foreach ($kind in @('image', 'audio')) {
    $items = @($uploads.files | Where-Object { $_.type -eq $kind })
    if ($items.Count -ne 1 -or -not $items[0].upload_url -or -not $items[0].file_url) { throw 'Invalid upload response' }
    $path = if ($kind -eq 'image') { $imagePath } else { $audioPath }
    & curl.exe --disable --silent --fail --user-agent 'Lipsync-Talking-Photo/1.0' --upload-file $path --output NUL -- $items[0].upload_url
    if ($LASTEXITCODE -ne 0) { throw "Storage upload failed for $kind; do not create the task" }
    $urls[$kind] = $items[0].file_url
}
$body = @{ image_url = $urls.image; audio_url = $urls.audio } | ConvertTo-Json -Compress
# If this request times out, check existing tasks before retrying to avoid a duplicate charge.
$created = Invoke-RestMethod -Method Post -Uri "$origin/api/v1/lipsync/tasks" -Headers $headers -ContentType 'application/json' -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
$taskId = $created.task_id
Write-Output "task_id=$taskId status=$($created.status) cost_credit=$($created.cost_credit)"
```

Use the polling section below with the returned `$taskId`. For mixed inputs, request an upload URL only for each local file and use the supplied public HTTPS URL for the other input. For this skill, use images in JPG/JPEG, PNG or WebP and audio in MP3 or WAV format. The API uses V4 and supports audio up to 40 seconds. Upload URLs expire after 20 minutes; requests for new URLs are limited to once per 60 seconds per API key. Respect `Retry-After` on 429. A successful upload URL request does not mean the storage PUT succeeded. If PUT fails, diagnose the storage response without exposing its signed URL and do not create a task. A 403 from one client is not proof of a particular root cause; curl without an explicitly added content type has worked in one environment.

If the create outcome is uncertain, check existing tasks before retrying because another request may create and charge for a duplicate.

## Manual create and poll (PowerShell)

Run this example from the skill directory. The key reader prefers `LIPSYNC_API_KEY`, then the encrypted file. Use the default origin from API.md or an explicitly configured `LIPSYNC_API_BASE_URL`; do not change the origin merely to work around an error. Supply the user's public HTTPS URLs below. If the create request times out, check existing tasks before retrying because a retry may create and charge for a duplicate. Creating a task can consume credits.

```powershell
$origin = if ($env:LIPSYNC_API_BASE_URL) { $env:LIPSYNC_API_BASE_URL.TrimEnd('/') } else { 'https://lipsync.video' }
$apiKey = & .\scripts\api-key.ps1 -Action Read
$headers = @{ 'L-api-key' = $apiKey; 'User-Agent' = 'Lipsync-Talking-Photo/1.0'; 'Accept' = 'application/json' }
$body = @{ image_url = '<public-image-https-url>'; audio_url = '<public-audio-https-url>' } | ConvertTo-Json -Compress
$created = Invoke-RestMethod -Method Post -Uri "$origin/api/v1/lipsync/tasks" -Headers $headers -ContentType 'application/json' -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
$taskId = $created.task_id
Write-Output "task_id=$taskId status=$($created.status) cost_credit=$($created.cost_credit)"

$deadline = (Get-Date).AddMinutes(30)
$lastStatus = $created.status
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 10
    if ((Get-Date) -ge $deadline) { break }
    try {
        $result = Invoke-RestMethod -Uri "$origin/api/v1/lipsync/tasks/$taskId" -Headers $headers
        $lastStatus = $result.status
        if ($lastStatus -in @('succeeded', 'failed')) { $result | ConvertTo-Json -Compress; break }
    } catch {
        # Stop on HTTP errors; handle 429 Retry-After before querying again.
        # A failed query does not mean the task failed.
        if ($_.Exception.Response) { Write-Warning 'Task query returned an HTTP error; inspect it before retrying.'; break }
        Write-Warning 'Task query failed; retrying.'
    }
}
if ($lastStatus -notin @('succeeded', 'failed')) { Write-Output "task_id=$taskId last_known_status=$lastStatus; query again later" }
```

For another check later, use the non-Python GET request above with the existing task ID. An HTTP 403 from one client should be diagnosed rather than assumed to be an API outage; use an appropriate HTTPS client without exposing the key. Check existing tasks before retrying an uncertain create request to avoid duplicate charges.

See [API.md](../API.md) for the versioned contract.
