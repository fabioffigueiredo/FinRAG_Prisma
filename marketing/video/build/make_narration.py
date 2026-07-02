"""Gera a narração placeholder (macOS `say`, voz Luciana) e timings.json.

Para cada linha de narration-gestor.txt:
  - sintetiza um .aiff com `say`
  - mede a duração com ffprobe
  - concatena tudo num único mp3
Escreve timings.json com, por beat: índice, texto, startFrame e durFrames (fps=30),
incluindo um pequeno padding entre beats. Remotion lê esse JSON para cronometrar as cenas.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

import sys

FPS = 30
PAD_SECONDS = 0.6           # respiro entre beats
VOICE = "Luciana"
ROOT = Path(__file__).resolve().parents[1]      # marketing/video
VARIANT = (sys.argv[1] if len(sys.argv) > 1 else "gestor")
if VARIANT == "linkedin":
    TXT = ROOT / "narration.txt"
    OUT_MP3 = ROOT / "public" / "narration-linkedin.mp3"
    OUT_JSON = ROOT / "src" / "timings-linkedin.json"
else:
    TXT = ROOT / "narration-gestor.txt"
    OUT_MP3 = ROOT / "public" / "narration-gestor.mp3"
    OUT_JSON = ROOT / "src" / "timings.json"
TMP = ROOT / "build" / "tmp" / VARIANT


def _duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def main():
    lines = [ln.strip() for ln in TXT.read_text(encoding="utf-8").splitlines() if ln.strip()]
    TMP.mkdir(parents=True, exist_ok=True)
    OUT_MP3.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    aiffs: list[Path] = []
    beats = []
    cursor_frames = 0
    for i, text in enumerate(lines):
        aiff = TMP / f"beat_{i:02d}.aiff"
        subprocess.run(["say", "-v", VOICE, "-o", str(aiff), text], check=True)
        dur = _duration(aiff)
        aiffs.append(aiff)
        dur_frames = round(dur * FPS)
        beats.append({
            "index": i,
            "text": text,
            "startFrame": cursor_frames,
            "durFrames": dur_frames,
        })
        cursor_frames += dur_frames + round(PAD_SECONDS * FPS)

    # concatena os aiffs com pausa de PAD_SECONDS entre eles -> mp3.
    # Usa o FILTRO concat (não o demuxer): reescreve PTS e evita drift/DTS quebrado.
    # Sequência de inputs: beat0, silêncio, beat1, silêncio, ..., beatN, silêncio.
    silence = TMP / "silence.aiff"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
         "anullsrc=r=44100:cl=mono", "-t", str(PAD_SECONDS), str(silence)],
        check=True,
    )
    inputs: list[str] = []
    for a in aiffs:
        inputs += ["-i", str(a), "-i", str(silence)]
    n_inputs = len(aiffs) * 2
    # normaliza cada input para 44100/mono antes de concatenar
    parts = "".join(f"[{i}:a]aresample=44100,aformat=channel_layouts=mono[a{i}];"
                    for i in range(n_inputs))
    refs = "".join(f"[a{i}]" for i in range(n_inputs))
    filter_complex = f"{parts}{refs}concat=n={n_inputs}:v=0:a=1[out]"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", *inputs,
         "-filter_complex", filter_complex, "-map", "[out]",
         "-ac", "1", "-ar", "44100", str(OUT_MP3)],
        check=True,
    )

    total_frames = cursor_frames
    OUT_JSON.write_text(json.dumps(
        {"fps": FPS, "totalFrames": total_frames, "beats": beats},
        ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"narração: {OUT_MP3}")
    print(f"timings:  {OUT_JSON}  (total {total_frames} frames ~ {total_frames/FPS:.1f}s)")


if __name__ == "__main__":
    main()
