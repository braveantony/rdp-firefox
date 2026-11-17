# shellcheck shell=bash
# Sourced by startwm.sh when RDP_MODE=workspace. The account keeps its real
# home (/home is shared with the attached containers, which read the display's
# cookie from ~/.Xauthority); only the runtime dir and the Firefox profiles
# live in this session's directory $S and go away with it.
umask 022
mkdir -m 700 "$S/run"
export XDG_RUNTIME_DIR="$S/run" WORKSPACE_SESSION_DIR="$S"
cd "$HOME" || exit 1

eval "$(dbus-launch --sh-syntax)"

cleanup() {
  kill "$DBUS_SESSION_BUS_PID" 2>/dev/null
  pkill -TERM -P $$ 2>/dev/null
  rm -rf "$S"
}
trap cleanup EXIT
trap 'exit 143' TERM HUP INT

openbox --config-file /opt/desktop/workspace/rc.xml &
fcitx5 >/dev/null 2>&1 &

# The cards and the toolbar; restarted if it ever exits while the desktop is up
while [ -S "/tmp/.X11-unix/X${dnum}" ]; do
  python3 /opt/desktop/workspace/workspace.py &
  wait $!
  sleep 1
done
