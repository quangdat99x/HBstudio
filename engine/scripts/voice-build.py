"""Cut the narration take into lines, place them on the picture and time the captions word by word.

Reads audio/voice/plan.json (take, lines: scene + local frame, tempo, caption; see ENGINE.md) and src/timeline.js.
Writes out/voice/<id>.wav (48 kHz mono, trimmed, tempo-adjusted, lightly compressed) and src/voice.json
(absolute frames of every line and every spoken word) used by the captions (narration() in src/voice.ts) and by
scripts/make-audio.mjs (m.write(..., {voice: 'src/voice.json'})).

Needs numpy + faster-whisper: run it with the Python in $WHISPER_PY (set by Creater Vid and JRE Studio):
  "$WHISPER_PY" scripts/voice-build.py
"""
import json, os, site, subprocess, sys, wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

# faster-whisper loads the CUDA runtime from the nvidia-* wheels; ctranslate2 searches PATH for them.
dll_dirs = []
for root in site.getsitepackages() + [site.getusersitepackages()]:
    nv = Path(root) / "nvidia"
    if nv.is_dir():
        for b in nv.glob("*/bin"):
            os.add_dll_directory(str(b)); dll_dirs.append(str(b))
os.environ["PATH"] = os.pathsep.join(dll_dirs + [os.environ.get("PATH", "")])
import numpy as np

SR = 48000
plan = json.loads(Path("audio/voice/plan.json").read_text(encoding="utf-8"))
timeline = json.loads(subprocess.check_output(
    ["node", "-e", "import('./src/timeline.js').then(m => console.log(JSON.stringify({fps: m.FPS, scenes: m.SCENES, duration: m.DURATION})))"],
    text=True))
FPS = timeline["fps"]
out_dir = Path("out/voice"); out_dir.mkdir(parents=True, exist_ok=True)
take = Path("audio/voice") / plan["take"]

# 1. decode the take once, at the mixing rate
take_wav = out_dir / "take.wav"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(take), "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", str(take_wav)], check=True)
with wave.open(str(take_wav)) as w:
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768

# 2. words with timestamps (cached per take)
cache = out_dir / f"words_{take.stem}.json"
if cache.exists():
    words = json.loads(cache.read_text())
else:
    from faster_whisper import WhisperModel
    model = WhisperModel("large-v3", device="cuda", compute_type="float16")
    segs, _ = model.transcribe(str(take), language="en", word_timestamps=True)
    words = [dict(w=w.word.strip(), s=w.start, e=w.end, p=w.probability) for s in segs for w in s.words]
    cache.write_text(json.dumps(words, indent=1))

# 3. energy envelope (10 ms hop, 30 ms window) and speech islands
hop, win = SR // 100, int(SR * 0.03)
db = np.array([20 * np.log10(np.sqrt(np.mean(x[i:i + win] ** 2)) + 1e-9) for i in range(0, len(x) - win, hop)])
peak = np.percentile(db, 99)

def islands(thr=45, mingap=18):
    on = db > peak - thr
    out, start, gap, last = [], None, 0, 0
    for i, v in enumerate(on):
        if v:
            if start is None: start = i
            gap, last = 0, i
        elif start is not None:
            gap += 1
            if gap >= mingap: out.append([start / 100, last / 100 + 0.03]); start = None
    if start is not None: out.append([start / 100, last / 100 + 0.03])
    return out

def voiced(i):
    """Periodicity of the 30 ms frame at hop i (breaths and room tone are not voiced)."""
    f = x[i * hop:i * hop + win]; f = f - f.mean()
    ac = np.fft.irfft(np.abs(np.fft.rfft(f, 2 * win)) ** 2)[:win]
    lo, hi = int(SR / 400), int(SR / 60)
    k = int(np.argmax(ac[lo:hi]))
    # a real pitch period is an interior peak; noise gives a falling curve whose max sits on the lag bound
    return 2 < k < hi - lo - 2 and ac[lo + k] / (ac[0] + 1e-12) > 0.5

