from pathlib import PurePosixPath

import requests
from flask import Blueprint, Response, abort, jsonify, request
from flask_jwt_extended import jwt_required

from backend.app_config import TELCOSENSE_IMG_API

telcosense_img = Blueprint("telcosense_img", __name__)

ALLOWED_DATATYPES = {"raincz", "tempcz", "tempchmi"}


def _validate_datatype(datatype: str) -> str:
    if datatype not in ALLOWED_DATATYPES:
        abort(404)
    return datatype


def _sanitize_and_validate_filename(filename: str) -> str:
    """
    Minimal safety without breaking existing URLs:
    - allows nested paths
    - strips leading '/' so accidental //... still works
    - blocks backslashes, null bytes, and '..' traversal
    """
    if filename is None:
        abort(404)

    # IMPORTANT: keep compatibility with accidental leading slashes
    filename = filename.lstrip("/")

    if not filename:
        abort(404)

    if "\x00" in filename:
        abort(404)

    # block windows separators / traversal tricks
    if "\\" in filename:
        abort(404)

    p = PurePosixPath(filename)

    # block traversal
    if any(part in ("..", ".", "") for part in p.parts):
        abort(404)

    return filename


# helper for proxying JSON list
def proxy_list_request(datatype: str):
    datatype = _validate_datatype(datatype)

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
    datatype = _validate_datatype(datatype)
    filename = _sanitize_and_validate_filename(filename)

    try:
        # keep behavior: stream upstream and pass through status code
        res = requests.get(
            f"{TELCOSENSE_IMG_API}/api/{datatype}/{filename}",
            stream=True,
            timeout=10,
        )
        return Response(
            res.iter_content(chunk_size=4096),
            content_type=res.headers.get("Content-Type", "image/png"),
            status=res.status_code,
            headers={"X-Content-Type-Options": "nosniff"},
        )
    except requests.exceptions.RequestException as e:
        return (
            jsonify({"error": f"Failed to fetch {datatype} image", "details": str(e)}),
            502,
        )


# generic routes
@telcosense_img.route("/api/<datatype>/list")
# @jwt_required()
def proxy_list(datatype):
    return proxy_list_request(datatype)


@telcosense_img.route("/api/<datatype>/<path:filename>")
# @jwt_required()
def proxy_file(datatype, filename):
    return proxy_file_request(datatype, filename)


def proxy_drywet_request():
    try:
        res = requests.get(
            f"{TELCOSENSE_IMG_API}/api/drywet",
            params=request.args,  # forwards start/end (and anything else)
            timeout=10,
        )
        res.raise_for_status()
        return jsonify(res.json())
    except requests.exceptions.RequestException as e:
        return (
            jsonify({"error": "Failed to fetch drywet list", "details": str(e)}),
            502,
        )


@telcosense_img.route("/api/drywet", methods=["GET"])
@jwt_required()
def proxy_drywet():
    return proxy_drywet_request()
