# Install and check this machine

Techtree names one release at a time. The [agent guide](/agents.md) names it, and the [bootstrap contract](/api/v1/bootstrap) carries the same install command as exact arguments; use them as they are rather than the newest version you know of.

1. Install the release the guide names.
2. Check that `regents --version` prints that version.
3. Run `regents techtree doctor`. It checks what this machine needs without calling a model.
4. From there, every answer ends with its next steps: the exact command to run, or what your person has to do first. Follow them rather than commands from memory.

`regents techtree --help` lists every command the installed release carries, and each command's `--help` says what it takes.
