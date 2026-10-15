# Contributing

This repository contains the Haunt RNNoise adapter, reproducible build tooling,
and committed installable package. Upstream RNNoise source and model revisions
remain independently pinned in `upstream.lock.json`.

## Before submitting a change

- Do not commit private models, recordings, build caches, or test output.
- Preserve the restricted Wasm interface and documented memory/package limits.
- Update license notices and build metadata when packaged inputs change.
- Test audio changes with synthetic input and, locally, a short non-sensitive
  speech sample.

Run:

```sh
python3 scripts/build.py
node scripts/check.mjs
python3 scripts/check-docs.py
git diff --exit-code -- dist/
```

Report vulnerabilities through the private process in
[SECURITY.md](SECURITY.md), not in a public issue.

