"""VLM verifier: ask a vision-language model a yes/no or short-answer question
about an image. Backed by a llama.cpp llama-server /v1/chat/completions endpoint.

Fails soft: if the endpoint is down or times out, verify() returns "" so
callers can degrade gracefully to OCR-only behavior.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_ENDPOINT = "http://127.0.0.1:8090"


class VLMClient:
    def __init__(self, endpoint: str | None = None, timeout: float = 60.0):
        self.endpoint = (endpoint or os.environ.get("VLM_ENDPOINT") or DEFAULT_ENDPOINT).rstrip("/")
        self.timeout = timeout

    def verify(self, image_path: str | Path, question: str, max_tokens: int = 60) -> str:
        img_bytes = Path(image_path).read_bytes()
        b64 = base64.b64encode(img_bytes).decode("ascii")
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ],
                }
            ],
            "max_tokens": max_tokens,
            "temperature": 0,
        }
        req = urllib.request.Request(
            f"{self.endpoint}/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError):
            return ""
        try:
            return body["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError):
            return ""

    def is_visible(self, image_path: str | Path, target: str) -> bool:
        q = (
            f'Is a chat or group with the name "{target}" visible in this WeChat '
            'chat list screenshot? Answer only "yes" or "no".'
        )
        ans = self.verify(image_path, q, max_tokens=6).lower()
        return ans.startswith("yes")

    def healthy(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.endpoint}/health", timeout=3.0) as resp:
                return resp.status == 200
        except (urllib.error.URLError, TimeoutError, OSError):
            return False
