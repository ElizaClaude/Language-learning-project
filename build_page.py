"""Build the phone page (index.html, and an identical app.html) from page_template.html + the lessons.

17 Oct: the page lets you pick the language to learn AND the language to learn from. It no longer
plays one ready-made MP3 per lesson: it downloads the lesson's sentence clips (from clips/, made by
make_clips.py) and joins them on the phone in the same order make_lessons.py uses.

Run after make_clips.py:  C:\\Users\\Eliza\\anaconda3\\python.exe build_page.py
          --check  also joins every "from English" lesson here and compares it byte for byte with
                   the old ready-made MP3 in audio/ (normal and slow), to prove the page plays the same thing.
"""
import html
import json
import re
import sys
from pathlib import Path

from make_clips import BASE, courses
from make_lessons import CLIPS, FOREIGN, REPEATS, SLOW_RATE, clip_key, read_lesson

HERE = Path(__file__).resolve().parent
LANGS = {"de": {"label": "German", "short": "DE", "native": "Deutsch"},
         "zh": {"label": "Chinese", "short": "中文", "native": "中文"},
         "es": {"label": "Spanish", "short": "ES", "native": "Español"},
         "it": {"label": "Italian", "short": "IT", "native": "Italiano"},
         "en": {"label": "English", "short": "EN", "native": "English"}}
KBIT = 48   # edge-tts MP3 bitrate (kbit/s), used to get a lesson's length from its size


def lesson_title(path):
    first = path.read_text(encoding="utf-8").splitlines()[0]
    m = re.match(r"#\s*Level \d+, Lesson \d+:\s*(.+)", first)
    return re.sub(r"\s*\(.*\)$", "", m.group(1)) if m else path.stem


def size(key):
    return (CLIPS / f"{key}.mp3").stat().st_size


def join(lines, slow):
    """The lesson's bytes, exactly as the page joins them. lines = [[text, key, slow key, base key], ...]"""
    p2, p3 = (CLIPS / "pause2.mp3").read_bytes(), (CLIPS / "pause3.mp3").read_bytes()
    out = []
    for _, k, ks, kb in lines:
        out += [(CLIPS / f"{ks if slow else k}.mp3").read_bytes(), p2, (CLIPS / f"{kb}.mp3").read_bytes(), p3] * REPEATS
    return b"".join(out)


def main():
    p2, p3 = size("pause2"), size("pause3")
    # step-by-step lessons (make_pimsleur.py) live in data/<learn>_<from>.json, fetched by the page when needed
    steps = sorted(p.stem.replace("_", "|") for p in (HERE / "data").glob("*_*.json"))
    data = {"langs": LANGS, "courses": {}, "bases": {}, "steps": steps}
    check = []
    for target, base, txt, sentences, base_title in courses():
        pairs = read_lesson(txt)
        if sentences is None:
            sentences = [en for _, en in pairs]
        voice, rate = FOREIGN[target]
        lid = f"{txt.parent.name}_{txt.stem}"          # e.g. level1_lesson01
        level = int(txt.parent.name[5:])
        course = data["courses"].setdefault(target, {})
        if lid not in course:
            course[lid] = {"level": level, "n": int(txt.stem[6:]), "title": html.escape(lesson_title(txt)),
                           "lines": [[html.escape(fo), clip_key(fo, voice, rate), clip_key(fo, voice, SLOW_RATE)]
                                     for fo, _ in pairs]}
        tlines = course[lid]["lines"]
        blines = [[html.escape(b), clip_key(b, *BASE[base])] for b in sentences]
        dur = sum((size(t[1]) + p2 + size(b[1]) + p3) * REPEATS for t, b in zip(tlines, blines)) * 8 / (KBIT * 1000)
        dur_slow = sum((size(t[2]) + p2 + size(b[1]) + p3) * REPEATS for t, b in zip(tlines, blines)) * 8 / (KBIT * 1000)
        data["bases"].setdefault(f"{target}|{base}", {})[lid] = {
            "title": html.escape(base_title) if base_title else None,
            "lines": blines, "dur": round(dur), "durSlow": round(dur_slow)}
        if base == "en":
            check.append((target, lid, [[*t, b[1]] for t, b in zip(tlines, blines)]))
    # lessons as a list per target, in level/lesson order
    data["courses"] = {t: [{"id": lid, **x} for lid, x in sorted(c.items())] for t, c in data["courses"].items()}

    page = (HERE / "page_template.html").read_text(encoding="utf-8")
    page = page.replace("/*DATA*/", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    (HERE / "index.html").write_text(page, encoding="utf-8")   # GitHub Pages
    (HERE / "app.html").write_text(page, encoding="utf-8")     # old claude.ai copy (frozen, not published)
    for pair, lessons in sorted(data["bases"].items()):
        t, b = pair.split("|")
        print(f"learn {LANGS[t]['label']} from {LANGS[b]['label']}: {len(lessons)} lessons, "
              f"{sum(x['dur'] for x in lessons.values()) / 60:.0f} min")
    for pair in steps:
        d = json.loads((HERE / "data" / f"{pair.replace('|', '_')}.json").read_text(encoding="utf-8"))
        t, b = pair.split("|")
        print(f"step by step: {LANGS[t]['label']} from {LANGS[b]['label']}: {len(d['parts'])} parts, "
              f"{sum(p['dur'] for p in d['parts']) / 60:.0f} min")
    print(f"index.html: {len(page) / 1e3:.0f} kB")

    if "--check" in sys.argv:
        same = differ = 0
        for target, lid, lines in check:
            for slow in (False, True):
                old = HERE / "audio" / target / ("slow" if slow else "") / f"{lid}.mp3"
                if not old.exists():
                    continue
                if join(lines, slow) == old.read_bytes():
                    same += 1
                else:
                    differ += 1
                    print("DIFFERENT:", old.relative_to(HERE).as_posix())
        print(f"check: {same} joined lessons identical to the old MP3s, {differ} different")


if __name__ == "__main__":
    main()
