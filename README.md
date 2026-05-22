# quic-h3-proxy

Building a Burp-style interception proxy that can inspect HTTP/2 *and*
HTTP/3 (QUIC) traffic. The repo is being built in stages:

1. **`server/`** — a minimal aioquic HTTP/3 test server. *(current)*
2. **`android/`** — an Android app using Cronet to issue HTTP/3 requests
   against the server, with the server's cert pinned. *(current)*
3. **`proxy/`** — MITM proxy that terminates QUIC/TLS from the client,
   re-establishes a QUIC connection to the real server, and logs every
   request/response. *(next)*

## Quickstart

```bash
# 1. Server: generate cert + run
cd server
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python gen_cert.py
python server.py --host 0.0.0.0 --port 4433

# 2. Android: copy the cert and build
cp ../server/cert.pem ../android/app/src/main/res/raw/server_cert.pem
# open ../android in Android Studio, install on emulator, hit "GET /hello"
```

The app's status line will show `200 h3 (..B)` when HTTP/3 is actually
being negotiated (rather than falling back to HTTP/2 over TCP). The
server log mirrors every request.

## Why this exists

Burp Suite, mitmproxy and friends still don't do QUIC well. The goal is
to have a hackable Python codebase where the QUIC interception layer is
visible and modifiable, so we can experiment with H3-specific things
(0-RTT capture, DATAGRAM frame inspection, MASQUE, etc.) without
fighting a black box.

## Constraints worth knowing up front

- **Android trust store**: Android API 24+ ignores user-installed CAs
  for app traffic unless the app opts in via
  `network_security_config.xml`. The included config opts in for *debug*
  builds, which is what makes the future MITM step feasible against
  *this* app. It won't help against third-party apps without root.
- **QUIC proxy discovery**: there's no equivalent of an HTTP CONNECT
  proxy for QUIC in shipping browsers/Cronet. The simplest setup is to
  point the client directly at the proxy's IP (the proxy then dials the
  real upstream). RFC 9298 `CONNECT-UDP` exists and Cronet supports it,
  but configuring it is annoying — we'll start with direct-routing.
