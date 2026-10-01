"""Saare sound effects yahin generate hote hain — koi royalty/copyright issue nahi,
koi download nahi. numpy se banate hain, WAV likhte hain."""
import math
import wave
import numpy as np
from config import ASSETS, SAMPLE_RATE, OUT

# Bundled click. Same synthesis as _synth_key_click, written to disk so the
# Short ships a real sample. License: assets/sfx/LICENSE.txt (CC0).
C_ASSETS_CLICK = ASSETS / "sfx" / "keyclick.wav"


def _env(n, attack=0.005, decay=0.12):
    """Short percussive envelope."""
    a = int(SAMPLE_RATE * attack)
    d = n - a
    env = np.concatenate([
        np.linspace(0, 1, max(a, 1)),
        np.exp(-np.linspace(0, 1, max(d, 1)) / max(decay, 1e-6)),
    ])
    return env[:n]


def _tone(freq, dur, kind="sine"):
    n = int(SAMPLE_RATE * dur)
    t = np.arange(n) / SAMPLE_RATE
    if kind == "sine":
        w = np.sin(2 * math.pi * freq * t)
    elif kind == "tri":
        w = 2 * np.abs(2 * ((t * freq) % 1) - 1) - 1
    else:  # noise-ish click
        w = np.random.default_rng(int(freq)).uniform(-1, 1, n)
    return w


def tick(high=False):
    """Clock tik / tok. high=True -> 'tik', False -> 'tok'."""
    dur = 0.07
    n = int(SAMPLE_RATE * dur)
    base = 2100 if high else 1500
    body = 0.6 * _tone(base, dur, "sine") + 0.4 * _tone(base * 1.6, dur, "tri")
    click = 0.5 * _tone(base, dur, "noise")
    sig = (body + click) * _env(n, attack=0.001, decay=0.05)
    return sig.astype(np.float32)


def ding():
    """Sahi jawab reveal — do note ka pleasant chime (C6 -> E6)."""
    a = _tone(1046.5, 0.30) * _env(int(SAMPLE_RATE * 0.30), decay=0.35)
    b = _tone(1318.5, 0.55) * _env(int(SAMPLE_RATE * 0.55), decay=0.40)
    n = max(len(a), len(b))
    out = np.zeros(n, dtype=np.float64)
    out[:len(a)] += a * 0.7
    out[:len(b)] += b * 0.8
    return (out / (np.max(np.abs(out)) + 1e-9) * 0.85).astype(np.float32)


def whoosh():
    """Question transition."""
    dur = 0.45
    n = int(SAMPLE_RATE * dur)
    t = np.arange(n) / SAMPLE_RATE
    sweep = np.sin(2 * math.pi * (300 + 1400 * (t / dur) ** 2) * t)
    noise = np.random.default_rng(7).uniform(-1, 1, n) * 0.35
    env = np.sin(math.pi * t / dur) ** 2
    return ((sweep * 0.6 + noise) * env * 0.5).astype(np.float32)


def _synth_key_click() -> np.ndarray:
    """Short mechanical click. Original synthesis — not a sampled recording."""
    dur = 0.032
    n = int(SAMPLE_RATE * dur)
    t = np.arange(n) / SAMPLE_RATE
    rng = np.random.default_rng(11)
    noise = rng.uniform(-1, 1, n)
    noise = np.diff(noise, prepend=noise[0])
    tick = np.sin(2 * math.pi * 2100 * t) * np.exp(-t * 220)
    body = np.sin(2 * math.pi * 180 * t) * np.exp(-t * 80)
    env = np.exp(-t * 95)
    sig = (0.62 * noise + 0.28 * tick + 0.22 * body) * env
    peak = float(np.max(np.abs(sig))) + 1e-9
    return (sig / peak * 0.9).astype(np.float32)


def key_click() -> np.ndarray:
    """Bundled CC0 click if the wav is there, warna yahi synthesis."""
    path = C_ASSETS_CLICK
    if path.exists():
        with wave.open(str(path), "rb") as w:
            pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
            if w.getnchannels() == 2:
                pcm = pcm.reshape(-1, 2).mean(axis=1)
        return (pcm.astype(np.float32) / 32767.0)
    return _synth_key_click()


def keyclick_bed(text: str, seconds: float = 2.0) -> np.ndarray:
    """One click per non-space grapheme, at the same times the letters appear.

    Returned peak is about 0.9. Caller multiplies by KEYCLICK_VOLUME so the
    voiceover stays louder.
    """
    import hooktype
    clusters = hooktype.grapheme_clusters(" ".join((text or "").split()))
    n = len(clusters)
    total = max(1, int(SAMPLE_RATE * seconds))
    bed = np.zeros(total, dtype=np.float32)
    click = key_click()
    for i, cluster in enumerate(clusters):
        if cluster.isspace():
            continue
        start = int(hooktype.cluster_time(i, n) * SAMPLE_RATE)
        end = min(start + len(click), total)
        if end > start:
            bed[start:end] += click[: end - start]
    return bed


def build_timer_bed(seconds: int, volume: float) -> np.ndarray:
    """8 second ka tik-tik bed. Har second ek tick, aakhri 3 second me speed-up
    (2 tick/sec) taki tension bane."""
    n = int(SAMPLE_RATE * seconds)
    bed = np.zeros(n, dtype=np.float32)
    marks = []
    for s in range(seconds):
        if s >= seconds - 3:
            marks += [s, s + 0.5]
        else:
            marks.append(s)
    for i, m in enumerate(marks):
        start = int(m * SAMPLE_RATE)
        snd = tick(high=(i % 2 == 0))
        end = min(start + len(snd), n)
        if end > start:
            bed[start:end] += snd[:end - start]
    return bed * volume


def write_wav(path, mono: np.ndarray, sr=SAMPLE_RATE):
    mono = np.clip(mono, -1.0, 1.0)
    pcm = (mono * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return path


if __name__ == "__main__":
    write_wav(OUT / "_sfx_timer.wav", build_timer_bed(8, 0.3))
    write_wav(OUT / "_sfx_ding.wav", ding())
    print("sfx ok")
