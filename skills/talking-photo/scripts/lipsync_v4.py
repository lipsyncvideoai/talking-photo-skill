"""Minimal Python 3.8 client for the Lipsync v4 open API."""

import argparse
import ipaddress
import json
import os
import socket
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


class APIError(Exception):
    def __init__(self, status, code, message):
        self.status = status
        self.code = code
        super().__init__(message)


def public_https_url(value):
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Image and audio URLs must be public HTTPS URLs")
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        if parsed.hostname.lower() == "localhost" or parsed.hostname.lower().endswith(
            ".localhost"
        ):
            raise ValueError("Local URLs are not accepted")
    else:
        if not address.is_global:
            raise ValueError("Local URLs are not accepted")
    return value


class LipsyncClient:
    def __init__(self, api_key, base_url, sleep=time.sleep):
        if not api_key:
            raise ValueError("Set LIPSYNC_API_KEY in the host environment")
        base = urlsplit(base_url)
        if base.scheme != "https" or not base.netloc or base.username or base.password:
            raise ValueError("LIPSYNC_API_BASE_URL must be an HTTPS origin")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.sleep = sleep

    def request(self, method, path, payload=None):
        headers = {"L-api-key": self.api_key, "Accept": "application/json"}
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")
        request = Request(
            self.base_url + path, data=data, headers=headers, method=method
        )
        for attempt in range(3):
            try:
                with urlopen(request, timeout=20) as response:
                    return json.load(response)
            except HTTPError as exc:
                try:
                    body = json.load(exc)
                    error = body.get("error", {})
                    code = error.get("code", "HTTP_%s" % exc.code)
                    message = error.get("message", "Request failed")
                except (ValueError, AttributeError):
                    code, message = "HTTP_%s" % exc.code, "Request failed"
                if exc.code == 429 and attempt < 2:
                    retry_after = (
                        exc.headers.get("Retry-After") if exc.headers else None
                    )
                    try:
                        delay = max(3.0, min(float(retry_after), 60.0))
                    except (TypeError, ValueError):
                        delay = 3.0
                    self.sleep(delay)
                    continue
                raise APIError(exc.code, code, message)
            except (URLError, socket.timeout, TimeoutError) as exc:
                if method == "POST" and path == "/api/v1/lipsync/tasks":
                    raise APIError(
                        None, "NETWORK_ERROR",
                        "Task creation outcome unknown; check existing tasks before retrying",
                    ) from exc
                if attempt == 2:
                    raise APIError(
                        None, "NETWORK_ERROR", "Network request failed"
                    ) from exc
                self.sleep(3.0)

    def put_file(self, upload_url, path):
        public_https_url(upload_url)
        with open(path, "rb") as source:
            request = Request(upload_url, data=source.read(), method="PUT")
        try:
            with urlopen(request, timeout=120):
                pass
        except (HTTPError, URLError, socket.timeout, TimeoutError) as exc:
            raise APIError(None, "UPLOAD_ERROR", "File upload failed") from exc

    def upload_files(self, paths):
        files = [
            {"type": kind, "file_name": Path(path).name} for kind, path in paths.items()
        ]
        allowed_extensions = {
            "image": {".jpg", ".jpeg", ".png", ".webp"},
            "audio": {".mp3", ".wav"},
        }
        for kind, path in paths.items():
            if not Path(path).is_file():
                raise ValueError("Local media file does not exist")
            if Path(path).suffix.lower() not in allowed_extensions.get(kind, set()):
                if kind == "image":
                    raise ValueError("Image file must be JPG, JPEG, PNG or WebP")
                raise ValueError("Audio file must be MP3 or WAV")
        result = self.request("POST", "/api/v1/lipsync/uploads", {"files": files})
        entries = result["files"]
        if len(entries) != len(paths) or {item["type"] for item in entries} != set(
            paths
        ):
            raise ValueError("Invalid upload response")
        urls = {}
        for item in entries:
            self.put_file(item["upload_url"], paths[item["type"]])
            urls[item["type"]] = public_https_url(item["file_url"])
        return urls

    def create(self, image_url, audio_url):
        payload = {
            "image_url": public_https_url(image_url),
            "audio_url": public_https_url(audio_url),
        }
        return self.request("POST", "/api/v1/lipsync/tasks", payload)

    def get(self, task_id):
        return self.request("GET", "/api/v1/lipsync/tasks/" + quote(task_id, safe=""))

    def run(self, image_url, audio_url, create_only=False, max_wait=120):
        created = self.create(image_url, audio_url)
        task_id = created["task_id"]
        if create_only or max_wait <= 0:
            return (
                {
                    "task_id": task_id,
                    "status": created["status"],
                    "cost_credit": created.get("cost_credit"),
                }
                if create_only
                else {"task_id": task_id, "status": "processing"}
            )
        deadline = time.monotonic() + max_wait
        while time.monotonic() + 3 <= deadline:
            self.sleep(3)
            result = self.get(task_id)
            if result["status"] in ("succeeded", "failed"):
                return result
        return {"task_id": task_id, "status": "processing"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Create or query a Lipsync v4 task")
    parser.add_argument(
        "--base-url", default=os.getenv("LIPSYNC_API_BASE_URL", "https://lipsync.video")
    )
    parser.add_argument("--image-url")
    parser.add_argument("--audio-url")
    parser.add_argument("--image-file")
    parser.add_argument("--audio-file")
    parser.add_argument("--task-id")
    parser.add_argument("--create-only", action="store_true")
    parser.add_argument("--max-wait", type=int, default=120)
    args = parser.parse_args(argv)
    if not args.task_id and (
        bool(args.image_url) == bool(args.image_file)
        or bool(args.audio_url) == bool(args.audio_file)
    ):
        parser.error(
            "provide one URL or file for each of image and audio, or --task-id"
        )
    try:
        api = LipsyncClient(os.getenv("LIPSYNC_API_KEY"), args.base_url)
        if args.task_id:
            result = api.get(args.task_id)
        else:
            paths = {
                kind: path
                for kind, path in (
                    ("image", args.image_file),
                    ("audio", args.audio_file),
                )
                if path
            }
            uploaded = api.upload_files(paths) if paths else {}
            result = api.run(
                args.image_url or uploaded.get("image"),
                args.audio_url or uploaded.get("audio"),
                args.create_only,
                args.max_wait,
            )
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (APIError, ValueError, KeyError, OSError) as exc:
        status = exc.status if isinstance(exc, APIError) else None
        advice = {
            401: "Check or regenerate your API key",
            402: "Insufficient credits",
        }.get(status, str(exc))
        print(json.dumps({"error": advice, "status": status}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
