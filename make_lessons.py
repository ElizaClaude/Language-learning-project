"""Turn lesson text files into MP3s: foreign sentence, pause, English sentence, pause.

Lesson files:  lessons/<lang>/level<N>/lesson<MM>.txt, one line per sentence,
               "foreign | English" (lang = de German, zh Chinese, es Spanish, it Italian). # lines are comments.
Output:        audio/<lang>/level<N>_lesson<MM>.mp3

Voices come from edge-tts (free Microsoft online voices). Each spoken sentence is
cached in clips/, so re-running only fetches new or changed sentences.

Run:  C:\\Users\\Eliza\\anaconda3\\python.exe make_lessons.py               (all languages)
      C:\\Users\\Eliza\\anaconda3\\python.exe make_lessons.py zh            (one language)
      C:\\Users\\Eliza\\anaconda3\\python.exe make_lessons.py zh level1     (one level)
Add --slow to make the slow versions instead (audio/<lang>/slow/...): the foreign voice at
half of normal speech (-50%, the slowest edge-tts allows), English at its usual speed.
"""
import asyncio
import hashlib
import sys
from pathlib import Path

import edge_tts

HERE = Path(__file__).resolve().parent
LESSONS = HERE / "lessons"
AUDIO = HERE / "audio"
CLIPS = HERE / "clips"

# language code: (voice, speed). A negative rate = slower than normal speech.
FOREIGN = {"de": ("de-DE-KatjaNeural", "-10%"),
           "zh": ("zh-CN-XiaoxiaoNeural", "-15%"),
           "es": ("es-ES-ElviraNeural", "-10%"),   # Spain Spanish (Eliza, 16 Oct)
           "it": ("it-IT-ElsaNeural", "-10%")}
SLOW_RATE = "-50%"            # --slow: foreign voice at half speed (edge-tts clamps anything slower)
ENGLISH_VOICE = "en-US-JennyNeural"
ENGLISH_RATE = "+0%"
PAUSE_AFTER_FOREIGN = 2.0     # seconds
PAUSE_AFTER_ENGLISH = 3.0     # seconds
REPEATS = 2                   # each foreign+English pair is played this many times in a row

# MPEG audio tables (bitrate in kbit/s, sample rate in Hz), Layer III only
BITRATES = {1: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
            2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]}
RATES = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}


def silence(mp3_bytes, seconds):
    """Silent MP3 frames in the same format as mp3_bytes (a frame with empty data = silence)."""
    i = mp3_bytes.find(b"\xff")
    while not (mp3_bytes[i] == 0xFF and mp3_bytes[i + 1] & 0xE0 == 0xE0):
        i = mp3_bytes.find(b"\xff", i + 1)
    h = mp3_bytes[i:i + 4]
    version = (h[1] >> 3) & 3                     # 3 = MPEG-1, 2 = MPEG-2, 0 = MPEG-2.5
    bitrate = BITRATES[1 if version == 3 else 2][h[2] >> 4] * 1000
    rate = RATES[version][(h[2] >> 2) & 3]
    per_frame = 1152 if version == 3 else 576     # samples per frame
    length = (144 if version == 3 else 72) * bitrate // rate
    header = bytes([h[0], h[1] | 1, h[2] & 0xFD, h[3]])   # no CRC, no padding byte
    frame = header + bytes(length - 4)
    return frame * round(seconds * rate / per_frame)


async def speak(text, voice, rate):
    key = hashlib.sha1(f"{voice}|{rate}|{text}".encode("utf-8")).hexdigest()[:16]
    path = CLIPS / f"{key}.mp3"
    if not path.exists():
        await edge_tts.Communicate(text, voice, rate=rate).save(str(path))
    return path.read_bytes()


def read_lesson(path):
    pairs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        foreign, english = (part.strip() for part in line.split("|"))
        pairs.append((foreign, english))
    return pairs


async def make_lesson(lang, path, slow=False):
    folder = AUDIO / lang / "slow" if slow else AUDIO / lang
    out = folder / f"{path.parent.name}_{path.stem}.mp3"
    out.parent.mkdir(parents=True, exist_ok=True)
    voice, rate = FOREIGN[lang]
    if slow:
        rate = SLOW_RATE
    pieces = []
    for foreign, english in read_lesson(path):
        fo = await speak(foreign, voice, rate)
        en = await speak(english, ENGLISH_VOICE, ENGLISH_RATE)
        pair = [fo, silence(fo, PAUSE_AFTER_FOREIGN), en, silence(en, PAUSE_AFTER_ENGLISH)]
        pieces += pair * REPEATS
    out.write_bytes(b"".join(pieces))
    print(f"{out.relative_to(AUDIO).as_posix()}: {len(pieces) // (4 * REPEATS)} sentences x{REPEATS}, "
          f"{out.stat().st_size / 1e3:.0f} kB")


async def main():
    CLIPS.mkdir(exist_ok=True)
    slow = "--slow" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--slow"]
    langs = [args[0]] if args else list(FOREIGN)
    level = args[1] if len(args) > 1 else "level*"
    for lang in langs:
        for path in sorted((LESSONS / lang).glob(f"{level}/lesson*.txt")):
            await make_lesson(lang, path, slow)


if __name__ == "__main__":
    asyncio.run(main())
