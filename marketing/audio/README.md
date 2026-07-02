# Áudios de narração (ElevenLabs)

**Fabio: deposite aqui os 3 áudios** gerados no ElevenLabs, com estes nomes:

| Arquivo | Conteúdo | Uso |
|---|---|---|
| `finrag.mp3` | Narração sobre o FinRAG | Referência/linha do tempo da jornada |
| `finnlp.mp3` | Narração sobre o FinNLP | Referência/linha do tempo da jornada |
| `prisma.mp3` | Narração do Prisma | **Trilha dos vídeos** (gestor e LinkedIn) |

(Formatos aceitos: mp3, wav, m4a — se o nome/formato for outro, tudo bem, só avise.)

## O que será analisado automaticamente em cada arquivo
- Duração, sample rate, canais e bitrate (`ffprobe`);
- Loudness integrado (alvo para redes sociais: **-14 LUFS**) e true peak (`ffmpeg loudnorm`);
- Clipping e silêncios longos (`silencedetect`) — os silêncios entre frases
  também servem para gerar o `timings.json` que sincroniza as cenas do vídeo;
- Encaixe da duração com os roteiros dos vídeos (LinkedIn ~60–75s · gestor ~2min).

Se precisar de correção (normalização de volume, trim de pontas), a versão
ajustada será salva como `<nome>.norm.mp3`, preservando o original.
