#!/usr/bin/env bash
# Workspace mode (RDP_MODE=workspace) in a podman pod with three containers:
# this image as the desktop, rdp-vscode and rdp-jupyter in attached mode.
#   bash test/image/workspace.test.sh [image]
# Other images: VSCODE_IMAGE, JUPYTER_IMAGE (default: the :dev builds).
# Logins go through the xrdp login screen; cards and toolbar are clicked with
# the mouse of the RDP client. Screenshots go to test/e2e/out/.
# shellcheck disable=SC1091,SC2015,SC2016  # pass() never fails; single-quoted conditions are eval'd later
set -u
cd "$(dirname "$0")/../.." || exit 1
. test/lib.sh
IMG=${1:-localhost/rdp-firefox:dev}
VSCODE_IMAGE=${VSCODE_IMAGE:-localhost/rdp-vscode:dev}
JUPYTER_IMAGE=${JUPYTER_IMAGE:-localhost/rdp-jupyter:dev}
CLIENT=localhost/rdp-firefox-e2e-client:latest
POD=rdpf-workspace-test
HOMEVOL=rdpf-workspace-home
RUNVOL=rdpf-workspace-run
PORT=33395
OUT=$PWD/test/e2e/out
USERS=$OUT/workspace-users
# The client's screen is 1280x800 (test/e2e/client/login.sh)
W=1280; H=800; BAR=64
CARD_Y=$((H / 2)); CARD_TKADM=288; CARD_VSCODE=640; CARD_JUPYTER=992
BAR_Y=$((H - BAR / 2)); BAR_TKADM=100; BAR_VSCODE=276; BAR_JUPYTER=452; BAR_FIREFOX=628
# busybox pgrep -x does not match Firefox by name; match its command line
FIREFOX_RE='^/usr/lib/firefox/firefox '
mkdir -p "$OUT"
printf 'alice:alice-pw\nbob:bob-pw\n' > "$USERS"; chmod 644 "$USERS"

cleanup() {
  podman rm -f -t 0 rdpf-ws-alice rdpf-ws-bob rdpf-ws-solo >/dev/null 2>&1
  podman pod rm -f -t 0 "$POD" >/dev/null 2>&1
  podman volume rm -f "$HOMEVOL" "$RUNVOL" >/dev/null 2>&1
}
trap cleanup EXIT
cleanup

wait_for() {  # wait_for <seconds> <bash condition>
  local end=$((SECONDS + $1))
  while :; do
    eval "$2" && return 0
    [ "$SECONDS" -ge "$end" ] && return 1
    sleep 1
  done
}
dx() { podman exec "$POD-desktop" bash -c "$1"; }
vx() { podman exec "$POD-vscode" bash -c "$1"; }
jx() { podman exec "$POD-jupyter" bash -c "$1"; }
login() {  # login <account> <client display>
  podman rm -f -t 0 "rdpf-ws-$1" >/dev/null 2>&1
  podman run -d --name "rdpf-ws-$1" --network host -v "$OUT:/out:Z" \
    "$CLIENT" "127.0.0.1:$PORT" "$1" "$1-pw" "workspace-$1" "$2" >/dev/null
}
click() {  # click <account> <client display> <x> <y>
  podman exec "rdpf-ws-$1" sh -c "DISPLAY=$2 xdotool mousemove $3 $4 click 1"
}
shot() {   # shot <account> <client display> <name>
  podman exec "rdpf-ws-$1" sh -c "DISPLAY=$2 xwd -root -silent | magick xwd:- /out/workspace-$3.png"
}
display_of() { dx "ls -ld /tmp/.X11-unix/X* 2>/dev/null | awk -v u=$1 '\$3 == u {print \$NF}' | sed 's|.*/X|:|' | head -1"; }
# The desktop's own view of its windows: "name<TAB>active|-<TAB>WxH<TAB>class"
# per line; name is vscode, tkadm, jupyter, firefox, workspace-home or workspace-bar
windows() { dx "su $1 -s /bin/sh -c 'DISPLAY=$2 XAUTHORITY=/home/$1/.Xauthority python3 /opt/desktop/workspace/workspace.py windows'" 2>/dev/null; }
active() { windows "$1" "$2" | awk -F'\t' '$2 == "active" {print $1}'; }
has_window() { windows "$1" "$2" | awk -F'\t' '{print $1}' | grep -qx "$3"; }
ui_pid() { dx "pgrep -u $1 -f '^python3 /opt/desktop/workspace/workspace.py\$' || true"; }
codium_pids() { vx "pgrep -u $1 -f 'codium.*--user-data-dir' | head -1 || true"; }

