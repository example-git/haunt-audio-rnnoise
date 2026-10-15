// Serial, short PCM checks. Optional real speech is supplied locally, never uploaded.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import assert from "node:assert/strict";
const root = fileURLToPath(new URL("..", import.meta.url));
const out = path.join(root, "test-results");
fs.mkdirSync(out, { recursive: true });
const build = JSON.parse(fs.readFileSync(path.join(root, "dist/build.json")));
const manifest = JSON.parse(fs.readFileSync(path.join(root, "manifest.json")));
const sum = (x) => createHash("sha256").update(x).digest("hex");
assert.equal(sum(fs.readFileSync(path.join(root, "dist/haunt-plugin.zip"))), build.sha256);
function wav(name, data) {
  const b = Buffer.alloc(44 + data.length * 2);
  b.write("RIFF"); b.writeUInt32LE(b.length - 8, 4); b.write("WAVEfmt ", 8);
  b.writeUInt32LE(16, 16); b.writeUInt16LE(1, 20); b.writeUInt16LE(1, 22);
  b.writeUInt32LE(48000, 24); b.writeUInt32LE(96000, 28); b.writeUInt16LE(2, 32); b.writeUInt16LE(16, 34);
  b.write("data", 36); b.writeUInt32LE(data.length * 2, 40);
  for (let i=0;i<data.length;i++) b.writeInt16LE(Math.round(Math.max(-1,Math.min(1,data[i])) * 32767),44+i*2);
  fs.writeFileSync(path.join(out, name + ".wav"), b);
}
let speech = new Float32Array(48000 * 3);
if (process.argv[2]) {
  const pcm = path.join(out, "speech-source.f32");
  // Reuse the completed conversion on subsequent checks.
  if (!fs.existsSync(pcm)) execFileSync("ffmpeg", ["-nostdin", "-v", "error", "-i", process.argv[2], "-t", "12", "-ar", "48000", "-ac", "1", "-f", "f32le", pcm]);
  const b = fs.readFileSync(pcm);
  speech = new Float32Array(b.buffer.slice(b.byteOffset, b.byteOffset+b.length));
}
let seed = 41;
const random = () => { seed = (1664525 * seed + 1013904223) >>> 0; return seed/0x100000000 * 2-1; };
const clips = {};
for (const type of ["clean", "broadband", "hum-clicks"]) {
  const x = new Float32Array(Math.ceil((speech.length+48000+960)/480)*480);
  for (let i=0;i<x.length;i++) {
    const voice = i>=48000 && i<48000+speech.length ? speech[i-48000] : 0;
    const noise = type==="broadband" ? .025*random() : type==="hum-clicks" ? .012*Math.sin(2*Math.PI*120*i/48000)+(i%7200<80 ? .025*random():0) : 0;
    x[i] = Math.max(-1,Math.min(1,voice+noise));
  }
  clips[type] = x;
  wav(type+"-original",x);
}
const results=[];
for (const variant of manifest.variants) {
  const bytes=fs.readFileSync(path.join(root,".cache",variant.file));
  assert.equal(sum(bytes),build.files[variant.file].sha256);
  const module=await WebAssembly.compile(bytes);
  assert.deepEqual(WebAssembly.Module.imports(module),[]);
  const e=(await WebAssembly.instantiate(module)).exports;
  e._initialize(); assert.equal(e.audio_init(),1);
  assert.equal(e.memory.buffer.byteLength,32*1024*1024);
  const input=new Float32Array(e.memory.buffer,e.audio_input(),480);
  const output=new Float32Array(e.memory.buffer,e.audio_output(),480);
  // A zero-strength mix must retain a correctly aligned, unchanged signal.
  for(let f=0;f<5;f++) { input.fill((f+1)/10); assert.equal(e.audio_process(0),0); assert(Math.abs(output[100]-(f>=2?(f-1)/10:0))<1e-6); }
  for(const [type,x] of Object.entries(clips)) {
    e.audio_reset();
    const y=new Float32Array(x.length), times=[];
    for(let offset=0;offset<x.length;offset+=480) {
      input.set(x.subarray(offset,offset+480));
      const start=performance.now(); assert.equal(e.audio_process(1),0); times.push(performance.now()-start);
      assert(output.every(v=>Number.isFinite(v)&&Math.abs(v)<=1));
      const probability=e.audio_probability();assert(probability>=0&&probability<=1);
      y.set(output,offset);
    }
    wav(type+"-"+variant.id,y);
    const rms=(a)=>Math.sqrt(a.reduce((sum,v)=>sum+v*v,0)/a.length);
    times.sort((a,b)=>a-b);
    results.push({model:variant.id,clip:type,seconds:x.length/48000,frameMs:10,processingMedianMs:times[Math.floor(times.length/2)],processingP95Ms:times[Math.floor(times.length*.95)],noiseReductionDB:type==='clean'?null:20*Math.log10((rms(x.subarray(24000,44000))+1e-12)/(rms(y.subarray(24960,44960))+1e-12)),peak:Math.max(...y.subarray(0,48000).map(Math.abs))});
  }
}
fs.writeFileSync(path.join(out,"results.json"),JSON.stringify(results,null,2)+"\n");
console.log(JSON.stringify(results,null,2));
