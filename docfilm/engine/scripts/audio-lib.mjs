// Procedural score + sound effects, synthesised sample by sample (no downloaded audio).
// Usage (scripts/make-audio.mjs):
//   const m = new Mixer({seconds: 30});
//   m.tone(55, 0.16, (t) => env(t, [[0, 0], [2, 0.7], [29, 0.7], [30, 0]]));
//   m.boom(12.3, 0.9); m.thunder(21.2, 0.9);
//   m.duck([[4.0, 9.5]], -12);           // keep the score under a JRE quote
//   m.write('out/soundtrack_raw.wav', 'public/soundtrack.wav');   // mastered to -16 LUFS
import {spawnSync} from 'node:child_process';
import {mkdirSync, writeFileSync} from 'node:fs';
import path from 'node:path';

const TAU = Math.PI * 2;

export function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Piecewise-linear automation: [[time, value], ...]
export function env(t, pts) {
  if (t <= pts[0][0]) return pts[0][1];
  for (let k = 0; k < pts.length - 1; k++) {
    const [t0, v0] = pts[k];
    const [t1, v1] = pts[k + 1];
    if (t <= t1) return v0 + (v1 - v0) * ((t - t0) / (t1 - t0 || 1));
  }
  return pts[pts.length - 1][1];
}

export class Mixer {
  constructor({seconds, sr = 48000, seed = 2024}) {
    this.SR = sr;
    this.N = Math.round(seconds * sr);
    this.dryL = new Float32Array(this.N);
    this.dryR = new Float32Array(this.N);
    this.sendL = new Float32Array(this.N);
    this.sendR = new Float32Array(this.N);
    this.gain = new Float32Array(this.N).fill(1); // ducking
    this.rnd = mulberry32(seed);
    this.TABLE = 4096;
    this.WT = new Float32Array(this.TABLE);
    for (let i = 0; i < this.TABLE; i++) {
      let s = 0;
      for (let h = 1; h <= 7; h++) s += Math.sin((TAU * h * i) / this.TABLE) / Math.pow(h, 1.7);
      this.WT[i] = s * 0.6;
    }
  }

  noise() {
    return this.rnd() * 2 - 1;
  }

  put(i, x, pan = 0, send = 0.25) {
    if (i < 0 || i >= this.N) return;
    const gl = Math.cos(((pan + 1) * Math.PI) / 4);
    const gr = Math.sin(((pan + 1) * Math.PI) / 4);
    this.dryL[i] += x * gl;
    this.dryR[i] += x * gr;
    this.sendL[i] += x * gl * send;
    this.sendR[i] += x * gr * send;
  }

  // Topology-preserving state-variable filter (lp / bp / hp).
  svf() {
    let ic1 = 0;
    let ic2 = 0;
    const SR = this.SR;
    return (x, fc, q = 0.7) => {
      const g = Math.tan((Math.PI * Math.min(fc, SR * 0.45)) / SR);
      const k = 1 / q;
      const a1 = 1 / (1 + g * (g + k));
      const a2 = g * a1;
      const a3 = g * a2;
      const v3 = x - ic2;
      const v1 = a1 * ic1 + a2 * v3;
      const v2 = ic2 + a2 * ic1 + a3 * v3;
      ic1 = 2 * v1 - ic1;
      ic2 = 2 * v2 - ic2;
      return {lp: v2, bp: v1, hp: x - k * v1 - v2};
    };
  }

  // Two detuned wavetable (or sine) oscillators with a slow breathing swell.
  tone(f, gain, curve, {pan = 0, send = 0.35, from = 0, to = this.N / this.SR, pure = false} = {}) {
    let p1 = this.rnd();
    let p2 = this.rnd();
    const lph = this.rnd() * TAU;
    const lfo = 0.05 + this.rnd() * 0.08;
    for (let i = Math.floor(from * this.SR); i < Math.min(this.N, Math.floor(to * this.SR)); i++) {
      const t = i / this.SR;
      const c = curve(t);
      if (c <= 0) continue;
      p1 += f / this.SR;
      p2 += (f * 1.0035) / this.SR;
      const s = pure ? Math.sin(TAU * p1) + Math.sin(TAU * p2) : this.WT[((p1 % 1) * this.TABLE) | 0] + this.WT[((p2 % 1) * this.TABLE) | 0];
      this.put(i, s * gain * c * (0.78 + 0.22 * Math.sin(TAU * lfo * t + lph)), pan, send);
    }
  }

  wind(curve, level = 0.5) {
    const fl = this.svf();
    const fr = this.svf();
    let bl = 0;
    let br = 0;
    for (let i = 0; i < this.N; i++) {
      const t = i / this.SR;
      bl = (bl + 0.02 * this.noise()) / 1.02;
      br = (br + 0.02 * this.noise()) / 1.02;
      const g = curve(t);
      const m = 0.65 + 0.35 * Math.sin(TAU * 0.13 * t) * Math.sin(TAU * 0.07 * t + 1);
      const fc = 380 + 260 * Math.sin(TAU * 0.05 * t);
      this.dryL[i] += fl(bl * 7, fc).lp * g * m * level;
      this.dryR[i] += fr(br * 7, fc * 1.1).lp * g * m * level;
    }
  }

