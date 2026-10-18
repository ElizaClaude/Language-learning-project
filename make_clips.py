"""Make the sentence clips that the page joins into lessons ("learn X from Y").

The page no longer needs one MP3 per lesson per language pair. Instead it downloads the
clips of one lesson and joins them on the phone: target sentence, 2 s pause, the same
sentence in the learner's language, 3 s pause, and the pair twice (the same as make_lessons.py).

Where the "from" sentences come from:
  from English:        the English column of lessons/<target>/level<N>/lesson<MM>.txt
  from any other one:  translations/<target>/<from>/level<N>/lesson<MM>.txt, one line per
                       sentence in the same order; the first line "# <title>" is the lesson title.

Run:  C:\\Users\\Eliza\\anaconda3\\python.exe make_clips.py
Writes the missing clips into clips/ (the same cache make_lessons.py uses) and the two
pause files clips/pause2.mp3 and clips/pause3.mp3.
"""
import asyncio

from make_lessons import (CLIPS, ENGLISH_RATE, ENGLISH_VOICE, FOREIGN, LESSONS, PAUSE_AFTER_ENGLISH,
                          PAUSE_AFTER_FOREIGN, SLOW_RATE, read_lesson, silence, speak)

HERE = LESSONS.parent
TRANSLATIONS = HERE / "translations"
# voice of each language when it is the learner's own language: normal speed
BASE = {"en": (ENGLISH_VOICE, ENGLISH_RATE),
        "de": ("de-DE-KatjaNeural", "+0%"),
        "zh": ("zh-CN-XiaoxiaoNeural", "+0%"),
        "es": ("es-ES-ElviraNeural", "+0%"),
        "it": ("it-IT-ElsaNeural", "+0%")}


def read_translation(path):
    """(title, list of sentences) from a translations/... file."""
    lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    title = lines[0].lstrip("#").strip() if lines and lines[0].startswith("#") else path.stem
    return title, [l for l in lines if not l.startswith("#")]


def courses():
    """Yield (target, base, lesson file, base sentences or None for English, base title)."""
    for target in FOREIGN:
        for txt in sorted((LESSONS / target).glob("level*/lesson*.txt")):
            yield target, "en", txt, None, None
            for tr_dir in sorted((TRANSLATIONS / target).glob("*")):
                tr = tr_dir / txt.parent.name / txt.name
                if tr.exists():
                    title, sentences = read_translation(tr)
                    yield target, tr_dir.name, txt, sentences, title


async def main():
    CLIPS.mkdir(exist_ok=True)
    made = 0
    for target, base, txt, sentences, _ in courses():
        pairs = read_lesson(txt)
        if sentences is None:
            sentences = [en for _, en in pairs]
        if len(sentences) != len(pairs):
            raise SystemExit(f"{target}->{base} {txt.parent.name}/{txt.name}: "
                             f"{len(pairs)} sentences but {len(sentences)} translations")
        voice, rate = FOREIGN[target]
        for (fo, _), b in zip(pairs, sentences):
            for text, v, r in [(fo, voice, rate), (fo, voice, SLOW_RATE), (b, *BASE[base])]:
                await speak(text, v, r)
        if base != "en":
            made += 1
            print(f"{target} from {base}: {txt.parent.name}/{txt.name} ok ({len(pairs)} sentences)")
    sample = next(p for p in CLIPS.glob("*.mp3") if not p.stem.startswith("pause")).read_bytes()
    (CLIPS / "pause2.mp3").write_bytes(silence(sample, PAUSE_AFTER_FOREIGN))
    (CLIPS / "pause3.mp3").write_bytes(silence(sample, PAUSE_AFTER_ENGLISH))
    print(f"done: {made} translated lessons; {len(list(CLIPS.glob('*.mp3')))} clips in clips/")


if __name__ == "__main__":
    asyncio.run(main())
