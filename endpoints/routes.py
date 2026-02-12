from urllib.parse import urlparse

import requests
from flask import Blueprint, Response, jsonify, make_response, request, stream_with_context

api_bp = Blueprint("api", __name__)

ALLOWED_ORIGINS = {"https://github.com", "https://www.github.com"}
ALLOWED_DOMAIN = "ncert.nic.in"
ALLOWED_BOOK_CONTENT_TYPES = {"application/zip", "application/octet-stream"}
CHROME_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,application/zip,application/octet-stream,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def _apply_cors(response: Response) -> Response:
    origin = request.headers.get("Origin")
    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


def _options_response() -> Response:
    return _apply_cors(make_response("", 204))


def _is_allowed_host(hostname: str | None) -> bool:
    if not hostname:
        return False
    host = hostname.lower()
    return host == ALLOWED_DOMAIN or host.endswith(f".{ALLOWED_DOMAIN}")


def _validate_ncert_url(raw_url: str) -> tuple[str | None, str | None]:
    parsed = urlparse(raw_url)
    if parsed.scheme != "https":
        return None, "Only https URLs are allowed"
    if not _is_allowed_host(parsed.hostname):
        return None, "Only URLs from ncert.nic.in are allowed"
    return parsed.geturl(), None


def _proxy_url(
    remote_url: str,
    allowed_content_types: set[str] | None = None,
    content_type_error: str = "Only PDF and ZIP responses are allowed",
) -> Response:
    try:
        upstream_resp = requests.get(
            remote_url,
            stream=True,
            timeout=30,
            headers=CHROME_HEADERS,
        )
    except requests.RequestException:
        return _apply_cors(jsonify({"error": "Failed to fetch upstream URL"})), 502

    if upstream_resp.status_code >= 400:
        return _apply_cors(
            jsonify(
                {
                    "error": "Upstream returned an error",
                    "status_code": upstream_resp.status_code,
                }
            )
        ), 502

    content_type = upstream_resp.headers.get("Content-Type", "")
    if allowed_content_types is not None:
        mime_type = content_type.split(";", 1)[0].strip().lower()
        if not mime_type or mime_type not in allowed_content_types:
            return _apply_cors(
                jsonify(
                    {
                        "error": content_type_error,
                        "content_type": content_type,
                    }
                )
            ), 415

    response = Response(
        stream_with_context(upstream_resp.iter_content(chunk_size=8192)),
        content_type=content_type,
        status=upstream_resp.status_code,
    )

    content_disposition = upstream_resp.headers.get("Content-Disposition")
    if content_disposition:
        response.headers["Content-Disposition"] = content_disposition

    return _apply_cors(response)


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


@api_bp.route("/api/get_book/<string:book_code>", methods=["GET", "OPTIONS"])
def get_book(book_code: str):
    if request.method == "OPTIONS":
        return _options_response()

    remote_url = f"https://ncert.nic.in/textbook/pdf/{book_code}.zip"
    return _proxy_url(
        remote_url,
        allowed_content_types=ALLOWED_BOOK_CONTENT_TYPES,
        content_type_error="Book endpoint only allows ZIP responses",
    )


@api_bp.route("/api/proxy", methods=["GET", "OPTIONS"])
def proxy_ncert_asset():
    if request.method == "OPTIONS":
        return _options_response()

    raw_url = request.args.get("url", "").strip()
    if not raw_url:
        return _apply_cors(jsonify({"error": "Missing required query parameter: url"})), 400

    validated_url, error = _validate_ncert_url(raw_url)
    if error:
        return _apply_cors(jsonify({"error": error})), 403

    return _proxy_url(validated_url)