def onset(s, e, first=False):
    """Whisper word starts absorb the silence before a word: move each start to where the voice begins.
    The first word of a line may follow a breath, so it must also be voiced (whisper can end it before its vowel)."""
    a, b = int(s * 100), int(e * 100) + (25 if first else 0)
    cand = [i for i in range(a, min(b, len(db))) if db[i] > peak - 40]
    if first: cand = [i for i in cand if voiced(i)] or cand
    return cand[0] / 100 if cand else s

def onsets(ws, seg0):
    out = []
    for j, w in enumerate(ws):
        t = max(seg0, onset(w["s"], w["e"], j == 0))
        out.append(max(t, out[-1] + 0.06) if out else t)
    return out

# 4. split the take into the planned lines (word counts come from the captions)
isl, k, lines = islands(), 0, []
for n, line in enumerate(plan["lines"]):
    count = line.get("words") or len(line["caption"].split())
    ws = words[k:] if n == len(plan["lines"]) - 1 else words[k:k + count]
    k += count
    a, b = ws[0]["e"] - 0.05, ws[-1]["e"]
    mine = [s for s in isl if (n == 0 and s[1] <= b) or (a - 0.6 <= (s[0] + s[1]) / 2 <= b + 0.3 and s[1] > a)]
    for s in mine: isl.remove(s)
    seg0, seg1 = mine[0][0] - 0.04, mine[-1][1] + 0.06
    # the last line takes the rest of the take; whisper may add a word for a breath, keep the last `count`
    lines.append(dict(line, seg=[round(seg0, 3), round(seg1, 3)], spoken=" ".join(w["w"] for w in ws),
                      onsets=onsets(ws[-count:], seg0)))

# 5. render each line and place it
result = []
for L in lines:
    tempo = L.get("tempo", 1.0)
    seg0, seg1 = L["seg"]
    dur = (seg1 - seg0) / tempo
    start = (timeline["scenes"][L["scene"]]["from"] + L["at"]) / FPS
    chain = [f"atrim=start={seg0}:end={seg1}", "asetpts=PTS-STARTPTS"]
    if abs(tempo - 1) > 1e-3:
        chain.append(f"rubberband=tempo={tempo}:pitchq=quality:transients=smooth")
    chain += ["highpass=f=70", "acompressor=threshold=-21dB:ratio=2.2:attack=6:release=140:makeup=1.6",
              "afade=t=in:d=0.02", f"afade=t=out:st={max(0, dur - 0.09):.3f}:d=0.09"]
    wav = out_dir / f"{L['id']}.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(take_wav), "-af", ",".join(chain), "-ar", str(SR), "-ac", "1",
                    "-c:a", "pcm_s16le", "-map_metadata", "-1", "-bitexact", str(wav)], check=True)
    to_frame = lambda t: round((start + (t - seg0) / tempo) * FPS, 2)
    result.append(dict(id=L["id"], scene=L["scene"], caption=L.get("caption"), cite=L.get("cite"), file=wav.as_posix(),
                       start=round(start * FPS, 2), end=round((start + dur) * FPS, 2),
                       words=[to_frame(t) for t in L["onsets"]], spoken=L["spoken"]))

for i, r in enumerate(result):
    gap = (r["start"] - result[i - 1]["end"]) / FPS if i else r["start"] / FPS
    print(f"{r['id']:8s} {r['start'] / FPS:6.2f}s - {r['end'] / FPS:6.2f}s  gap {gap:5.2f}s  | {r['spoken']}")
    if gap < 0: print(f"  !! overlaps the previous line by {-gap:.2f}s")
end = timeline["duration"] / FPS
if result[-1]["end"] / FPS > end - 0.5: print(f"  !! last line ends {result[-1]['end'] / FPS:.2f}s, film ends {end:.2f}s")
Path("src/voice.json").write_text(json.dumps(dict(fps=FPS, take=plan["take"], voice=plan["voice"]["name"], lines=result), indent=1), encoding="utf-8")
print("src/voice.json written")
