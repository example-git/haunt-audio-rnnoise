# Adapting a model into a Haunt audio plugin

This repository is both Haunt's bundled RNNoise plugin and a working example of
its audio ABI. For a tiny starting point, use the [client gain-plugin tutorial](https://github.com/example-git/haunt-client/blob/main/docs/audio-plugin-authoring.md).
The [server authoring guide](https://github.com/example-git/haunt-server/blob/main/docs/audio-plugin-authoring.md)
covers installation, limits and distribution.

## What each file does

| File | Responsibility |
| --- | --- |
| `src/adapter.c` | Converts Haunt PCM, maintains RNNoise state, processes frames, aligns dry mixing and exports diagnostics |
| `manifest.json` | Stable plugin/model IDs, ABI exports, control schema and displayed text |
| `upstream.lock.json` | Exact source revision, source/model hashes and compiler version |
| `scripts/build.py` | Verifies inputs, compiles both variants, embeds license notices and builds the ZIP/checksums |
| `scripts/check.mjs` | Checks artifacts and saves original/filtered clips plus measurements |
| `dist/` | Reviewed package, SHA-256 and build metadata committed for pinned repository installation |

## Forking the example

1. Give the fork its own plugin ID/name in `manifest.json` so installation does not
   replace RNNoise. Keep `version: 1`, which means the host schema/ABI version.
2. Decide the variants, stable IDs and defaults. Each variant owns exactly one
   Wasm file named `<variant-id>.wasm`. Keep the combined ZIP and unpacked files
   within 50 MiB; the current two RNNoise models share that package budget.
3. Adapt the model's C/C++ CPU inference interface in `src/adapter.c`. Haunt passes
   48 kHz mono normalized float32. `audio_init` returns 1, buffer getters return
   aligned byte offsets, and `audio_process` writes one complete frame and returns
   0. The adapter's buffers, model frame length and manifest must agree.
4. Update `scripts/build.py` for the new library and model format. Its source list,
   model filename selection, downloads and exports are RNNoise-specific; simply
   swapping an ONNX file into this repository will not work. Embed a compatible
   CPU inference runtime and weights in Wasm if your model needs one.
5. Pin new inputs independently in `upstream.lock.json`, review redistribution
   terms and update license notices. Do not weaken checksum checks or run
   unreviewed upstream installer/build scripts during package installation.

RNNoise expects samples at a signed-16-bit-like amplitude, although its API uses
float arrays. This adapter multiplies normalized input by 32768 and divides the
filtered output back down. It processes 480 samples per frame (10 ms). Its dry
mix uses a 960-sample delay (20 ms) to match this upstream model's overlap and
lookahead. **Measure your replacement's delay**; those numbers are not universal.
Clear recurrent and delayed state on reset. Maintain stable buffer offsets and
avoid memory growth after creation because the host retains typed-array views.

## Controls and diagnostics

`strength` is a range from 0–100 with `scale: 0.01`; the host passes 0–1 to
`audio_process`. Add numeric `range` or `number` fields to `fields`, then bind them
through ordered `abi.process_controls` or a field's setter `export`. The host
renders labels/help and validates bounds. Do not add scripts or custom UI.

The `speech` diagnostic calls `audio_probability()` while the settings monitor is
running. It is read-only and never gates speech. Diagnostics are optional and must
return finite numeric values. The client provides the plugin and model selectors,
persists choices locally per server, and applies changes to calls and monitoring.
No custom client changes are needed for compatible fields or additional variants.

## Compile and test

Use Python 3, Node.js and the Zig version pinned in the lock file:

```sh
ZIG=/path/to/zig python3 scripts/build.py
node scripts/check.mjs /path/to/short-speech.wav
```

The script builds variants serially at low priority and caps CPU affinity on Linux.
The check accepts a WAV speech clip, saves clean/noisy originals and each filtered
variant under ignored `test-results/`, and checks finite output, initialization,
reset and dry-path alignment. Retain completed results; do not repeatedly launch
parallel corpora on a shared host. Listen to saved pairs and test quiet/loud speech
and several noise types. Noise reduction alone is not a speech-quality score.

Fixed 32 MiB memory and no host imports are intentional. Haunt's maximum is 64 MiB
per module, not an invitation to use it all. Package size and watchdog limits do
not guarantee acceptable CPU use: leave room inside the 10 ms processing budget
on slower devices. Echo cancellation, network callbacks and GPU inference are not
part of this interface.

Finally install on an isolated Haunt server and test real microphone preview,
plugin/model switching, enabled/disabled capture, join-before-download, retry and
cached reload. The package's Node check is not a browser sandbox or call test.

## Publish reproducible bytes

Run the build and checks, review `git diff -- dist/`, and commit the reviewed ZIP,
`SHA256SUMS`, `build.json`, source, lock file and notices together. Never include
`.cache/` or test recordings. GitHub CI rebuilds the package and rejects differing
committed artifacts. The final 40-character commit and ZIP's SHA-256 are the two
installation pins; tags/branch names are not sufficient.

The server downloads only `dist/haunt-plugin.zip` and runs no repository scripts.
A private repo can use a server-side contents-read token or direct ZIP upload.
Keep the checksum alongside the expected commit when sharing installation details.
Checksum verification identifies bytes; publisher review and the client sandbox
remain separate requirements.
