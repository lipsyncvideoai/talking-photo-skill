import importlib.util
import io
import json
import pathlib
import socket
import tempfile
import unittest
from unittest import mock
from urllib.error import HTTPError, URLError


SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "lipsync_v4.py"
spec = importlib.util.spec_from_file_location("lipsync_v4", str(SCRIPT))
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


class Response:
    def __init__(self, data, headers=None):
        self.data = json.dumps(data).encode()
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.data


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.api = client.LipsyncClient("secret", "https://api.example.com", sleep=lambda _: None)

    def test_create_only_returns_task_without_idempotency_header(self):
        with mock.patch.object(client, "urlopen", return_value=Response({"task_id": "42", "status": "processing", "cost_credit": 3})) as send:
            result = self.api.run("https://example.com/a.jpg", "https://example.com/a.mp3", create_only=True)
        self.assertEqual(result["task_id"], "42")
        self.assertEqual(send.call_args.args[0].headers["L-api-key"], "secret")
        self.assertNotIn("Authorization", send.call_args.args[0].headers)
        self.assertNotIn("Idempotency-key", send.call_args.args[0].headers)

    def test_poll_success_and_failure(self):
        for terminal in ({"status": "succeeded", "video_url": "https://example.com/v.mp4", "error": None},
                         {"status": "failed", "video_url": None, "error": {"code": "TASK_TIMEOUT", "message": "Timed out"}}):
            replies = [Response({"task_id": "42", "status": "processing", "cost_credit": 3}),
                       Response({"task_id": "42", "status": "processing", "video_url": None, "error": None}),
                       Response(dict(terminal, task_id="42"))]
            with mock.patch.object(client, "urlopen", side_effect=replies):
                result = self.api.run("https://example.com/a.jpg", "https://example.com/a.mp3", max_wait=10)
            self.assertEqual(result["status"], terminal["status"])

    def test_network_timeout_does_not_retry_create(self):
        with mock.patch.object(client, "urlopen", side_effect=[URLError(socket.timeout()), Response({"task_id": "42", "status": "processing", "cost_credit": 3})]) as send:
            with self.assertRaises(client.APIError):
                self.api.run("https://example.com/a.jpg", "https://example.com/a.mp3", create_only=True)
        self.assertEqual(send.call_count, 1)

    def test_http_errors(self):
        for status in (401, 402):
            with mock.patch.object(client, "urlopen", side_effect=HTTPError("url", status, "error", {}, io.BytesIO(b'{}'))):
                with self.assertRaises(client.APIError) as caught:
                    self.api.run("https://example.com/a.jpg", "https://example.com/a.mp3", create_only=True)
            self.assertEqual(caught.exception.status, status)

    def test_rate_limit_honors_retry_after(self):
        sleep = mock.Mock()
        self.api.sleep = sleep
        replies = [HTTPError("url", 429, "rate", {"Retry-After": "4"}, io.BytesIO(b'{}')),
                   Response({"task_id": "42", "status": "processing", "cost_credit": 3})]
        with mock.patch.object(client, "urlopen", side_effect=replies):
            self.api.run("https://example.com/a.jpg", "https://example.com/a.mp3", create_only=True)
        sleep.assert_called_once_with(4.0)

    def test_wait_limit_keeps_processing(self):
        with mock.patch.object(client, "urlopen", return_value=Response({"task_id": "42", "status": "processing", "cost_credit": 3})):
            result = self.api.run("https://example.com/a.jpg", "https://example.com/a.mp3", max_wait=0)
        self.assertEqual(result, {"task_id": "42", "status": "processing"})

    def test_upload_rejects_unsupported_file_formats_before_request(self):
        with tempfile.TemporaryDirectory() as folder:
            image = pathlib.Path(folder) / "photo.gif"
            audio = pathlib.Path(folder) / "voice.ogg"
            image.touch()
            audio.touch()
            with mock.patch.object(self.api, "request") as request:
                with self.assertRaisesRegex(ValueError, "JPG"):
                    self.api.upload_files({"image": str(image)})
                with self.assertRaisesRegex(ValueError, "MP3 or WAV"):
                    self.api.upload_files({"audio": str(audio)})
                request.assert_not_called()

    def test_missing_key_and_local_media_are_rejected_before_request(self):
        with self.assertRaises(ValueError):
            client.LipsyncClient("", "https://api.example.com")
        with mock.patch.object(client, "urlopen") as send:
            with self.assertRaises(ValueError):
                self.api.run("https://127.0.0.1/private.jpg", "https://example.com/a.mp3")
            send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
