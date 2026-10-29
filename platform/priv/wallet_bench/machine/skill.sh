#!/usr/bin/env bash
# Puts a batch's Skill where the tested agent's adapter finds it (runner/awb_runner/roster.py SKILLS): the SKILL.md
# arrives on standard input and lands in /opt/awb-skills/<name>/, owned by root and readable by every account, so the
# agent can read it and cannot change it there. The adapter copies it into the agent's own skills folder before each
# turn. The machine's reset to its baseline removes it with the rest of the attempt. Prints the file's sha256 as written.
#
# Usage: skill.sh <name>
set -euo pipefail
NAME=${1:?skill name}
[[ $NAME =~ ^[a-z0-9-]+$ ]] || { echo "skill names are lowercase letters, digits and dashes" >&2; exit 2; }
D=/opt/awb-skills/$NAME

sudo install -d -m 755 /opt/awb-skills "$D"
sudo tee "$D/SKILL.md" > /dev/null
sudo chmod 644 "$D/SKILL.md"
sha256sum "$D/SKILL.md" | cut -d' ' -f1
