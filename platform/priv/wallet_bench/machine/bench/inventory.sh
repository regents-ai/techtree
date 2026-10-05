# Runs as the tested account (common.sh as_bench). The account before any wallet work.
echo "captured_at=$(date -u +%FT%TZ)"
echo "--- id"; id
echo "--- sudo"; sudo -n true 2>&1 && echo "HAS SUDO" || echo "no sudo"
echo "--- PATH"; echo "$PATH"
echo "--- env names"; compgen -e | sort | tr "\n" " "; echo
echo "--- home tree (depth 3)"; find ~ -maxdepth 3 -not -path "*/.local/share/claude/versions/*" | sort
echo "--- can read /work? (expect denied)"; ls /work 2>&1 | head -1
