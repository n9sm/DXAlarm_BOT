#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
import json
import telnetlib
import requests
import re
import logging
from datetime import datetime, timedelta

CONFIG_FILE = "config.json"

# --- Logging ---
logging.basicConfig(
    filename="dxbot.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# dedup in memory
last_spots = {}

# --- Utility ---
def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def send_telegram(token, chat_ids, text):
    if not isinstance(chat_ids, list):
        chat_ids = [chat_ids]
    for chat_id in chat_ids:
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                timeout=10
            )
        except Exception as e:
            logging.error(f"Telegram Error chat_id {chat_id}: {e}")

def normalize_call(c):
    return re.sub(r'[^A-Z0-9/]', '', c.upper())

def parse_ve7cc_line(line):
    parts = line.split("^")
    if len(parts) < 7:
        return None
    freq = parts[1] or "?"
    call = parts[2] or "?"
    date = parts[3] or ""
    time_utc = parts[4] or ""
    info = parts[5] or ""
    spotter = parts[6] or "?"
    return {
        "freq": freq,
        "call": call,
        "datetime": f"{date} {time_utc}",
        "info": info,
        "spotter": spotter,
        "band": freq_to_band(freq),
        "mode": extract_mode(info),
    }

def freq_to_band(freq_str):
    try:
        freq = float(freq_str)
    except ValueError:
        return "?"
    bands = [
        (1800, 2000, "160m"),
        (3500, 3800, "80m"),
        (5300, 5400, "60m"),
        (7000, 7200, "40m"),
        (10100, 10150, "30m"),
        (14000, 14350, "20m"),
        (18068, 18168, "17m"),
        (21000, 21450, "15m"),
        (24890, 24990, "12m"),
        (28000, 29700, "10m"),
        (50000, 54000, "6m")
    ]
    for low, high, band in bands:
        if low <= freq <= high:
            return band
    return "?"

def extract_mode(info_str):
    info = info_str.upper()
    for m in ["CW", "FT8", "RTTY"]:
        if m in info:
            return m
    if any(s in info for s in ["SSB", "USB", "LSB"]):
        return "SSB"
    return "?"

def matches_target(parsed, target):
    call_n = normalize_call(parsed["call"])
    t_call = normalize_call(target.get("call", ""))
    if call_n != t_call:
        return False
    bands = [b.upper() for b in target.get("bands", [])]
    modes = [m.upper() for m in target.get("modes", [])]
    if bands and parsed["band"].upper() not in bands:
        return False
    if modes and parsed["mode"].upper() not in modes:
        return False
    return True

def should_send(call, dedup_min):
    """Verifies how much time elapsed since last message for given call"""
    now = datetime.utcnow()
    last_time = last_spots.get(call)
    if last_time and now - last_time < timedelta(minutes=dedup_min):
        return False
    last_spots[call] = now
    return True

# --- DXCluster Listener ---
def dxcluster_listener(cfg):
    host = cfg.get("dxcluster_host")
    port = cfg.get("dxcluster_port", 7373)
    token = cfg["telegram_token"]
    chat = cfg["chat_id"]
    targets = cfg["targets"]
    dedup_min = int(cfg.get("dedup_minutes", 30))
    mycall = cfg.get("dxcluster_call", "NOCALL")

    while True:
        try:
            logging.info(f"Connecting to DX cluster {host}:{port} ...")
            tn = telnetlib.Telnet(host, port, timeout=60)
            tn.write((mycall + "\n").encode("utf-8"))
            time.sleep(1)
            for cmd in [b"set/skimmer\n", b"set/ft8\n", b"set/announce on\n", b"set/ve7cc 1\n"]:
                tn.write(cmd)

            # --- watchdog + keepalive ---
            last_activity = datetime.utcnow()
            keepalive_interval = timedelta(minutes=10)   # sends a command every 10min
            max_inactive = timedelta(minutes=15)        # if 15min with no spots -> reconnect

            while True:
                line = tn.read_until(b"\n", timeout=60)
                now = datetime.utcnow()

                if line:
                    text = line.decode("utf-8", errors="replace").strip()
                    if not text:
                        continue
                    last_activity = now

                    if text.startswith("CC"):
                        parsed = parse_ve7cc_line(text)
                        if parsed:
                            for target in targets:
                                if matches_target(parsed, target):
                                    call_n = normalize_call(parsed["call"])
                                    if not should_send(call_n, dedup_min):
                                        continue
                                    msg = (
                                        f"🛰️ <b>Spot DXCluster</b>\n"
                                        f"Station: <b>{parsed['call']}</b>\n"
                                        f"Freq: {parsed['freq']} kHz ({parsed['band']})\n"
                                        f"Mode: {parsed['mode']}\n"
                                        f"Date/Time: {parsed['datetime']}\n"
                                        f"Comment: {parsed['info']}\n"
                                        f"Spotter: {parsed['spotter']}"
                                    )
                                    logging.info(f"Sending Telegram alert for {parsed['call']} {parsed['freq']}")
                                    send_telegram(token, chat, msg)
                    else:
                        logging.debug(f"[DX RAW] {text}")

                # --- KEEPALIVE ---
                if now - last_activity >= keepalive_interval:
                    logging.info("Sending keepalive command to cluster...")
                    tn.write(b"sh/dx\n")
                    last_activity = now

                # --- WATCHDOG ---
                if now - last_activity >= max_inactive:
                    logging.warning("No activity for 15 minutes, reconnecting...")
                    tn.close()
                    break

        except Exception as e:
            logging.error(f"DXCluster Error: {e}")
            time.sleep(10)

# --- Main ---
def main():
    cfg = load_config()
    dxcluster_listener(cfg)

if __name__ == "__main__":
    main()
