#!/bin/sh
# mm-adbpath-probe.sh - enumerate ADB candidate paths and A/B the workaround.
# Run inside Termux. No patching of node_modules; only filesystem conditions change.
H=/data/data/com.termux/files/home
BIN=/data/data/com.termux/files/usr/bin
M=$H/survival/mobilemcp2
SDK=$H/android-sdk/platform-tools
T=$H/survival/.probe
mkdir -p "$T"

line() { echo "----------------------------------------------------------------"; }

line
echo "[ENV]"
echo "node: $(node -v 2>&1)"
echo "HOME=$HOME"
echo "platform/homedir: $(node -p 'process.platform + " | " + require("os").homedir()' 2>&1)"
echo "ANDROID_HOME=${ANDROID_HOME:-<unset>}"
echo "PATH=$PATH"

line
echo "[STEP 1] does /usr exist at all? (Termux is an FHS variant; prefix is /data/data/com.termux/files/usr)"
ls -ld /usr /usr/bin /usr/local /usr/local/bin 2>&1

line
echo "[STEP 2] candidate list as computed by mobile-use getPotentialADBPaths() else-branch"
for p in /usr/local/bin/adb /usr/bin/adb $H/android-sdk/platform-tools/adb; do
  if [ -e "$p" ]; then echo "  EXISTS   $p"; else echo "  MISSING  $p"; fi
done

line
echo "[STEP 3] baseline run, no workaround"
cd "$M" || exit 1
timeout 8 node node_modules/mobile-mcp/dist/mcp_server.js </dev/null >"$T/b.out" 2>"$T/b.err"
B1=$?
echo "  EXIT=$B1  stderr_bytes=$(wc -c <"$T/b.err")"
sed -n '1,6p' "$T/b.err" | sed 's/^/  | /'

line
echo "[STEP 4] apply workaround: create $SDK/adb -> $BIN/adb"
mkdir -p "$SDK"
ln -sf "$BIN/adb" "$SDK/adb"
ls -l "$SDK/adb" | sed 's/^/  /'

line
echo "[STEP 5] rerun with only the symlink in place (ANDROID_HOME still unset)"
timeout 8 node node_modules/mobile-mcp/dist/mcp_server.js </dev/null >"$T/c.out" 2>"$T/c.err"
C1=$?
echo "  EXIT=$C1  stderr_bytes=$(wc -c <"$T/c.err")"
cat "$T/c.err" | sed 's/^/  | /'

line
echo "[STEP 6] remove workaround, rerun to prove reversibility"
rm -f "$SDK/adb"
rmdir "$SDK" 2>/dev/null
rmdir "$H/android-sdk" 2>/dev/null
timeout 8 node node_modules/mobile-mcp/dist/mcp_server.js </dev/null >"$T/d.out" 2>"$T/d.err"
D1=$?
echo "  EXIT=$D1  stderr_bytes=$(wc -c <"$T/d.err")"
sed -n '1,4p' "$T/d.err" | sed 's/^/  | /'

line
echo "[VERDICT] baseline EXIT=$B1 / with-symlink EXIT=$C1 / after-cleanup EXIT=$D1"
echo "  stdin is /dev/null, so a successfully started server reads EOF and exits cleanly:"
echo "    EXIT=0  -> module load + ADBClient construction succeeded (no throw), handshake reachable"
echo "    EXIT=1  -> threw during module load, server never started"
echo "    EXIT=124 -> survived the 8s timeout (still running), also means no throw"
line