podman image exists "$IMG" || { bad "image $IMG not found"; finish; }
for i in "$VSCODE_IMAGE" "$JUPYTER_IMAGE"; do podman image exists "$i" || { bad "image $i not found"; finish; }; done
podman build -q -t "$CLIENT" test/e2e/client >/dev/null || { bad "client build"; finish; }

say invalid-mode
out=$(timeout 20 podman run --rm --name rdpf-ws-solo -e RDP_PASSWORD=x -e RDP_MODE=bogus "$IMG" 2>&1); rc=$?
podman rm -f -t 0 rdpf-ws-solo >/dev/null 2>&1
[ "$rc" -ne 124 ] || rc=0   # still running after 20s: the mode was not rejected
[ "$rc" -ne 0 ] && grep -q "RDP_MODE" <<<"$out" && pass "an unknown RDP_MODE stops the container with a message" \
  || bad "RDP_MODE=bogus: rc=$rc out=$(tail -2 <<<"$out")"

say kiosk-default
# Without RDP_MODE the image behaves as before: a full-screen Firefox per login
podman run -d --name rdpf-ws-solo -p "$PORT:3389" --shm-size 1g -e RDP_USER=alice -e RDP_PASSWORD=alice-pw "$IMG" >/dev/null
sx() { podman exec rdpf-ws-solo bash -c "$1"; }
wait_for 30 'sx "grep -q \"listening to port 3389\" /var/log/xrdp.log" 2>/dev/null' || bad "default mode did not start"
sx 'grep -q "^Policy=Separate" /etc/xrdp/sesman.ini' \
  && pass "every connection still gets its own desktop (Policy=Separate)" || bad "default mode changed sesman's Policy"
login alice :80
wait_for 90 'sx "pgrep -u alice -f \"$FIREFOX_RE\" >/dev/null"' && pass "a login starts Firefox by itself" || bad "no firefox in default mode"
sx '! pgrep -u alice -f workspace.py >/dev/null' && pass "and no workspace desktop" || bad "workspace.py runs in default mode"
sx "su alice -s /bin/sh -c 'readlink /proc/\$(pgrep -u alice -x openbox | head -1)/cwd'" | grep -q '^/tmp/sess/' \
  && pass "with a throwaway home per connection" || bad "kiosk session home is not under /tmp/sess"
podman rm -f -t 0 rdpf-ws-alice rdpf-ws-solo >/dev/null

say pod
podman volume create "$HOMEVOL" >/dev/null; podman volume create "$RUNVOL" >/dev/null
podman pod create --name "$POD" --shm-size 1g -p "$PORT:3389" >/dev/null
common=(-e USERS_FILE=/etc/workspace/users -v "$USERS:/etc/workspace/users:ro,Z" -v "$HOMEVOL:/home" -v "$RUNVOL:/run/rdp-workspace")
podman run -d --pod "$POD" --name "$POD-desktop" -e RDP_MODE=workspace "${common[@]}" "$IMG" >/dev/null
wait_for 30 'dx "grep -q \"listening to port 3389\" /var/log/xrdp.log" 2>/dev/null' && pass "desktop up" || { bad "desktop did not start: $(podman logs "$POD-desktop" 2>&1 | tail -3)"; finish; }
podman run -d --pod "$POD" --name "$POD-vscode" -e RDP_MODE=attached "${common[@]}" "$VSCODE_IMAGE" >/dev/null
podman run -d --pod "$POD" --name "$POD-jupyter" -e RDP_MODE=attached "${common[@]}" "$JUPYTER_IMAGE" >/dev/null
wait_for 30 "dx '[ -S /run/rdp-workspace/vscode.sock ] && [ -S /run/rdp-workspace/jupyter.sock ]'" \
  && pass "both attached containers serve their sockets" || { bad "sockets missing: $(dx 'ls /run/rdp-workspace')"; finish; }
