#!/usr/bin/env python3
"""
Interactive & Scriptable End-to-End Test Data Generator for ForestGuard AI.

Sends customized IoT sensor telemetry to the TCP Ingestion listener (Port 20000)
using the authentic ZProtocol binary format, waits for real-time AI inference,
and queries the Web Dashboard API (Port 8000) to verify that the telemetry
and calculated risk levels appear on the Leaflet map.
"""

import sys
import time
import struct
import socket
import argparse
import urllib.request
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.ingestion.protocol.zprotocol import encode_zprotocol, ROLE_MASTER


def build_sensor_payload(
    eco2: int = 400,
    ech2o: int = 10,
    tvoc: int = 50,
    pm25: int = 15,
    pm10: int = 25,
    temperature: float = 22.5,
    humidity: float = 45.0,
    latitude: float = 49.2827,
    longitude: float = -123.1207,
    altitude: int = 85,
    satellites: int = 9,
    fix_quality: int = 1,
    smoke: float = 0.05,
    nh3: float = 0.12,
    h2s: float = 0.08,
    rain: int = 0,
    battery: float = 4.15
) -> bytes:
    """Build the 41-byte binary sensor telemetry payload matching hardware specification."""
    temp_raw = int(round(temperature * 10.0))
    hum_raw = int(round(humidity * 10.0))
    lat_raw = int(round(latitude * 1e7))
    lng_raw = int(round(longitude * 1e7))
    timestamp = int(time.time())

    smoke_raw = int(round(smoke * 1000.0))
    nh3_raw = int(round(nh3 * 1000.0))
    h2s_raw = int(round(h2s * 1000.0))
    rain_raw = int(rain)
    bat_raw = int(round(battery * 1000.0))

    # Bit 0 = Air Quality Valid, Bit 1 = GPS Valid
    flags = 0x03

    payload = struct.pack(
        "<HHHHHhHiiHBBIHHHHHB",
        eco2,
        ech2o,
        tvoc,
        pm25,
        pm10,
        temp_raw,
        hum_raw,
        lat_raw,
        lng_raw,
        altitude,
        satellites,
        fix_quality,
        timestamp,
        smoke_raw,
        nh3_raw,
        h2s_raw,
        rain_raw,
        bat_raw,
        flags
    )
    return payload


def build_tcp_frame(imei: str, iccid: str, sensor_payload: bytes) -> bytes:
    """
    Wrap sensor payload with TCP prefix and ZProtocol frame.
    Format: [IMEI_LEN (1B)][IMEI][ICCID_LEN (1B)][ICCID][PAYLOAD_LEN (2B big-endian)][PAYLOAD]
    """
    imei_bytes = imei.encode('ascii')
    iccid_bytes = iccid.encode('ascii')

    prefix_data = bytearray()
    prefix_data.append(len(imei_bytes))
    prefix_data.extend(imei_bytes)
    prefix_data.append(len(iccid_bytes))
    prefix_data.extend(iccid_bytes)
    prefix_data.extend(struct.pack(">H", len(sensor_payload)))
    prefix_data.extend(sensor_payload)

    # Wrap in ZProtocol with command 0x31 (Sensor Data)
    zframe = encode_zprotocol(
        role=ROLE_MASTER,
        msg_id=int(time.time()) % 65535,
        command=0x31,
        data=bytes(prefix_data)
    )
    return zframe


