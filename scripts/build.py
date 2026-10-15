#!/usr/bin/env python3
"""Build a bounded Wasm package from independently pinned source/model archives."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.cache'
CACHE.mkdir(exist_ok=True)
lock = json.loads((ROOT / 'upstream.lock.json').read_text())
zig = os.environ.get('ZIG', 'zig')
if subprocess.check_output([zig, 'version'], text=True).strip() != lock['zig_version']:
    raise SystemExit('Use the Zig version pinned in upstream.lock.json')
if hasattr(os, 'sched_setaffinity'):
    os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:2])
if hasattr(os, 'nice'):
    os.nice(15)


def fetch(name, url, digest):
    path = CACHE / name
    if not path.exists():
        with urllib.request.urlopen(url, timeout=60) as response, path.with_suffix('.partial').open('wb') as output:
            size = 0
            while block := response.read(65536):
                size += len(block)
                if size > 128 << 20:
                    raise ValueError('Upstream archive too large')
                output.write(block)
        path.with_suffix('.partial').replace(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError('Upstream checksum mismatch: ' + name)
    return path


source = fetch('source.tar.gz', 'https://codeload.github.com/xiph/rnnoise/tar.gz/' + lock['commit'], lock['source_sha256'])
model = fetch('model.tar.gz', 'https://media.xiph.org/rnnoise/models/rnnoise_data-' + lock['model_sha256'] + '.tar.gz', lock['model_sha256'])
tree = CACHE / 'upstream'
tree.mkdir(exist_ok=True)
# No upstream scripts run. Extract only regular C headers/sources and notices.
for archive, prefix in [(source, 'rnnoise-' + lock['commit'] + '/'), (model, '')]:
    with tarfile.open(archive) as tar:
        for entry in tar:
            name = entry.name.removeprefix(prefix)
            path = Path(name)
            allowed = name in {'COPYING', 'AUTHORS'} or (path.parts and path.parts[0] in {'src', 'include'} and path.suffix in {'.c', '.h'})
            if not allowed:
                continue
            if not entry.isfile() or path.is_absolute() or '..' in path.parts or entry.size > 100 << 20:
                raise ValueError('Unsafe source archive')
            dest = tree / path
            dest.parent.mkdir(exist_ok=True, parents=True)
            with tar.extractfile(entry) as inp, dest.open('wb') as out:
                shutil.copyfileobj(inp, out)

sources = ['denoise', 'rnn', 'pitch', 'kiss_fft', 'celt_lpc', 'nnet', 'nnet_default', 'parse_lpcnet_weights', 'rnnoise_tables']
exports = ['audio_init', 'audio_input', 'audio_output', 'audio_process', 'audio_reset', 'audio_probability']
manifest = json.loads((ROOT / 'manifest.json').read_text())
license_text = (ROOT / 'LICENSE').read_bytes() + b'\n\nRNNoise upstream notices:\n' + (ROOT / 'THIRD-PARTY-NOTICES.txt').read_bytes()
def uleb(value):
    result = bytearray()
    while True:
        byte = value & 127
        value >>= 7
        result.append(byte | (128 if value else 0))
        if not value:
            return bytes(result)

files = {}
for variant in manifest['variants']:
    name = variant['id']
    model_source = tree / 'src' / ('rnnoise_data_little.c' if name == 'little' else 'rnnoise_data.c')
    output = CACHE / (name + '.wasm')
    command = [zig, 'cc', '-target', 'wasm32-wasi', '-mexec-model=reactor', '-O3', '-msimd128', '-I' + str(tree / 'include'), '-I' + str(tree / 'src'), str(ROOT / 'src/adapter.c'),
               *[str(tree / 'src' / (s + '.c')) for s in sources], str(model_source),
               *['-Wl,--export=' + e for e in exports], '-Wl,-z,stack-size=1048576', '-Wl,--initial-memory=33554432', '-Wl,--max-memory=33554432', '-Wl,--strip-all', '-o', str(output)]
    subprocess.run(command, check=True)
    # Keep attribution with the binary even when a client downloads only Wasm.
    section = uleb(7) + b'license' + license_text
    output.write_bytes(output.read_bytes() + b'\x00' + uleb(len(section)) + section)
    files[variant['file']] = output.read_bytes()

files['manifest.json'] = (ROOT / 'manifest.json').read_bytes()
files['LICENSE.txt'] = license_text
if sum(map(len, files.values())) > 50 << 20 or len(files['LICENSE.txt']) > 64 << 10:
    raise ValueError('Package exceeds the host limits')
dist = ROOT / 'dist'
dist.mkdir(exist_ok=True)
with zipfile.ZipFile(dist / 'haunt-plugin.zip', 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as package:
    for name, data in sorted(files.items()):
        info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        package.writestr(info, data)
digest = hashlib.sha256((dist / 'haunt-plugin.zip').read_bytes()).hexdigest()
(dist / 'SHA256SUMS').write_text(digest + '  haunt-plugin.zip\n')
(dist / 'build.json').write_text(json.dumps({'upstream': lock, 'files': {name: {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()} for name, data in files.items()}, 'sha256': digest}, indent=2) + '\n')
print('Built dist/haunt-plugin.zip:', digest)
