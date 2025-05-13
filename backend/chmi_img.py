import requests
from flask import Blueprint, Response, jsonify, request

from backend.app_config import CHMI_IMG_API

chmi_img = Blueprint("chmi_img", __name__)


@chmi_img.route("/api/maxz/list")
def proxy_maxz_list():
    try:
        res = requests.get(f"{CHMI_IMG_API}/api/maxz/list", params=request.args)
        return jsonify(res.json())
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Failed to fetch maxz list", "details": str(e)}), 502


@chmi_img.route("/api/maxz/<path:filename>")
def proxy_maxz_file(filename):
    try:
        res = requests.get(f"{CHMI_IMG_API}/api/maxz/{filename}", stream=True)
        return Response(
            res.iter_content(chunk_size=4096),
            content_type=res.headers.get("Content-Type", "image/png"),
            status=res.status_code,
        )
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Failed to fetch maxz image", "details": str(e)}), 502


@chmi_img.route("/api/merge1h/list")
def proxy_merge1h_list():
    try:
        res = requests.get(f"{CHMI_IMG_API}/api/merge1h/list", params=request.args)
        return jsonify(res.json())
    except requests.exceptions.RequestException as e:
        return (
            jsonify({"error": "Failed to fetch merge1h list", "details": str(e)}),
            502,
        )


@chmi_img.route("/api/merge1h/<path:filename>")
def proxy_merge1h_file(filename):
    try:
        res = requests.get(f"{CHMI_IMG_API}/api/merge1h/{filename}", stream=True)
        return Response(
            res.iter_content(chunk_size=4096),
            content_type=res.headers.get("Content-Type", "image/png"),
            status=res.status_code,
        )
    except requests.exceptions.RequestException as e:
        return (
            jsonify({"error": "Failed to fetch merge1h image", "details": str(e)}),
            502,
        )
