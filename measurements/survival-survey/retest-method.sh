#!/system/bin/sh
NPMROOT=/data/data/com.termux/files/home/.npm/_npx/9833c18b2d85bc59/node_modules
echo ===VERSIONS===
grep -m1 '"version"' $NPMROOT/@playwright/mcp/package.json
grep -m1 '"version"' $NPMROOT/playwright-core/package.json
INIT='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}'
NOTIF='{"jsonrpc":"2.0","method":"notifications/initialized"}'
LIST='{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
cd /data/data/com.termux/files/home
echo ===TEST2_ENV0===
printf '%s\n%s\n%s\n' "$INIT" "$NOTIF" "$LIST" | PLAYWRIGHT_BROWSERS_PATH=0 timeout 90 npx -y @playwright/mcp@latest > pw2.out 2>&1
echo EXIT2=$?
grep -oE '"name":"browser_[a-z_]+"' pw2.out | sort -u | wc -l
head -c 300 pw2.out
echo
echo ===TEST3_HOMEPW===
printf '%s\n%s\n%s\n' "$INIT" "$NOTIF" "$LIST" | PLAYWRIGHT_BROWSERS_PATH=$HOME/pw-browsers timeout 90 npx -y @playwright/mcp@latest > pw3.out 2>&1
echo EXIT3=$?
grep -oE '"name":"browser_[a-z_]+"' pw3.out | sort -u | wc -l
head -c 300 pw3.out
echo
echo ===SHIPPED_SRC===
sed -n '33896,33912p' $NPMROOT/playwright-core/lib/coreBundle.js
echo ---CALLSITE---
sed -n '34350,34370p' $NPMROOT/playwright-core/lib/coreBundle.js
echo ===ALLDONE===
