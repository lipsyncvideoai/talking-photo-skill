# Talking Photo Skill

Create a lip-synced talking photo video from an image and audio with Lipsync. This repository provides one skill for talking photo generation, including local-file upload and task status queries.

## Install / 安装

Requires Node.js and npm for the installer. After this repository is pushed to GitHub, run in your project directory:

```bash
npx skills add lipsyncvideoai/talking-photo-skill --skill talking-photo
```

Select the agent(s) in the installer. Use `--global` for user-wide installation, or `--list` to list available skills. Support and installation locations vary by agent; see the [skills CLI](https://github.com/vercel-labs/skills). For manual installation, copy the entire `skills/talking-photo` directory into your agent's skills directory, keeping `SKILL.md`, `API.md`, `references/`, and `scripts/` together. For example, use `.agents/skills/talking-photo` for a Codex project or `.claude/skills/talking-photo` for Claude Code. Restart the agent session if needed.

## Set up / 配置

1. Create an API key on the [Lipsync subscription page](https://lipsync.video/subscription).
2. Set `LIPSYNC_API_KEY` securely in the environment where the agent runs. Never commit the key or paste it into chat. Restart the agent if it inherited its environment before the variable was set.
3. The bundled client requires Python 3.8+ and HTTPS access to the API and upload storage. The default API origin is documented in [API.md](skills/talking-photo/API.md). Set `LIPSYNC_API_BASE_URL` only when using an explicitly selected deployment.

macOS/Linux (current shell):

```bash
read -rs -p 'Lipsync API key: ' LIPSYNC_API_KEY; echo
export LIPSYNC_API_KEY
```

Windows PowerShell (current shell, hidden input):

```powershell
$key = Read-Host 'Lipsync API key' -AsSecureString
$env:LIPSYNC_API_KEY = [System.Net.NetworkCredential]::new('', $key).Password
```

Configure the environment where the agent actually runs; a shell variable does not automatically propagate to an already running agent or a remote runtime. Persistent configuration is available through your platform's secure environment settings.

## Use with an agent / 使用

Provide one JPG/JPEG, PNG or WebP image and one MP3 or WAV audio file (up to 40 seconds), or supported HTTPS URLs for those formats. For example:

> Use the talking-photo skill to turn `portrait.jpg` and `speech.mp3` into a talking photo. Wait for the result.

> 使用 talking-photo skill，把这张人物照片和这段音频生成对口型视频。

The agent uploads local files, creates a task, reports its ID, and polls the task. It can also query an existing task when given its ID. The service uses V4, accepts audio up to 40 seconds, and may charge credits according to the product's pricing; the creation response reports the actual charge. Only media hosts accepted by the API can be used directly. No `mode` parameter is needed.

If the API key is missing, configure it before trying again. If a request to create a task times out, check existing jobs before retrying: the task may already exist and another request can incur another charge. See [the skill instructions](skills/talking-photo/SKILL.md), [API contract](skills/talking-photo/API.md), and [manual upload and polling examples](skills/talking-photo/references/upload-and-polling.md).

## License

Apache License 2.0. See [LICENSE](LICENSE). The service and its API usage are governed by their own terms and pricing.
