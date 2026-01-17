from flask import Blueprint, jsonify, Response, stream_with_context
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

@api_bp.get("/api/get_book/<book_code>")
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
