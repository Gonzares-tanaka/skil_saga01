#!/bin/sh
# Copy to plumOS roms/ports and run from Ports. No installs or game/save edits.
# Python location: https://github.com/game-de-it/plumOS-pixel2#pyxelについて
probe_dir=$(CDPATH= cd "$(dirname "$0")" 2>/dev/null && pwd)
probe_output=
# A Ports launcher may change the working directory or source this script.
# Prefer the known plumOS Ports directory, rather than relying only on $0.
# Overrides are for isolated verification; players do not need to set them.
for probe_candidate in "${GKD_CHECK_DIR:-}" /storage/roms/ports "$probe_dir" "$(pwd)" /tmp; do
    [ -n "$probe_candidate" ] && [ -d "$probe_candidate" ] || continue
    if (umask 077; : > "$probe_candidate/gkd_versions.txt") 2>/dev/null; then
        probe_output="$probe_candidate/gkd_versions.txt"
        break
    fi
done
if [ -z "$probe_output" ]; then
    printf '%s\n' 'Cannot create gkd_versions.txt in any available directory.' >&2
    exit 1
fi
# Write a start marker before trying Python. Even a broken Python runtime
# leaves its error in this file after an update.
exec > "$probe_output" 2>&1
printf '%s\n' 'CHECK START - diagnostic revision 2'
printf 'Script argument: %s\nWorking directory: %s\nReport path: %s\n' "$0" "$(pwd)" "$probe_output"
probe_python=${GKD_CHECK_PYTHON:-/storage/pyxel_Python/bin/python3}
if [ ! -x "$probe_python" ]; then
    probe_python=$(command -v python3)
fi

{
    printf '%s\n' 'GKD Pixel 2 runtime version check' 'This does not launch Pyxel or modify installed packages.'
    date
    uname -m
    if [ -n "$probe_python" ] && [ -x "$probe_python" ]; then
        "$probe_python" - <<'PY'
import sys
print("Python:", sys.version.replace("\n", " "))
print("Executable:", sys.executable)
try:
    from importlib.metadata import version
    print("Pyxel:", version("pyxel"))
except Exception as error:
    print("Pyxel: could not read installed package metadata:", str(error))
print("NOTE: This checks the selected Python environment, not game compatibility.")
PY
        probe_status=$?
        printf 'Python exit status: %s\n' "$probe_status"
    else
        printf '%s\n' 'Python: not found at /storage/pyxel_Python/bin/python3 or on PATH.'
    fi
}
printf '%s\n' 'CHECK COMPLETE'
