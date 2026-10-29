---
name: wallet-secrets
description: Keep wallet secrets out of plain files. Use whenever you make, receive or store a private key, seed phrase, wallet access key or API key, sign-in key, or a password that unlocks a wallet.
---

# Wallet secrets

A wallet secret is anything that lets someone use a wallet or its account: a private key, a
seed phrase, a wallet tool's access key or API key, a key used to sign in, or a password that
unlocks a keystore.

## Keep it in the secure store

Put every wallet secret in the operating system's secure store, never in a plain file:

- **macOS:** the Keychain, with `security add-generic-password` and
  `security find-generic-password -w`.
- **Linux:** the Secret Service, with `secret-tool store` (it reads the secret from standard
  input) and `secret-tool lookup`. It needs a running, unlocked keyring; store and look up a
  test value first to see that it works.
- **Neither works:** an encrypted file (`age -p`, `gpg --symmetric` or `openssl enc`) whose
  passphrase is never written to disk. Say plainly that access then depends on that
  passphrase, who holds it, and that it is lost on a restart if nobody does.

## Handle it without showing it

- Never print a secret: not in chat, command output, logs, notes or a commit. Every command
  you run may be recorded, so never type a secret into a command line either. Move it
  through standard input or a pipe, or read it from the store inside the command, such as
  `TOOL_API_KEY="$(secret-tool lookup service tool)" tool ...`.
- Make a new key straight into the store, for example
  `openssl rand -hex 32 | secret-tool store --label=name service name`.
- When a wallet tool saves its own key in a plain file, check whether it can read the key
  from an environment variable instead. If it can, keep the key in the store, pass it when
  the tool runs and delete the plain file. If it cannot, leave the file and name it.
- Once a secret is in the store and reads back from it, delete every plain copy you made,
  temporary files included. Never delete the only copy of a secret.

## Say where it lives

Tell your person, for each secret, without revealing it: which store or file holds it and
under what name, who can read it, what unlocks it, and whether access survives a restart.
Say whether you tested that or only expect it.

## Ask a person when it needs one

Never get around a sign-in, a code, Terms or an approval meant for a person. If keeping a
secret safe needs your person, such as to unlock a keychain or choose a passphrase, stop and
ask them.
