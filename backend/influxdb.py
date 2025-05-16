from flask import Blueprint, jsonify, request
from influxdb_client import InfluxDBClient

from backend.app_config import ORG, TOKEN_PUBLIC_READ, URL_PUBLIC

influxdb = Blueprint("influxb", __name__)

client = InfluxDBClient(url=URL_PUBLIC, token=TOKEN_PUBLIC_READ, org=ORG)


@influxdb.route("/api/wsdata", methods=["POST"])
def ws_data():
    data = request.get_json()
    start = data.get("start")
    stop = data.get("stop")
    gh_id = data.get("ghId")
    if not start or not stop or not gh_id:
        return jsonify({"error": "Missing start, stop, or ghId"}), 400
    query = f"""
        from(bucket: "chmi_data")
        |> range(start: {start}, stop: {stop})
        |> filter(fn: (r) =>
        (r["_measurement"] == "T" or r["_measurement"] == "SRA10M") and r["_field"] == "{gh_id}")
    """.strip()
    try:
        result = {"T": [], "SRA10M": []}
        tables = client.query_api().query(query)
        for table in tables:
            for record in table.records:
                point = {
                    "time": record.get_time().isoformat(),
                    "value": record.get_value(),
                }
                measurement = record.get_measurement()
                if measurement in result:
                    result[measurement].append(point)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
