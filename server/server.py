"""Minimal HTTP/3 server built on aioquic.

Endpoints:
  GET  /             -> JSON banner
  GET  /hello        -> JSON {hello: world}
  POST /echo         -> echoes the request body back
  GET  /info         -> JSON describing the incoming request

Run:
  python gen_cert.py
  python server.py --host 0.0.0.0 --port 4433
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from typing import Dict, Optional

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import DataReceived, H3Event, HeadersReceived
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent

log = logging.getLogger("h3-server")


class RequestState:
    __slots__ = ("authority", "method", "path", "headers", "body", "done")

    def __init__(self, authority: str, method: str, path: str, headers: list):
        self.authority = authority
        self.method = method
        self.path = path
        self.headers = headers
        self.body = bytearray()
        self.done = False


def _route(req: RequestState) -> tuple[int, str, bytes]:
    if req.path in ("/", "/hello"):
        body = json.dumps(
            {"hello": "world", "method": req.method, "path": req.path}
        ).encode()
        return 200, "application/json", body
    if req.path == "/echo":
        return 200, "application/octet-stream", bytes(req.body) or b"(empty)\n"
    if req.path == "/info":
        body = json.dumps(
            {
                "method": req.method,
                "path": req.path,
                "authority": req.authority,
                "body_len": len(req.body),
                "headers": [[k.decode(), v.decode()] for k, v in req.headers],
            },
            indent=2,
        ).encode()
        return 200, "application/json", body
    return 404, "text/plain", b"not found\n"


class H3ServerProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._h3: Optional[H3Connection] = None
        self._requests: Dict[int, RequestState] = {}

    def quic_event_received(self, event: QuicEvent) -> None:
        if self._h3 is None:
            self._h3 = H3Connection(self._quic)
        for h3_event in self._h3.handle_event(event):
            self._handle_h3(h3_event)

    def _handle_h3(self, event: H3Event) -> None:
        if isinstance(event, HeadersReceived):
            authority = method = path = ""
            for k, v in event.headers:
                if k == b":authority":
                    authority = v.decode()
                elif k == b":method":
                    method = v.decode()
                elif k == b":path":
                    path = v.decode()
            req = RequestState(authority, method, path, event.headers)
            self._requests[event.stream_id] = req
            if event.stream_ended:
                self._respond(event.stream_id, req)
        elif isinstance(event, DataReceived):
            req = self._requests.get(event.stream_id)
            if req is None:
                return
            req.body.extend(event.data)
            if event.stream_ended:
                self._respond(event.stream_id, req)

    def _respond(self, stream_id: int, req: RequestState) -> None:
        if req.done:
            return
        req.done = True
        status, ctype, body = _route(req)
        log.info(
            "%s %s %s -> %d (%dB)", req.authority, req.method, req.path, status, len(body)
        )
        assert self._h3 is not None
        self._h3.send_headers(
            stream_id=stream_id,
            headers=[
                (b":status", str(status).encode()),
                (b"content-type", ctype.encode()),
                (b"content-length", str(len(body)).encode()),
                (b"server", b"aioquic-h3-demo"),
                (b"alt-svc", b'h3=":4433"'),
            ],
        )
        self._h3.send_data(stream_id=stream_id, data=body, end_stream=True)
        self.transmit()


async def main(host: str, port: int, cert: str, key: str) -> None:
    config = QuicConfiguration(
        alpn_protocols=H3_ALPN,
        is_client=False,
        max_datagram_frame_size=65536,
    )
    config.load_cert_chain(cert, key)

    log.info("H3 server listening on udp://%s:%d", host, port)
    await serve(host, port, configuration=config, create_protocol=H3ServerProtocol)
    await asyncio.Future()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=4433)
    p.add_argument("--cert", default="cert.pem")
    p.add_argument("--key", default="key.pem")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        asyncio.run(main(args.host, args.port, args.cert, args.key))
    except KeyboardInterrupt:
        pass
