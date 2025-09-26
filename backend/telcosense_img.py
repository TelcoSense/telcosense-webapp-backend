import requests
from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import jwt_required

from backend.app_config import TELCOSENSE_IMG_API

telcosense_img = Blueprint("telcosense_img", __name__)


# helper for proxying JSON list
def proxy_list_request(datatype: str):
    try:
        res = requests.get(
            f"{TELCOSENSE_IMG_API}/api/{datatype}/list",
            params=request.args,
            timeout=10,
        )
        res.raise_for_status()
        return jsonify(res.json())
    except requests.exceptions.RequestException as e:
        return (
            jsonify({"error": f"Failed to fetch {datatype} list", "details": str(e)}),
            502,
        )


# helper for proxying image files
def proxy_file_request(datatype: str, filename: str):
    try:
        res = requests.get(
            f"{TELCOSENSE_IMG_API}/api/{datatype}/{filename}",
            stream=True,
            timeout=10,
        )
        return Response(
            res.iter_content(chunk_size=4096),
            content_type=res.headers.get("Content-Type", "image/png"),
            status=res.status_code,
        )
    except requests.exceptions.RequestException as e:
        return (
            jsonify({"error": f"Failed to fetch {datatype} image", "details": str(e)}),
            502,
        )


# generic routes
@telcosense_img.route("/api/<datatype>/list")
@jwt_required()
def proxy_list(datatype):
    return proxy_list_request(datatype)


@telcosense_img.route("/api/<datatype>/<path:filename>")
@jwt_required()
def proxy_file(datatype, filename):
    return proxy_file_request(datatype, filename)
