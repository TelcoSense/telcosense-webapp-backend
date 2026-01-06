from pathlib import PurePosixPath

import requests
from flask import Blueprint, Response, abort, jsonify, request

from backend.app_config import CHMI_IMG_API

chmi_img = Blueprint("chmi_img", __name__)


def _sanitize_and_validate_filename(filename: str) -> str:
    if filename is None:
        abort(404)

    filename = filename.lstrip("/")
    if not filename:
        abort(404)

    if "\x00" in filename:
        abort(404)

    if "\\" in filename:
        abort(404)

    # basic abuse limits
    if len(filename) > 2048:
        abort(404)

    p = PurePosixPath(filename)

    if any(part in ("", ".", "..") for part in p.parts):
        abort(404)

    if len(p.parts) > 30:
        abort(404)

    return filename


def _proxy_list(upstream_path: str):
    try:
        res = requests.get(
            f"{CHMI_IMG_API}{upstream_path}",
            params=request.args,
            timeout=10,
        )
        res.raise_for_status()
        return jsonify(res.json()), 200
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Failed to fetch list", "details": str(e)}), 502


def _proxy_file(upstream_prefix: str, filename: str):
    filename = _sanitize_and_validate_filename(filename)

    try:
        upstream_res = requests.get(
            f"{CHMI_IMG_API}{upstream_prefix}{filename}",
            stream=True,
            timeout=10,
        )

        resp = Response(
            upstream_res.iter_content(chunk_size=4096),
            content_type=upstream_res.headers.get("Content-Type", "image/png"),
            status=upstream_res.status_code,
            headers={"X-Content-Type-Options": "nosniff"},
        )

        # Ensure we close the upstream connection after Flask finishes streaming
        resp.call_on_close(upstream_res.close)
        return resp

    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Failed to fetch image", "details": str(e)}), 502


@chmi_img.route("/api/maxz/list")
# @jwt_required()
def proxy_maxz_list():
    return _proxy_list("/api/maxz/list")


@chmi_img.route("/api/maxz/<path:filename>")
# @jwt_required()
def proxy_maxz_file(filename):
    return _proxy_file("/api/maxz/", filename)


@chmi_img.route("/api/merge1h/list")
# @jwt_required()
def proxy_merge1h_list():
    return _proxy_list("/api/merge1h/list")


@chmi_img.route("/api/merge1h/<path:filename>")
# @jwt_required()
def proxy_merge1h_file(filename):
    return _proxy_file("/api/merge1h/", filename)
