#!/usr/bin/env bash
# install-to-device.sh — regenerate the server cert with your LAN IP, copy it
# into the Android app, build a debug APK, and push it to a USB-connected
# device.
#
# Usage:
#   ./scripts/install-to-device.sh <host-lan-ip>
#
# Example:
#   ./scripts/install-to-device.sh 192.168.1.42
#
# Pre-reqs:
#   - adb on PATH; device with USB debugging enabled (`adb devices` lists it)
#   - Android SDK installed; ANDROID_HOME or ANDROID_SDK_ROOT exported
#   - python venv at server/.venv with requirements.txt installed
#
# Notes for a rooted phone specifically:
#   - Root isn't required to install the app or run HTTP/3 against the dev box.
#   - Root *is* useful for the upcoming proxy step (install the MITM CA into
#     /system/etc/security/cacerts so apps trust it without rebuild).
#   - `adb reverse` cannot tunnel UDP, so the phone must reach the dev box on
#     the LAN. Put both on the same WiFi (or run a hotspot from the dev box).

set -euo pipefail

if [ $# -ne 1 ]; then
  echo "usage: $0 <host-lan-ip>" >&2
  echo "  e.g. $0 192.168.1.42" >&2
  exit 2
fi

HOST_IP="$1"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVER_DIR="$REPO_ROOT/server"
ANDROID_DIR="$REPO_ROOT/android"

cd "$SERVER_DIR"

if [ ! -x .venv/bin/python ]; then
  echo "==> creating server venv"
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi

echo "==> regenerating cert with SAN ${HOST_IP}"
.venv/bin/python gen_cert.py --ip "$HOST_IP"

echo "==> copying cert into android resources"
cp cert.pem "$ANDROID_DIR/app/src/main/res/raw/server_cert.pem"

echo "==> patching default base URL to https://${HOST_IP}:4433"
# Only touch the dev default; the user can still override at runtime.
sed -i.bak \
  -E "s|<string name=\"default_base_url\">[^<]*</string>|<string name=\"default_base_url\">https://${HOST_IP}:4433</string>|" \
  "$ANDROID_DIR/app/src/main/res/values/strings.xml"
rm -f "$ANDROID_DIR/app/src/main/res/values/strings.xml.bak"

cd "$ANDROID_DIR"
echo "==> building debug APK"
./gradlew :app:assembleDebug

APK="$ANDROID_DIR/app/build/outputs/apk/debug/app-debug.apk"
if [ ! -f "$APK" ]; then
  echo "build did not produce $APK" >&2
  exit 1
fi

echo "==> installing to device"
adb install -r -t "$APK"

echo
echo "Done."
echo "  - Start the server:  cd server && .venv/bin/python server.py --host 0.0.0.0 --port 4433"
echo "  - Make sure UDP/4433 is allowed by your host firewall."
echo "  - On the phone, launch \"H3 Client\" and hit GET /hello."
echo "  - Status line should read '200 h3 (..B)'."
