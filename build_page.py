"""Build app.html (the phone page) from page_template.html + the lesson files.

The page lists every lesson in audio/<lang>/ that has a matching lessons/<lang>/ text file.
Writes app.html (claude.ai) and index.html (GitHub Pages), identical.
Run after make_lessons.py:  C:\\Users\\Eliza\\anaconda3\\python.exe build_page.py
"""
import html
import json
import re
from pathlib import Path

from make_lessons import read_lesson

HERE = Path(__file__).resolve().parent
LANGS = {"de": {"label": "German", "short": "DE", "native": "Deutsch"},
         "zh": {"label": "Chinese", "short": "中文", "native": "中文"},
         "es": {"label": "Spanish", "short": "ES", "native": "Español"},
         "it": {"label": "Italian", "short": "IT", "native": "Italiano"}}
KBIT = 48   # edge-tts MP3 bitrate (kbit/s), used to get each file's length from its size


def lesson_title(path):
    first = path.read_text(encoding="utf-8").splitlines()[0]
    m = re.match(r"#\s*Level \d+, Lesson \d+:\s*(.+)", first)
    return re.sub(r"\s*\(.*\)$", "", m.group(1)) if m else path.stem


def main():
    data = {"langs": {}}
    for lang, info in LANGS.items():
        levels = []
        for level_dir in sorted((HERE / "lessons" / lang).glob("level*")):
            lessons = []
            for txt in sorted(level_dir.glob("lesson*.txt")):
                mp3 = HERE / "audio" / lang / f"{level_dir.name}_{txt.stem}.mp3"
                if not mp3.exists():
                    continue
                lessons.append({
                    "n": int(txt.stem[6:]),
                    "title": html.escape(lesson_title(txt)),
                    "file": mp3.relative_to(HERE).as_posix(),
                    "slow": (slow.relative_to(HERE).as_posix()
                             if (slow := mp3.parent / "slow" / mp3.name).exists() else None),
                    "dur": round(mp3.stat().st_size * 8 / (KBIT * 1000)),
                    "lines": [[html.escape(f), html.escape(e)] for f, e in read_lesson(txt)],
                })
            if lessons:
                levels.append({"level": int(level_dir.name[5:]), "lessons": lessons})
        data["langs"][lang] = {**info, "levels": levels}
    page = (HERE / "page_template.html").read_text(encoding="utf-8")
    page = page.replace("/*DATA*/", json.dumps(data, ensure_ascii=False))
    (HERE / "app.html").write_text(page, encoding="utf-8")     # claude.ai page
    (HERE / "index.html").write_text(page, encoding="utf-8")   # same page, for GitHub Pages
    n = sum(len(v["lessons"]) for L in data["langs"].values() for v in L["levels"])
    print(f"app.html: {n} lessons, {len(page) / 1e3:.0f} kB")


if __name__ == "__main__":
    main()
