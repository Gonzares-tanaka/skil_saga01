#!/bin/sh
# Copy this script as Skill_Seekers.sh beside the Skill_Seekers directory.
launcher_dir=$(CDPATH= cd "$(dirname "$0")" 2>/dev/null && pwd) || exit 1
game_dir="$launcher_dir/Skill_Seekers"
launcher_log="$launcher_dir/skill_seekers_launch.log"
if (umask 077; : > "$launcher_log") 2>/dev/null; then
    exec > "$launcher_log" 2>&1
fi
printf '%s\n' 'Skill Seekers GKD launcher'
date
printf 'Game directory: %s\n' "$game_dir"
if [ ! -f "$game_dir/main.py" ]; then
    printf '%s\n' 'Cannot find Skill_Seekers/main.py beside this launcher.' >&2
    exit 1
fi
# Keep relative save/save.json under the game directory, independent of Ports.
cd "$game_dir" || exit 1
# The override is for isolated launcher verification only.
game_python=${SKILL_SEEKERS_PYTHON:-/storage/pyxel_Python/bin/python3}
if [ ! -x "$game_python" ]; then
    printf 'Python executable not found: %s\n' "$game_python" >&2
    exit 1
fi
printf 'Python: %s\nSave path: %s/save/save.json\n' "$game_python" "$game_dir"
exec "$game_python" -u main.py "$@"
