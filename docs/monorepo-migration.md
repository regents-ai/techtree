# v0.2 monorepo migration

The v0.2 source tree combines the three frozen v0.1 repositories while keeping
their complete product histories and component documentation.

| Directory | Previous repository | Imported source tip |
| --- | --- | --- |
| `cli/` | `regents-ai/techtree-python` | `3526d9b0b9b226e0ea018c9617c3186e6277a26c` |
| `plugin/` | `regents-ai/techtree-hermes` | `ca22ee782f5572b179c665c2c2a33120171f0158` |
| `platform/` | `regents-ai/techtree-ash` | `f6a45e00d183bbe9bc470ad755fba64cfa66f5d5` |

Each source history was rewritten only to add its final directory prefix, then
merged into this repository. The source repositories were not changed. Their
v0.1 branches remain release records; v0.2 work continues here.

Original README SHA-256 values at import:

```text
cli       9ce0958dec00abab26e5e0543d4d49cce7862028ebe07a0d242910bf6ac93ea4
plugin    bf1bb61f323a6bf3e5084b3201a99518e81eeb57f3c83704edd302a1b48ae001
platform  c2c59a6562ada47f9d1e7544f678aeca1968780f3ad039f962e5bf9268384d25
```

No automatic mirror back to the former component repositories is part of this
migration. Future release pins may reference monorepo subdirectories once the
v0.2 release process is defined; the frozen v0.1 coordinates remain unchanged.