  thump(t, gain, pan = 0, f0 = 110, f1 = 38, decay = 0.35, send = 0.2) {
    let ph = 0;
    const i0 = Math.floor(t * this.SR);
    const len = Math.floor(decay * 5 * this.SR);
    for (let k = 0; k < len; k++) {
      const tt = k / this.SR;
      const fr = f1 + (f0 - f1) * Math.exp(-tt / 0.06);
      ph += fr / this.SR;
      const e = Math.exp(-tt / decay) * Math.min(1, k / (0.003 * this.SR));
      this.put(i0 + k, Math.sin(TAU * ph) * e * gain, pan, send);
    }
  }

  burst(t, gain, {len = 1.2, decay = 0.3, fc0 = 2000, fc1 = 200, fdecay = 0.1, pan = 0, send = 0.5} = {}) {
    const flt = this.svf();
    const i0 = Math.floor(t * this.SR);
    for (let k = 0; k < len * this.SR; k++) {
      const tt = k / this.SR;
      const fc = fc1 + (fc0 - fc1) * Math.exp(-tt / fdecay);
      this.put(i0 + k, flt(this.noise(), fc).lp * Math.exp(-tt / decay) * gain, pan, send);
    }
  }

  boom(t, gain, decay = 1.2) {
    this.thump(t, gain, 0, 90, 26, decay, 0.5);
    this.burst(t, gain * 0.7, {len: 2, decay: 0.45, fc0: 2400, fc1: 160, fdecay: 0.12, send: 0.7});
  }

  riser(t0, t1, gain) {
    const flt = this.svf();
    for (let i = Math.floor(t0 * this.SR); i < t1 * this.SR; i++) {
      const p = (i / this.SR - t0) / (t1 - t0);
      this.put(i, flt(this.noise(), 200 + 3200 * p * p, 1.4).bp * p * p * p * gain, Math.sin(p * 9) * 0.4, 0.6);
    }
  }

  metal(t, gain, f0, {ratios = [1, 2.76, 5.4, 8.93, 13.34], amps = [1, 0.55, 0.35, 0.22, 0.12], decays = [1.1, 0.7, 0.45, 0.28, 0.18], pan = 0, send = 0.5, click = 0.4} = {}) {
    const i0 = Math.floor(t * this.SR);
    const len = Math.floor(Math.max(...decays) * 5 * this.SR);
    const ph = ratios.map(() => this.rnd());
    for (let k = 0; k < len; k++) {
      const tt = k / this.SR;
      let s = 0;
      for (let j = 0; j < ratios.length; j++) s += amps[j] * Math.sin(TAU * (f0 * ratios[j] * tt + ph[j])) * Math.exp(-tt / decays[j]);
      s += this.noise() * Math.exp(-tt / 0.004) * click;
      this.put(i0 + k, s * gain * Math.min(1, k / (0.0008 * this.SR)), pan, send);
    }
  }

  crackle(t, gain, pan) {
    const i0 = Math.floor(t * this.SR);
    let prev = 0;
    for (let k = 0; k < 0.006 * this.SR; k++) {
      const x = this.noise() * Math.exp(-k / (0.001 * this.SR));
      this.put(i0 + k, (x - prev) * gain, pan, 0.2);
      prev = x;
    }
  }

  whooshDown(t0, t1, gain, pan0 = 0, pan1 = 0) {
    const flt = this.svf();
    for (let i = Math.floor(t0 * this.SR); i < t1 * this.SR + 0.15 * this.SR; i++) {
      const t = i / this.SR;
      const p = Math.min(1, (t - t0) / (t1 - t0));
      const e = t < t1 ? p * p : Math.exp(-(t - t1) / 0.04);
      this.put(i, flt(this.noise(), 400 + 3000 * p * p, 1.2).bp * e * gain, pan0 + (pan1 - pan0) * p, 0.35);
    }
  }

  thunder(t, gain) {
    const fl = this.svf();
    const fr = this.svf();
    let bl = 0;
    let br = 0;
    const bumps = Array.from({length: 7}, () => ({c: this.rnd() * 2.6, w: 0.15 + this.rnd() * 0.4, a: 0.4 + this.rnd() * 0.6}));
    const i0 = Math.floor(t * this.SR);
    for (let k = 0; k < 4.5 * this.SR; k++) {
      const i = i0 + k;
      if (i >= this.N) break;
      const tt = k / this.SR;
      bl = (bl + 0.03 * this.noise()) / 1.03;
      br = (br + 0.03 * this.noise()) / 1.03;
      let am = 0.5;
      for (const b of bumps) am += b.a * Math.exp(-(((tt - b.c) / b.w) ** 2));
      const rumble = Math.min(1, tt / 0.06) * Math.exp(-tt / 1.6) * am;
      const crack = this.noise() * Math.exp(-tt / 0.045) * 0.8;
      const fc = 160 + 500 * Math.exp(-tt / 0.4);
      const L = (crack + fl(bl * 9, fc).lp * rumble) * gain;
      const R = (crack * 0.8 + fr(br * 9, fc).lp * rumble) * gain;
      this.dryL[i] += L;
      this.dryR[i] += R;
      this.sendL[i] += L * 0.5;
      this.sendR[i] += R * 0.5;
    }
  }

