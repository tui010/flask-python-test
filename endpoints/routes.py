import re
from urllib.parse import urlparse

from flask import Blueprint, jsonify, Response, request, stream_with_context
import requests

api_bp = Blueprint("api", __name__)

@api_bp.get("/api/data")
def get_sample_data():
    return jsonify(
        {
            "data": [
                {"id": 1, "name": "Sample Item 1", "value": 100},
                {"id": 2, "name": "Sample Item 2", "value": 200},
                {"id": 3, "name": "Sample Item 3", "value": 300},
            ],
            "total": 3,
            "timestamp": "2024-01-01T00:00:00Z",
        }
    )

@api_bp.get("/api/items/<int:item_id>")
def get_item(item_id: int):
    return jsonify(
        {
            "item": {
                "id": item_id,
                "name": f"Sample Item {item_id}",
                "value": item_id * 100,
            },
            "timestamp": "2024-01-01T00:00:00Z",
        }
    )

@api_bp.get("/api/get_book/<string:book_code>")
def get_book(book_code: str):
    remote_url = f"https://ncert.nic.in/textbook/pdf/{book_code}.zip"
    upstream_resp = requests.get(remote_url, stream=True)

    return Response(
        stream_with_context(upstream_resp.iter_content(chunk_size=8192)),
        content_type=upstream_resp.headers.get('Content-Type', 'application/octet-stream'),
        headers={
            'Content-Disposition': f'attachment; filename="{book_code}.zip"'
        }
    )


def _extract_filename(content_disposition: str | None, fallback_path: str) -> str | None:
    if content_disposition:
        match = re.search(r'filename="?([^";]+)"?', content_disposition, re.IGNORECASE)
        if match:
            return match.group(1)
    if fallback_path:
        return fallback_path.rsplit("/", 1)[-1] or None
    return None


@api_bp.get("/api/proxy")
def proxy_ncert():
    url = request.args.get("url")
    if not url:
        return jsonify(error="Missing required query parameter: url"), 400

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return jsonify(error="Invalid url: must include scheme and host"), 400
    if parsed.scheme != "https":
        return jsonify(error="Invalid url: scheme must be https"), 400
    if parsed.hostname != "ncert.nic.in":
        return jsonify(error="Invalid url: host must be ncert.nic.in"), 400

    upstream_resp = requests.get(url, stream=True)
    raw_content_type = upstream_resp.headers.get("Content-Type", "")
    filename = _extract_filename(upstream_resp.headers.get("Content-Disposition"), parsed.path)

    headers = {}
    if upstream_resp.headers.get("Content-Disposition"):
        headers["Content-Disposition"] = upstream_resp.headers["Content-Disposition"]
    elif filename:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'

    return Response(
        stream_with_context(upstream_resp.iter_content(chunk_size=8192)),
        content_type=raw_content_type or "application/octet-stream",
        headers=headers,
    )