def send_packet(host: str, port: int, packet: bytes, timeout: float = 5.0):
    """Connect to TCP listener and transmit packet."""
    print(f"[*] Connecting to Ingestion Service at {host}:{port}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect((host, port))
    print(f"[+] Connected! Sending {len(packet)} bytes (ZProtocol frame)...")
    sock.sendall(packet)
    time.sleep(0.5)
    sock.close()
    print("[+] Transmission complete and socket closed.")


def query_dashboard_api(host: str, web_port: int, imei: str) -> dict:
    """Query Web Backend API to check the latest processed record for the device."""
    url = f"http://{host}:{web_port}/api/data"
    print(f"[*] Querying Web Backend API: {url} ...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'ForestGuard-Test'})
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            for record in data:
                if str(record.get('device_imei')) == str(imei):
                    return record
    except Exception as e:
        print(f"[-] Failed to query API: {e}")
    return {}


def main():
    parser = argparse.ArgumentParser(description="Send customized test data to ForestGuard AI")
    parser.add_argument("--host", type=str, default="localhost", help="Server host (default: localhost)")
    parser.add_argument("--tcp-port", type=int, default=20000, help="Ingestion TCP port (default: 20000)")
    parser.add_argument("--web-port", type=int, default=8000, help="Web Dashboard port (default: 8000)")
    parser.add_argument("--imei", type=str, default="860000000000001", help="Device IMEI (default: 860000000000001)")
    parser.add_argument("--iccid", type=str, default="89860401101990000000", help="SIM ICCID")
    parser.add_argument("--preset", choices=["normal", "warning", "alert", "custom"], default="alert",
                        help="Scenario preset: normal (safe green), warning (yellow), alert (red fire)")
    parser.add_argument("--eco2", type=int, default=None, help="eCO2 in ppm")
    parser.add_argument("--tvoc", type=int, default=None, help="TVOC in ppb")
    parser.add_argument("--temp", type=float, default=None, help="Temperature in °C")
    parser.add_argument("--hum", type=float, default=None, help="Humidity in %")
    parser.add_argument("--smoke", type=float, default=None, help="Smoke sensor reading (mV/V)")
    parser.add_argument("--lat", type=float, default=49.2827, help="Latitude coordinate (default: 49.2827 Vancouver)")
    parser.add_argument("--lng", type=float, default=-123.1207, help="Longitude coordinate (default: -123.1207 Vancouver)")

    args = parser.parse_args()

    # Preset configurations
    presets = {
        "normal": {
            "eco2": 410, "ech2o": 10, "tvoc": 45, "pm25": 12, "pm10": 20,
            "temperature": 19.5, "humidity": 55.0, "smoke": 0.02,
            "nh3": 0.05, "h2s": 0.03, "rain": 0, "battery": 4.18
        },
        "warning": {
            "eco2": 1100, "ech2o": 25, "tvoc": 450, "pm25": 65, "pm10": 95,
            "temperature": 28.0, "humidity": 30.0, "smoke": 0.35,
            "nh3": 0.40, "h2s": 0.25, "rain": 0, "battery": 4.05
        },
        "alert": {
            "eco2": 2600, "ech2o": 50, "tvoc": 1800, "pm25": 220, "pm10": 350,
            "temperature": 39.5, "humidity": 18.0, "smoke": 0.85,
            "nh3": 0.95, "h2s": 0.80, "rain": 0, "battery": 3.95
        }
    }

    config = presets.get(args.preset, presets["normal"]).copy()

    # Apply overrides
    if args.eco2 is not None:
        config["eco2"] = args.eco2
    if args.tvoc is not None:
        config["tvoc"] = args.tvoc
    if args.temp is not None:
        config["temperature"] = args.temp
    if args.hum is not None:
        config["humidity"] = args.hum
    if args.smoke is not None:
        config["smoke"] = args.smoke

    print("=" * 70)
    print("🌲 ForestGuard AI - End-to-End Test Telemetry Dispatcher")
    print("=" * 70)
    print(f"Target Server:    {args.host}")
    print(f"Ingestion Port:   {args.tcp_port} (TCP / ZProtocol)")
    print(f"Dashboard Port:   {args.web_port} (HTTP / Web)")
    print(f"Device IMEI:      {args.imei}")
    print(f"Coordinates:      ({args.lat:.4f}, {args.lng:.4f})")
    print(f"Scenario Preset:  {args.preset.upper()}")
    print(f"Sensor Values:    eCO2={config['eco2']}ppm, TVOC={config['tvoc']}ppb, "
          f"Temp={config['temperature']}°C, Hum={config['humidity']}%, Smoke={config['smoke']}V")
    print("=" * 70)

    # 1. Build and transmit packet
    payload = build_sensor_payload(
        eco2=config["eco2"],
        ech2o=config["ech2o"],
        tvoc=config["tvoc"],
        pm25=config["pm25"],
        pm10=config["pm10"],
        temperature=config["temperature"],
        humidity=config["humidity"],
        latitude=args.lat,
        longitude=args.lng,
        smoke=config["smoke"],
        nh3=config["nh3"],
        h2s=config["h2s"],
        rain=config["rain"],
        battery=config["battery"]
    )

    frame = build_tcp_frame(args.imei, args.iccid, payload)
    send_packet(args.host, args.tcp_port, frame)

    # 2. Wait for real-time pipeline processing (TCP Ingestion -> DB -> AI Service -> Web Callback)
    print("\n[*] Waiting 3 seconds for asynchronous AI pipeline execution...")
    time.sleep(3.0)

    # 3. Query Web Backend
    rec = query_dashboard_api(args.host, args.web_port, args.imei)

    print("\n" + "=" * 70)
    print("🔍 Verification & Result on Live Map Dashboard")
    print("=" * 70)
    if rec:
        print(f"[✓] Record found in database!")
        print(f"    - Database Record ID: {rec.get('id')}")
        print(f"    - Device IMEI:        {rec.get('device_imei')}")
        print(f"    - Received At:        {rec.get('received_at')}")
        print(f"    - Coordinates:        Lat={rec.get('latitude')}, Lng={rec.get('longitude')}")
        print(f"    - AI-1 Score:         {rec.get('ai1')} (XGBoost Environmental Risk)")
        print(f"    - AI-2 Score:         {rec.get('ai2')} (CNN Visual Verification)")
        print(f"    - Final Risk Level:   {rec.get('final_risk_level')} (Badge Color: {rec.get('final_risk_level', 'green').upper()})")
        print(f"\n[✓] Map URL: http://{args.host}:{args.web_port}/")
        print("    Open the URL in your browser to view your test marker live on the map!")
    else:
        print("[-] Notice: Record not immediately returned by /api/data top 100 or query timed out.")
        print(f"    Please check Web Dashboard directly at: http://{args.host}:{args.web_port}/")
    print("=" * 70)


if __name__ == "__main__":
    main()
