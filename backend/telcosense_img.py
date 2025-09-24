import requests
from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import jwt_required

from backend.app_config import TELCOSENSE_IMG_API

telcosense_img = Blueprint("telcosense_img", __name__)


@telcosense_img.route("/api/raincz/list")
@jwt_required()
def proxy_raincz_list():
    try:
        res = requests.get(f"{TELCOSENSE_IMG_API}/api/raincz/list", params=request.args)
        return jsonify(res.json())
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Failed to fetch raincz list", "details": str(e)}), 502


@telcosense_img.route("/api/raincz/<path:filename>")
@jwt_required()
def proxy_raincz_file(filename):
    try:
        res = requests.get(f"{TELCOSENSE_IMG_API}/api/raincz/{filename}", stream=True)
        return Response(
            res.iter_content(chunk_size=4096),
            content_type=res.headers.get("Content-Type", "image/png"),
            status=res.status_code,
        )
    except requests.exceptions.RequestException as e:
        return (
            jsonify({"error": "Failed to fetch raincz image", "details": str(e)}),
            502,
        )


@telcosense_img.route("/api/tempcz/list")
@jwt_required()
def proxy_tempcz_list():
    try:
        res = requests.get(f"{TELCOSENSE_IMG_API}/api/tempcz/list", params=request.args)
        return jsonify(res.json())
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Failed to fetch tempcz list", "details": str(e)}), 502


@telcosense_img.route("/api/tempcz/<path:filename>")
@jwt_required()
def proxy_tempcz_file(filename):
    try:
        res = requests.get(f"{TELCOSENSE_IMG_API}/api/tempcz/{filename}", stream=True)
        return Response(
            res.iter_content(chunk_size=4096),
            content_type=res.headers.get("Content-Type", "image/png"),
            status=res.status_code,
        )
    except requests.exceptions.RequestException as e:
        return (
            jsonify({"error": "Failed to fetch tempcz image", "details": str(e)}),
            502,
        )
