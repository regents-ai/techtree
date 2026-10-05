# Claude Code: headless, stream-json events, no permission prompts (the sprite is the sandbox).
CMD="claude -p --output-format stream-json --verbose --permission-mode bypassPermissions${RESUME:+ --resume $RESUME}"