  // Lower the whole score by `db` during each [t0, t1] window (fades of `fade` seconds).
  duck(windows, db = -12, fade = 0.35) {
    const low = Math.pow(10, db / 20);
    for (const [t0, t1] of windows) {
      for (let i = Math.max(0, Math.floor((t0 - fade) * this.SR)); i < Math.min(this.N, Math.ceil((t1 + fade) * this.SR)); i++) {
        const t = i / this.SR;
        const k = t < t0 ? (t0 - t) / fade : t > t1 ? (t - t1) / fade : 0;
        this.gain[i] = Math.min(this.gain[i], low + (1 - low) * Math.min(1, k));
      }
    }
  }

  freeverb(inp, spread) {
    const k = this.SR / 44100;
    const combs = [1116, 1188, 1277, 1356, 1422, 1491, 1557, 1617].map((n) => ({buf: new Float32Array(Math.round((n + spread) * k)), i: 0, store: 0}));
    const aps = [556, 441, 341, 225].map((n) => ({buf: new Float32Array(Math.round((n + spread) * k)), i: 0}));
    const fb = 0.87;
    const damp = 0.3;
    const out = new Float32Array(inp.length);
    for (let n = 0; n < inp.length; n++) {
      const x = inp[n] * 0.03;
      let s = 0;
      for (const c of combs) {
        const y = c.buf[c.i];
        c.store = y * (1 - damp) + c.store * damp;
        c.buf[c.i] = x + c.store * fb;
        if (++c.i >= c.buf.length) c.i = 0;
        s += y;
      }
      for (const a of aps) {
        const b = a.buf[a.i];
        const y = -s + b;
        a.buf[a.i] = s + b * 0.5;
        if (++a.i >= a.buf.length) a.i = 0;
        s = y;
      }
      out[n] = s;
    }
    return out;
  }

  // Reverb, gentle saturation, fade-out, 16-bit WAV, then ffmpeg loudnorm to `lufs`.
  write(rawPath, masteredPath, {lufs = -16, tp = -1.5, wet = 0.7} = {}) {
    const N = this.N;
    const wetL = this.freeverb(this.sendL, 0);
    const wetR = this.freeverb(this.sendR, 23);
    const outL = new Float32Array(N);
    const outR = new Float32Array(N);
    let peak = 1e-9;
    for (let i = 0; i < N; i++) {
      outL[i] = (this.dryL[i] + wetL[i] * wet) * this.gain[i];
      outR[i] = (this.dryR[i] + wetR[i] * wet) * this.gain[i];
      peak = Math.max(peak, Math.abs(outL[i]), Math.abs(outR[i]));
    }
    const drive = 1.6;
    for (let i = 0; i < N; i++) {
      const fade = Math.min(1, (N - i) / (0.8 * this.SR));
      outL[i] = (Math.tanh((outL[i] / peak) * drive) / Math.tanh(drive)) * 0.9 * fade;
      outR[i] = (Math.tanh((outR[i] / peak) * drive) / Math.tanh(drive)) * 0.9 * fade;
    }
    const buf = Buffer.alloc(44 + N * 4);
    buf.write('RIFF', 0);
    buf.writeUInt32LE(36 + N * 4, 4);
    buf.write('WAVE', 8);
    buf.write('fmt ', 12);
    buf.writeUInt32LE(16, 16);
    buf.writeUInt16LE(1, 20);
    buf.writeUInt16LE(2, 22);
    buf.writeUInt32LE(this.SR, 24);
    buf.writeUInt32LE(this.SR * 4, 28);
    buf.writeUInt16LE(4, 32);
    buf.writeUInt16LE(16, 34);
    buf.write('data', 36);
    buf.writeUInt32LE(N * 4, 40);
    for (let i = 0; i < N; i++) {
      buf.writeInt16LE(Math.round(Math.max(-1, Math.min(1, outL[i])) * 32767), 44 + i * 4);
      buf.writeInt16LE(Math.round(Math.max(-1, Math.min(1, outR[i])) * 32767), 46 + i * 4);
    }
    mkdirSync(path.dirname(rawPath), {recursive: true});
    mkdirSync(path.dirname(masteredPath), {recursive: true});
    writeFileSync(rawPath, buf);
    const ffmpeg = process.env.FFMPEG || 'ffmpeg';
    const r = spawnSync(ffmpeg, ['-hide_banner', '-loglevel', 'error', '-y', '-i', rawPath, '-af', `loudnorm=I=${lufs}:TP=${tp}:LRA=14`, '-ar', String(this.SR), masteredPath], {stdio: 'inherit'});
    if (r.status !== 0) throw new Error('ffmpeg loudnorm failed');
    console.log(`${masteredPath}  ${(N / this.SR).toFixed(2)}s  mastered to ${lufs} LUFS`);
  }
}
