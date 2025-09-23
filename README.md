# DX Cluster to Telegram Bot
A lightweight Python script that connects to a DX Cluster node, filters incoming spots, and delivers instant notifications directly to your smartphone via Telegram.  
Ideal for DXers and contesters who want to track specific stations without sitting in front of the radio or computer all day.

---

## Features
- Connects to a DX Cluster node (tested with **ve7cc.net**).
- Filters spots by **callsign**, **band**, and **mode** (defined in `config.json`).
- Deduplication system avoids repeated alerts within a configurable time window (defined in `config.json`).
- Sends formatted alerts via a **Telegram bot** (frequency, mode, timestamp, spotter).
- Lightweight: runs on Raspberry Pi, Linux, or any small server.

---

## Configuration

Edit config.json before running.

- **telegram_token**: Bot API token from BotFather
- **chat_id**: Your Telegram user or group chat ID.
- **targets**: Callsigns, bands, and modes to monitor.
- **dedup_minutes**: Time window to prevent repeated alerts.

---

73 and enjoy DXing.
