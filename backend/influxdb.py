from time import time as timer

import numpy as np
import pandas as pd
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from influxdb_client import InfluxDBClient

from backend.app_config import (
    ORG,
    TOKEN_INTERNAL_READ,
    TOKEN_PUBLIC_READ,
    URL_INTERNAL,
    URL_PUBLIC,
)

influxdb = Blueprint("influxb", __name__)

client_public = InfluxDBClient(url=URL_PUBLIC, token=TOKEN_PUBLIC_READ, org=ORG)
client_internal = InfluxDBClient(url=URL_INTERNAL, token=TOKEN_INTERNAL_READ, org=ORG)


@influxdb.route("/api/wsdata", methods=["POST"])
@jwt_required()
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
        tables = client_public.query_api().query(query)
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


@influxdb.route("/api/cmldata", methods=["POST"])
@jwt_required()
def cml_data():
    data = request.get_json()
    start = data.get("start")
    stop = data.get("stop")
    ip_a = data.get("ipA")
    ip_b = data.get("ipB")
    tech = data.get("tech")
    cml_id = data.get("cmlId")
    if not start or not stop or not ip_a or not ip_b or not tech:
        return jsonify({"error": "Missing start, stop, ip, or tech"}), 400
    temp_query = f"""
        from(bucket: "realtime_cbl")
        |> range(start: {start}, stop: {stop})
        |> filter(fn: (r) => r["_measurement"] == "{tech}")
        |> filter(fn: (r) => r["_field"] == "Teplota")
        |> filter(fn: (r) => r["agent_host"] == "{ip_a}" or r["agent_host"] == "{ip_b}")
        |> aggregateWindow(every: 10m, fn: mean)
        |> yield(name: "mean")
        """.strip()
    rain_intensity_query = f"""
        from(bucket: "telcorain_output")
        |> range(start: {start}, stop: {stop})
        |> filter(fn: (r) => r["_measurement"] == "telcorain")
        |> filter(fn: (r) => r["_field"] == "rain_intensity")
        |> filter(fn: (r) => r["cml_id"] == "{cml_id}")
        """.strip()
    temp_pred_query = f"""
        from(bucket: "telcorain_output")
        |> range(start: {start}, stop: {stop})
        |> filter(fn: (r) => r["_measurement"] == "telcotemp")
        |> filter(fn: (r) => r["_field"] == "temperature")
        |> filter(fn: (r) => r["cml_id"] == "{cml_id}")
        |> filter(fn: (r) => r["side"] == "A" or r["side"] == "B")
        |> pivot(rowKey:["_time"], columnKey: ["side"], valueColumn: "_value")
        """.strip()
    # define rsl and tsl queries for each tech
    if tech == "summit" or tech == "summit_bt":
        filter_string = f"""|> filter(fn: (r) => r["_field"] == "PrijimanaUroven")"""
    elif tech == "ceragon_ip_10":
        filter_string = f"""|> filter(fn: (r) => r["_field"] == "PrijimanaUroven" or r["_field"] == "VysilaciVykon")"""
        rsl_string = "PrijimanaUroven"
        tsl_string = "VysilaciVykon"
    elif tech == "ceragon_ip_20" or tech == "ceragon_ip_50":
        filter_string = f"""|> filter(fn: (r) => r["_field"] == "Signal" or r["_field"] == "Vysilany_Vykon")"""
        rsl_string = "Signal"
        tsl_string = "Vysilany_Vykon"
    elif tech == "1s10":
        filter_string = f"""|> filter(fn: (r) => r["_field"] == "PrijimanaUroven" or r["_field"] == "Tx_Power_Act")"""
        rsl_string = "PrijimanaUroven"
        tsl_string = "Tx_Power_Act"
    trsl_query = f"""
        from(bucket: "realtime_cbl")
        |> range(start: {start}, stop: {stop})
        |> filter(fn: (r) => r["_measurement"] == "{tech}")
        {filter_string}
        |> filter(fn: (r) => r["agent_host"] == "{ip_a}" or r["agent_host"] == "{ip_b}")
        |> aggregateWindow(every: 10m, fn: mean)
        |> yield(name: "mean")
        """.strip()
    try:
        result = {
            "temp_a": [],
            "temp_b": [],
            "rain_intensity": [],
            "rain_intensity_time": [],
            "temp_pred_a": [],
            "temp_pred_b": [],
            "temp_pred_time": [],
        }
        # temperatures first
        tables = client_internal.query_api().query(temp_query)
        for table in tables:
            for record in table.records:
                if ip_a == record.values.get("agent_host"):
                    result["temp_a"].append(
                        round(record.get_value(), 1)
                        if record.get_value() is not None
                        else None
                    )
                elif ip_b == record.values.get("agent_host"):
                    result["temp_b"].append(
                        round(record.get_value(), 1)
                        if record.get_value() is not None
                        else None
                    )
        # rain intensity
        tables = client_internal.query_api().query(rain_intensity_query)
        for table in tables:
            for record in table.records:
                result["rain_intensity"].append(
                    round(record.get_value(), 1)
                    if record.get_value() is not None
                    else None
                )
                result["rain_intensity_time"].append(record.get_time().isoformat())
        # temp pred

        df = client_internal.query_api().query_data_frame(temp_pred_query)
        if not df.empty:
            result["temp_pred_time"] = [t.isoformat() for t in df["_time"]]
            result["temp_pred_a"] = [
                float(round(v, 1)) if v is not None else None for v in df["A"]
            ]
            result["temp_pred_b"] = [
                float(round(v, 1)) if v is not None else None for v in df["B"]
            ]

        # tsl and rsl second
        tables = client_internal.query_api().query(trsl_query)
        # summit (only rsl is used and since it is positive it is considered as trsl)
        if tech == "summit" or tech == "summit_bt" and len(tables) == 2:
            trsl_a = []
            trsl_b = []
            result["time"] = []
            for table in tables:
                for record in table.records:
                    if ip_a == record.values.get("agent_host"):
                        trsl_a.append(
                            round(record.get_value(), 1)
                            if record.get_value() is not None
                            else None
                        )
                        result["time"].append(record.get_time().isoformat())
                    elif ip_b == record.values.get("agent_host"):
                        trsl_b.append(
                            round(record.get_value(), 1)
                            if record.get_value() is not None
                            else None
                        )
            result["trsl_a"] = trsl_a
            result["trsl_b"] = trsl_b
        # special case for cmls with 4 channels
        elif (
            (tech == "ceragon_ip_10" and len(tables) == 8)
            or (tech == "ceragon_ip_20" and len(tables) == 8)
            or (tech == "ceragon_ip_50" and len(tables) == 8)
        ):
            time = []
            rsl_a = []
            tsl_a = []
            rsl_a2 = []
            tsl_a2 = []
            rsl_b = []
            tsl_b = []
            rsl_b2 = []
            tsl_b2 = []
            for table in tables:
                for i, record in enumerate(table.records):
                    if (
                        ip_a == record.values.get("agent_host")
                        and rsl_string == record.get_field()
                        and "Port 1" in record.values.get("interface-name")
                    ):
                        rsl_a.append(record.get_value())
                        time.append(record.get_time().isoformat())
                    elif (
                        ip_a == record.values.get("agent_host")
                        and tsl_string == record.get_field()
                        and "Port 1" in record.values.get("interface-name")
                    ):
                        tsl_a.append(record.get_value())
                    elif (
                        ip_a == record.values.get("agent_host")
                        and rsl_string == record.get_field()
                        and "Port 2" in record.values.get("interface-name")
                    ):
                        rsl_a2.append(record.get_value())
                    elif (
                        ip_a == record.values.get("agent_host")
                        and tsl_string == record.get_field()
                        and "Port 2" in record.values.get("interface-name")
                    ):
                        tsl_a2.append(record.get_value())

                    elif (
                        ip_b == record.values.get("agent_host")
                        and rsl_string == record.get_field()
                        and "Port 1" in record.values.get("interface-name")
                    ):
                        rsl_b.append(record.get_value())
                    elif (
                        ip_b == record.values.get("agent_host")
                        and tsl_string == record.get_field()
                        and "Port 1" in record.values.get("interface-name")
                    ):
                        tsl_b.append(record.get_value())
                    elif (
                        ip_b == record.values.get("agent_host")
                        and rsl_string == record.get_field()
                        and "Port 2" in record.values.get("interface-name")
                    ):
                        rsl_b2.append(record.get_value())
                    elif (
                        ip_b == record.values.get("agent_host")
                        and tsl_string == record.get_field()
                        and "Port 2" in record.values.get("interface-name")
                    ):
                        tsl_b2.append(record.get_value())
            trsl_a = np.round(
                np.array(tsl_a, dtype=np.float64) - np.array(rsl_a, dtype=np.float64), 1
            )
            trsl_b = np.round(
                np.array(tsl_b, dtype=np.float64) - np.array(rsl_b, dtype=np.float64), 1
            )
            trsl_a2 = np.round(
                np.array(tsl_a2, dtype=np.float64) - np.array(rsl_a2, dtype=np.float64),
                1,
            )
            trsl_b2 = np.round(
                np.array(tsl_b2, dtype=np.float64) - np.array(rsl_b2, dtype=np.float64),
                1,
            )
            result["trsl_a"] = [None if np.isnan(x) else float(x) for x in trsl_a]
            result["trsl_b"] = [None if np.isnan(x) else float(x) for x in trsl_b]
            result["trsl_a2"] = [None if np.isnan(x) else float(x) for x in trsl_a2]
            result["trsl_b2"] = [None if np.isnan(x) else float(x) for x in trsl_b2]
            result["time"] = time
        # rest of the cmls only have 2 channels and the logic is the same for all techs
        else:
            time = []
            rsl_a = []
            tsl_a = []
            rsl_b = []
            tsl_b = []
            for table in tables:
                for i, record in enumerate(table.records):
                    if (
                        ip_a == record.values.get("agent_host")
                        and rsl_string == record.get_field()
                    ):
                        rsl_a.append(record.get_value())
                        time.append(record.get_time().isoformat())
                    elif (
                        ip_a == record.values.get("agent_host")
                        and tsl_string == record.get_field()
                    ):
                        tsl_a.append(record.get_value())
                    elif (
                        ip_b == record.values.get("agent_host")
                        and rsl_string == record.get_field()
                    ):
                        rsl_b.append(record.get_value())
                    elif (
                        ip_b == record.values.get("agent_host")
                        and tsl_string == record.get_field()
                    ):
                        tsl_b.append(record.get_value())
            trsl_a = np.round(
                np.array(tsl_a, dtype=np.float64) - np.array(rsl_a, dtype=np.float64), 1
            )
            trsl_b = np.round(
                np.array(tsl_b, dtype=np.float64) - np.array(rsl_b, dtype=np.float64), 1
            )
            result["trsl_a"] = [None if np.isnan(x) else float(x) for x in trsl_a]
            result["trsl_b"] = [None if np.isnan(x) else float(x) for x in trsl_b]
            result["time"] = time
        return jsonify(result)
    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500
