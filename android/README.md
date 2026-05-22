# H3 client (Android)

A minimal Android app that talks HTTP/3 to the local aioquic server using
Cronet (Chromium's HTTP stack).

## Build

Open the `android/` directory in Android Studio (Hedgehog or newer), or
from the command line with a configured Android SDK:

```bash
cd android
./gradlew :app:installDebug   # requires gradle wrapper; see below
```

If there's no `gradlew` yet, generate one once with Android Studio
("Sync Project with Gradle Files") or `gradle wrapper --gradle-version 8.7`
from inside `android/`.

## Wiring up the cert

The app pins to the server's self-signed cert via
`res/xml/network_security_config.xml`, which references `@raw/server_cert`.

After running `python server/gen_cert.py`:

```bash
cp server/cert.pem android/app/src/main/res/raw/server_cert.pem
```

Rebuild and install. Without this step every request will fail with a
`CertPathValidatorException`.

## Pointing at the server

- **Emulator**: leave the default `https://10.0.2.2:4433` — that alias
  maps to the host machine.
- **Physical device on your LAN**: regenerate the cert with your LAN IP
  (`python gen_cert.py --ip 192.168.1.5`), copy `cert.pem` over, and edit
  the URL field in the app to `https://192.168.1.5:4433`.

## Confirming H3 was used

After a request, the `status` line at the top shows the negotiated
protocol — it should read `200 h3 (NN B)`. If you see `h2` or
`http/1.1`, QUIC negotiation failed (firewall on UDP/4433, port
mismatch, or cert pin issue) and Cronet fell back to TCP.

You can also tail the server log; aioquic logs every request and you'll
see them as H3 frames arrive.
