# H3 test server

Minimal HTTP/3 server built on [aioquic](https://github.com/aiortc/aioquic).
Used as the target endpoint for the Android client and (later) the
interception proxy.

## Setup

```bash
cd server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Generate a self-signed cert

```bash
python gen_cert.py                  # localhost + 127.0.0.1 + 10.0.2.2 + h3.local
python gen_cert.py --ip 192.168.1.5 # add a LAN IP for a physical Android device
```

This writes `cert.pem` and `key.pem` in the current directory.

The Android app pins to this cert, so after regenerating you must copy
`cert.pem` to `android/app/src/main/res/raw/server_cert.pem` and rebuild.

## Run

```bash
python server.py --host 0.0.0.0 --port 4433
```

## Smoke test from the host

`curl` with HTTP/3 support (curl built against ngtcp2/quiche):

```bash
curl --http3-only -k https://localhost:4433/hello
curl --http3-only -k -X POST --data-binary @somefile https://localhost:4433/echo
curl --http3-only -k https://localhost:4433/info
```

If your curl lacks `--http3`, install one that has it (e.g. via Homebrew
`curl` or `nghttp3`), or use the Android app to test.

## Endpoints

| Method | Path    | Response                                    |
| ------ | ------- | ------------------------------------------- |
| GET    | /       | `{"hello":"world",...}`                     |
| GET    | /hello  | same as `/`                                 |
| POST   | /echo   | echoes the request body                     |
| GET    | /info   | JSON dump of method, path, authority, headers |
