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


# --- modo clone (XTTS-v2 com a voz do Fabio) ---------------------------------
CLONE = "--clone" in sys.argv
REF_VOZ = ROOT.parents[0] / "audio" / "ref_voz_limpa.wav"   # marketing/audio/
# fala fonética p/ termos que o TTS tropeça; a legenda mantém a grafia correta
SPOKEN_MAP = {
    "compliance": "compláians",
    "Prisma": "Prisma",
}

_tts = None
_asr = None


def _tts_engine():
    global _tts
    if _tts is None:
        from TTS.api import TTS
        import os
        os.environ.setdefault("COQUI_TOS_AGREED", "1")
        _tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
    return _tts


def _asr_engine():
    global _asr
    if _asr is None:
        import whisper
        _asr = whisper.load_model("base")
    return _asr


import re as _re


def _sentencas(texto: str) -> list[str]:
    """Divide o beat em sentenças e REMOVE o ponto final falável de cada uma
    (mantém ? e ! pela entonação). Evita o XTTS verbalizar 'ponto'."""
    partes = [s.strip() for s in _re.split(r"(?<=[.?!])\s+", texto) if s.strip()]
    out = []
    for s in partes:
        if s.endswith("."):
            s = s[:-1]
        out.append(s)
    return out


def _trim_artefato(wav: Path) -> None:
    """Remove respiro/ruído após a última palavra (fonte dos '.vip', '.pato')."""
    tmp = wav.with_suffix(".trim.wav")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-af",
         "areverse,silenceremove=start_periods=1:start_threshold=-42dB:start_silence=0.05,areverse",
         str(tmp)], check=True)
    tmp.replace(wav)


def _flags_qa(heard: str, esperado: str) -> list[str]:
    """Detectores: pontuação falada, repetição e cobertura de termos."""
    flags = []
    for pw in ("ponto", "vírgula", "virgula"):
        n_exp = len(_re.findall(rf"\b{pw}\b", esperado.lower()))
        n_heard = len(_re.findall(rf"\b{pw}\b", heard.lower()))
        if n_heard > n_exp:
            flags.append(f"pontuacao({pw})")
    ws = _re.findall(r"\w+", heard.lower())
    if any(ws[j:j+3] == ws[j+3:j+6] and len(set(ws[j:j+3])) > 1 for j in range(max(0, len(ws)-5))):
        flags.append("repeticao")
    alvo = [w for w in _re.findall(r"\w+", esperado.lower()) if len(w) > 3]
    falt = [w for w in alvo if w not in heard.lower() and w != "compliance"]
    if alvo and (1 - len(falt)/len(alvo)) < 0.8:
        flags.append("termos:" + ",".join(falt[:3]))
    return flags


def _sintetizar_clone(texto: str, destino: Path) -> None:
    """Sintetiza um beat: por SENTENÇA, com trim de artefato e QA whisper por
    sentença (até 3 tentativas). Concatena as sentenças com 0,28s de pausa."""
    tts = _tts_engine()
    asr = _asr_engine()
    pecas: list[Path] = []
    for j, sent in enumerate(_sentencas(texto)):
        falado = sent
        for k, v in SPOKEN_MAP.items():
            falado = falado.replace(k, v)
        peca = destino.with_suffix(f".s{j}.wav")
        for tentativa in range(3):
            tts.tts_to_file(text=falado, speaker_wav=str(REF_VOZ), language="pt",
                            file_path=str(peca))
            _trim_artefato(peca)
            heard = asr.transcribe(str(peca), language="pt")["text"]
            flags = _flags_qa(heard, sent)
            if not flags:
                break
            print(f"    sentença {j} tentativa {tentativa+1}: {flags} — re-sintetizando")
        pecas.append(peca)
    # concat sentenças com pausa curta
    gap = destino.with_suffix(".gap.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "anullsrc=r=24000:cl=mono", "-t", "0.28", str(gap)], check=True)
    inputs, n = [], 0
    for p in pecas:
        inputs += ["-i", str(p), "-i", str(gap)]; n += 2
    parts = "".join(f"[{i}:a]aresample=24000,aformat=channel_layouts=mono[a{i}];" for i in range(n))
    refs = "".join(f"[a{i}]" for i in range(n))
    subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex",
                    f"{parts}{refs}concat=n={n}:v=0:a=1[out]", "-map", "[out]",
                    str(destino)], check=True)
    for p in pecas:
        p.unlink(missing_ok=True)
    gap.unlink(missing_ok=True)


def _verificar_beat(wav: Path, esperado: str) -> float:
    """QA final do beat inteiro (score de cobertura p/ o log)."""
    heard = _asr_engine().transcribe(str(wav), language="pt")["text"].lower()
    palavras = [w for w in _re.findall(r"\w+", esperado.lower()) if len(w) > 3]
    if not palavras:
        return 1.0
    return sum(1 for w in palavras if w in heard) / len(palavras)


def main():
    lines = [ln.strip() for ln in TXT.read_text(encoding="utf-8").splitlines() if ln.strip()]
    TMP.mkdir(parents=True, exist_ok=True)
    OUT_MP3.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    aiffs: list[Path] = []
    beats = []
    cursor_frames = 0
    for i, text in enumerate(lines):
        if CLONE:
            aiff = TMP / f"beat_{i:02d}.wav"
            _sintetizar_clone(text, aiff)
            score = _verificar_beat(aiff, text)
            if score < 0.72:  # beat ruim -> uma nova tentativa (XTTS é estocástico)
                print(f"  beat {i}: QA {score:.0%} — re-sintetizando…")
                _sintetizar_clone(text, aiff)
                score = _verificar_beat(aiff, text)
            print(f"  beat {i}: QA whisper {score:.0%}")
        else:
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
    filter_complex = (f"{parts}{refs}concat=n={n_inputs}:v=0:a=1[cat];"
                      f"[cat]loudnorm=I=-16:TP=-1.5:LRA=11[out]")
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
