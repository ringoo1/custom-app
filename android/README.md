# H3 client (Android)

A minimal Android app that talks HTTP/3 to the local aioquic server using
Cronet (Chromium's HTTP stack).

## Build

Open the `android/` directory in Android Studio (Hedgehog or newer), or
from the command line with a configured Android SDK:

```bash
cd android
./gradlew :app:assembleDebug   # APK at app/build/outputs/apk/debug/app-debug.apk
./gradlew :app:installDebug    # build + adb install in one go
```

The gradle wrapper is checked in, so no system gradle is required — just
JDK 17 and an Android SDK with `ANDROID_HOME` (or `ANDROID_SDK_ROOT`) set.

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

### One-shot install for a USB-connected phone

There's a helper that does the cert + build + adb install dance:

```bash
./scripts/install-to-device.sh 192.168.1.42   # your dev box's LAN IP
```

This regenerates `cert.pem` with that IP in the SAN list, copies it into
`res/raw/server_cert.pem`, patches the default base URL in `strings.xml`,
builds the debug APK, and runs `adb install -r`. Then start the server
on the host:

```bash
cd server && .venv/bin/python server.py --host 0.0.0.0 --port 4433
```

Make sure UDP/4433 is open on the host firewall (e.g. `sudo ufw allow
4433/udp` on Ubuntu) and that the phone is on the same WiFi as the dev
box. **`adb reverse` cannot tunnel UDP**, so a USB-only setup will not
work for QUIC — the phone must reach the host over IP.

### Rooted-phone-specific notes

Root isn't required to run this app or test HTTP/3 against the dev
server — the cert is pinned in `network_security_config.xml` via the
bundled `@raw/server_cert`, which works on stock Android.

Root will matter for the **next** step (MITM proxy). On a rooted phone
you can drop the proxy's CA into the system trust store so *every* app
trusts it without modification:

```bash
# (later, once the proxy exists)
HASH=$(openssl x509 -in proxy-ca.pem -inform pem -subject_hash_old -noout)
adb push proxy-ca.pem /sdcard/${HASH}.0
adb shell
$ su
# mount -o rw,remount /system            # or use magisk's modules dir
# mv /sdcard/${HASH}.0 /system/etc/security/cacerts/
# chmod 644 /system/etc/security/cacerts/${HASH}.0
# reboot
```

On Android 14+ the `cacerts` dir is on the APEX-mounted
`com.android.conscrypt` module — Magisk's "Move Certificates" or
"AlwaysTrustUserCerts" modules are the cleanest path there. For *this*
app we don't need any of that, because the debug network config already
allows user-installed CAs.

## Confirming H3 was used

After a request, the `status` line at the top shows the negotiated
protocol — it should read `200 h3 (NN B)`. If you see `h2` or
`http/1.1`, QUIC negotiation failed (firewall on UDP/4433, port
mismatch, or cert pin issue) and Cronet fell back to TCP.

You can also tail the server log; aioquic logs every request and you'll
see them as H3 frames arrive.