dx 'grep -q "^Policy=Default" /etc/xrdp/sesman.ini' && pass "a reconnect gets the same desktop back (Policy=Default)" || bad "sesman Policy: $(dx 'grep ^Policy= /etc/xrdp/sesman.ini')"
[ "$(vx 'pgrep -x xrdp | wc -l')" = 0 ] && [ "$(jx 'pgrep -x xrdp | wc -l')" = 0 ] && [ "$(dx 'pgrep -x xrdp | wc -l')" -ge 1 ] \
  && pass "one xrdp in the pod (desktop only)" || bad "xrdp outside the desktop container"

say login
login alice :81
wait_for 60 '[ -n "$(display_of alice)" ]' || { bad "no desktop for alice"; finish; }
A=$(display_of alice)
wait_for 30 '[ -n "$(ui_pid alice)" ]' && pass "the workspace desktop runs as alice on $A" || { bad "workspace.py not running: $(dx 'ps -o user,args | grep -v grep | grep -E "workspace|openbox"')"; finish; }
sleep 5; shot alice :81 1-home
has_window alice "$A" workspace-home && pass "the home screen is shown" || bad "no home window: $(windows alice "$A" | tr '\n' ' ')"
! has_window alice "$A" workspace-bar && pass "no toolbar before a tool is open" || bad "toolbar shown on the home screen"
[ -z "$(dx "pgrep -u alice -f '$FIREFOX_RE' || true")" ] && pass "Firefox does not start by itself" || bad "firefox already running"
dx "su alice -s /bin/sh -c 'readlink /proc/\$(pgrep -u alice -x openbox | head -1)/cwd'" | grep -qx /home/alice && pass "the session uses the account's real home" || bad "session home is not /home/alice"
dx '[ "$(stat -c %a /home/alice)" = 700 ]' && dx "! su bob -s /bin/sh -c 'ls /home/alice' >/dev/null 2>&1" && pass "other accounts cannot read alice's home" || bad "/home/alice mode $(dx 'stat -c %a /home/alice')"

say open-vscode
click alice :81 $CARD_VSCODE $CARD_Y
wait_for 60 '[ -n "$(codium_pids alice)" ]' && pass "the VSCodium card starts VSCodium in the vscode container, as alice" || bad "no codium for alice: $(podman logs "$POD-vscode" 2>&1 | tail -3)"
wait_for 60 'has_window alice "$A" vscode' && pass "its window is on alice's desktop" || bad "no VSCodium window: $(windows alice "$A" | tr '\n' ' ')"
wait_for 10 'has_window alice "$A" workspace-bar' && pass "the toolbar appears" || bad "no toolbar after a tool opened"
sleep 3; shot alice :81 2-vscode
[ "$(active alice "$A")" = vscode ] && pass "VSCodium is the active window" || bad "active: $(active alice "$A")"
windows alice "$A" | awk -F'\t' -v want="${W}x$((H - BAR))" '$1 == "vscode" && $3 == want {ok = 1} END {exit !ok}' \
  && pass "the window leaves the toolbar's $BAR px free (${W}x$((H - BAR)))" || bad "VSCodium size: $(windows alice "$A" | grep vscode)"

say toolbar
click alice :81 $BAR_TKADM $BAR_Y
wait_for 40 'has_window alice "$A" tkadm' && pass "the toolbar's tkadm item opens the tkadm window" || bad "no tkadm window: $(windows alice "$A" | tr '\n' ' ')"
wait_for 10 '[ "$(active alice "$A")" = tkadm ]' && pass "and it becomes the active window" || bad "active: $(active alice "$A")"
c1=$(codium_pids alice)
click alice :81 $BAR_VSCODE $BAR_Y
wait_for 10 '[ "$(active alice "$A")" = vscode ]' && pass "the VSCodium item switches back to it" || bad "active after clicking VSCodium: $(active alice "$A")"
sleep 3; [ -n "$c1" ] && [ "$(codium_pids alice)" = "$c1" ] && pass "without starting a second VSCodium" || bad "codium before [$c1] after [$(codium_pids alice)]"
click alice :81 $BAR_JUPYTER $BAR_Y
wait_for 90 '[ -n "$(jx "pgrep -u alice -f \"^/opt/JupyterLab/jupyterlab-desktop\" || true")" ]' && pass "the JupyterLab item starts JupyterLab in the jupyter container" || bad "no JupyterLab for alice: $(podman logs "$POD-jupyter" 2>&1 | tail -3)"
wait_for 90 'has_window alice "$A" jupyter' && pass "its window is on alice's desktop" || bad "no JupyterLab window: $(windows alice "$A" | tr '\n' ' ')"
click alice :81 $BAR_FIREFOX $BAR_Y
wait_for 40 'has_window alice "$A" firefox' && pass "the Firefox item opens Firefox" || bad "no Firefox window: $(windows alice "$A" | tr '\n' ' ')"
sleep 2; shot alice :81 3-all-open

say chinese-input
# fcitx5 + chewing: Ctrl+Space switches to 注音, "su3cl3" is ㄋㄧˇㄏㄠˇ (你好).
# The result is checked by eye on the screenshot.
click alice :81 $BAR_FIREFOX $BAR_Y; sleep 2
podman exec rdpf-ws-alice sh -c 'DISPLAY=:81 xdotool key ctrl+l; sleep 1; DISPLAY=:81 xdotool key ctrl+space; sleep 1; for k in s u 3 c l 3; do DISPLAY=:81 xdotool key $k; sleep 0.3; done; sleep 1; DISPLAY=:81 xdotool key Return; sleep 1'
shot alice :81 3b-chinese-input
podman exec rdpf-ws-alice sh -c 'DISPLAY=:81 xdotool key ctrl+space; DISPLAY=:81 xdotool key Escape'
pass "screenshot saved: workspace-3b-chinese-input.png (check 你好 in the address bar)"

say theme
dx '[ ! -e /home/alice/.config/rdp-workspace/theme ]' && pass "light until the user chooses" || bad "theme file exists before a toggle"
click alice :81 $((W - 40)) $BAR_Y
wait_for 10 'dx "grep -qx dark /home/alice/.config/rdp-workspace/theme 2>/dev/null"' && pass "the toggle switches to dark and remembers it" || bad "theme: $(dx 'cat /home/alice/.config/rdp-workspace/theme 2>&1')"
sleep 1; shot alice :81 4-dark
click alice :81 $((W - 40)) $BAR_Y
wait_for 10 'dx "grep -qx light /home/alice/.config/rdp-workspace/theme"' && pass "and back to light" || bad "theme after second toggle: $(dx 'cat /home/alice/.config/rdp-workspace/theme')"

say two-accounts
login bob :82
wait_for 60 '[ -n "$(display_of bob)" ]' || bad "no desktop for bob"
B=$(display_of bob)
[ -n "$B" ] && [ "$B" != "$A" ] && pass "bob gets his own desktop ($B)" || bad "bob's display: [$B], alice's: [$A]"
wait_for 30 'has_window bob "$B" workspace-home' && pass "bob sees the home screen" || bad "bob has no home window"
! has_window bob "$B" vscode && pass "alice's VSCodium is not on bob's desktop" || bad "bob sees a VSCodium window"
click bob :82 $CARD_VSCODE $CARD_Y
wait_for 60 '[ -n "$(codium_pids bob)" ]' && pass "bob's card starts a VSCodium of his own" || bad "no codium for bob"
[ "$(codium_pids alice)" = "$c1" ] && pass "alice's VSCodium is untouched" || bad "alice's codium changed"
wait_for 60 'has_window bob "$B" vscode' && pass "bob's VSCodium window is on bob's desktop" || bad "no VSCodium window for bob"
shot bob :82 5-bob

say reconnect
u1=$(ui_pid alice)
podman rm -f -t 0 rdpf-ws-alice >/dev/null; sleep 5
login alice :83
sleep 40
[ "$(display_of alice)" = "$A" ] && pass "alice is back on the same display ($A)" || bad "display after reconnect: $(display_of alice)"
[ -n "$u1" ] && [ "$(ui_pid alice)" = "$u1" ] && pass "the desktop was not restarted" || bad "workspace.py before [$u1] after [$(ui_pid alice)]"
[ "$(codium_pids alice)" = "$c1" ] && has_window alice "$A" vscode && pass "VSCodium is still open" || bad "VSCodium lost on reconnect"
podman exec rdpf-ws-alice sh -c 'DISPLAY=:83 xwd -root -silent | magick xwd:- /out/workspace-6-reconnected.png'

finish
