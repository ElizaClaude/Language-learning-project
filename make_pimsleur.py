"""Step-by-step lessons (Pimsleur style), at most 3 minutes per part, for every ready language pair.

Eliza's structure (17 Oct): each new sentence is played whole, then word by word, then phrase by
phrase, then whole again. One part lasts at most MAX_SECONDS, so she can stop anytime. Like
Pimsleur, later parts come back to earlier sentences and test them:

  part = [review]  quiz on sentences from earlier parts (the last part, and one each from 2, 4, 8 parts back)
         [new]     new sentences, each built up: whole, words, phrases, whole
         [check]   quiz on this part's new sentences
  quiz item = your language, a long pause (you say it in the new language), then the answer.

A part never runs over into the next lesson, so each part keeps one topic. The review does reach
back into earlier lessons. A piece (word or phrase) that was already taught earlier in the course
is not taught again; it comes back inside the review quizzes instead.

Pieces:  buildups/<learn>/level<N>.txt
    # columns: zh en             <- the languages of the translation columns, in order
    ## lesson01
    = Hallo! Ich heiße Tom.      <- must equal the lesson's sentence, in the same order
    Hallo! | 你好！ | Hello!
    ich heiße Tom | 我叫汤姆 | my name is Tom
  Write the words first, then the phrases. "-" in a column = no translation for that language (piece skipped there).
Whole-sentence translations come from translations/<learn>/<from>/ or, for English, the lesson file.

Run:  C:\\Users\\Eliza\\anaconda3\\python.exe make_pimsleur.py            (all pairs that have pieces)
      C:\\Users\\Eliza\\anaconda3\\python.exe make_pimsleur.py de zh      (one pair)
Makes the missing clips (6 at a time) and writes data/<learn>_<from>.json for the page.
"""
import asyncio
import json
import re
import sys
from pathlib import Path

from make_clips import BASE, read_translation
from make_lessons import CLIPS, FOREIGN, LESSONS, clip_key, read_lesson, silence, speak_many, voices

HERE = Path(__file__).resolve().parent
BUILDUPS = HERE / "buildups"
OUT = HERE / "data"
MAX_SECONDS = 180
BYTES_PER_SECOND = 48000 / 8          # edge-tts MP3s are 48 kbit/s
# step kinds: (first clip, pause, second clip, pause); pause files are clips/<name>.mp3
KINDS = {0: ("T", "pause2", "B", "pause3"),       # whole sentence: new language, 2 s, yours, 3 s
         1: ("T", "pause15", "B", "pause2"),      # piece: new language, 1.5 s, yours, 2 s
         2: ("B", "pause35", "T", "pause2")}      # quiz: yours, 3.5 s to answer, new language, 2 s
PAUSE_SECONDS = {"pause15": 1.5, "pause2": 2.0, "pause3": 3.0, "pause35": 3.5}
REVIEW_CAP = 50                        # seconds of review at the start of a part, at most
SPACED = [2, 4, 8]                     # also review one sentence from 2, 4 and 8 parts back
LEVELS = ["level1", "level2"]          # Level 0 (word lists) is not needed: its words are taught as pieces
PARALLEL = 6                           # clips fetched at the same time


def norm(text):
    """Compare pieces without punctuation. Case is kept: German Morgen (morning) is not morgen (tomorrow)."""
    return re.sub(r"[\s!?.,;:¡¿。！？，、…]+", " ", text).strip()


def read_pieces(path):
    """{lesson: [(sentence, [(piece, {lang: translation}), ...]), ...]}"""
    cols, lessons, lesson = [], {}, None
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("# columns:"):
            cols = line.split(":", 1)[1].split()
        elif line.startswith("## "):
            lesson = line[3:].strip()
            lessons[lesson] = []
        elif line.startswith("#"):
            continue
        elif line.startswith("="):
            lessons[lesson].append((line[1:].strip(), []))
        else:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) != len(cols) + 1:
                raise SystemExit(f"{path.name} line {n}: expected {len(cols) + 1} columns: {raw}")
            lessons[lesson][-1][1].append((parts[0], {c: p for c, p in zip(cols, parts[1:]) if p != "-"}))
    return lessons


def course(learn, base):
    """[(lesson id, level, n, title, [(sentence, translation, [(piece, piece translation), ...]), ...]), ...]"""
    out = []
    for level in LEVELS:
        pieces_file = BUILDUPS / learn / f"{level}.txt"
        if not pieces_file.exists():
            continue
        pieces = read_pieces(pieces_file)
        for txt in sorted((LESSONS / learn / level).glob("lesson*.txt")):
            if txt.stem not in pieces:
                continue
            pairs = read_lesson(txt)
            if base == "en":
                trans = [en for _, en in pairs]
                title = re.sub(r"\s*\(.*\)$", "", re.match(r"#\s*Level \d+, Lesson \d+:\s*(.+)",
                                                           txt.read_text(encoding="utf-8").splitlines()[0]).group(1))
            else:
                tr = HERE / "translations" / learn / base / level / txt.name
                if not tr.exists():
                    continue
                title, trans = read_translation(tr)
            built = pieces[txt.stem]
            if [s for s, _ in built] != [fo for fo, _ in pairs]:
                bad = next(((a, b) for a, b in zip([s for s, _ in built], [fo for fo, _ in pairs]) if a != b), None)
                raise SystemExit(f"{learn}/{level}/{txt.stem}: sentences differ from the lesson file "
                                 f"({len(built)} vs {len(pairs)}; first difference: {bad})")
            sents = [(fo, tb, [(p, d[base]) for p, d in plist if base in d])
                     for (fo, _), tb, (_, plist) in zip(pairs, trans, built)]
            out.append((f"{level}_{txt.stem}", int(level[5:]), int(txt.stem[6:]), title, sents))
    return out


class Clips:
    """Text -> clip keys and sizes; makes missing clips PARALLEL at a time.
    T entries: [text, key, slow key] + [key, slow key] of a second voice (Chinese has two that take turns)."""
    def __init__(self, learn, base):
        self.tvoices = list(zip(voices(learn), voices(learn, slow=True)))
        self.bv, self.br = BASE[base]
        self.T, self.B, self.ti, self.bi = [], [], {}, {}

    def t(self, text):
        if text not in self.ti:
            self.ti[text] = len(self.T)
            self.T.append([text] + [clip_key(text, *vr) for pair in self.tvoices for vr in pair])
        return self.ti[text]

    def tkey(self, ti, vi, slow):
        return self.T[ti][1 + 2 * vi + (1 if slow else 0)]

    def b(self, text):
        if text not in self.bi:
            self.bi[text] = len(self.B)
            self.B.append([text, clip_key(text, self.bv, self.br)])
        return self.bi[text]

    async def make_all(self):
        jobs = [(t[0], *vr) for t in self.T for pair in self.tvoices for vr in pair] + \
               [(b, self.bv, self.br) for b, _ in self.B]
        return await speak_many(jobs, PARALLEL)


def size(key):
    return (CLIPS / f"{key}.mp3").stat().st_size


def step_seconds(c, step, slow, vi=None):
    """Length of one step. vi = which voice says the learned language; None = the longest voice (for packing)."""
    kind, ti, bi = step
    _, p1, _, p2 = KINDS[kind]
    t = max(size(c.tkey(ti, v, slow)) for v in range(len(c.tvoices))) if vi is None else size(c.tkey(ti, vi, slow))
    return (t + size(c.B[bi][1])) / BYTES_PER_SECOND + PAUSE_SECONDS[p1] + PAUSE_SECONDS[p2]


def voice_turns(steps, nv):
    """Which voice says the learned language in each step (the page uses the same rule): the voices take
    turns, and a text that comes back is said by the other voice than last time (Eliza: "first with one,
    second with another")."""
    said, nxt, out = {}, 0, []
    for _, ti, _ in steps:
        v = nxt % nv
        if nv > 1 and said.get(ti) == v:
            v = (v + 1) % nv
        said[ti], nxt = v, v + 1
        out.append(v)
    return out


def part_seconds(c, steps, slow):
    """Exact length of a part as the page plays it."""
    return sum(step_seconds(c, st, slow, v) for st, v in zip(steps, voice_turns(steps, len(c.tvoices))))


def plan(learn, base):
    """Pack the course into parts. Returns (Clips, parts) with steps as [kind, T index, B index]."""
    c = Clips(learn, base)
    lessons = course(learn, base)
    for _, _, _, _, sents in lessons:                     # register every text first, to make the clips
        for s, tb, pieces in sents:
            c.t(s), c.b(tb)
            for p, pb in pieces:
                c.t(p), c.b(pb)
    return c, lessons


def pack(c, lessons):
    taught_pieces, parts, taught = set(), [], []          # taught[k] = sentences new in part k
    secs = lambda steps: sum(step_seconds(c, st, False) for st in steps)
    for lid, level, n, title, sents in lessons:
        i, k_in_lesson = 0, 0
        while i < len(sents):
            k = len(parts)
            review_items = list(taught[k - 1]) if k >= 1 else []
            for back in SPACED:
                if k - back >= 0 and taught[k - back]:
                    old = taught[k - back]
                    review_items.append(old[k % len(old)])
            review = []
            for s, tb, _ in review_items:
                q = [[2, c.t(s), c.b(tb)]]
                if secs(review + q) > REVIEW_CAP:
                    break
                review += q
            new, check, new_sents = [], [], []
            while i < len(sents):
                s, tb, pieces = sents[i]
                seen = set(taught_pieces)
                build = [[0, c.t(s), c.b(tb)]]
                for p, pb in pieces:
                    key = norm(p)
                    if key in seen or key == norm(s):
                        continue
                    seen.add(key)
                    build.append([1, c.t(p), c.b(pb)])
                build.append([0, c.t(s), c.b(tb)])
                q = [[2, c.t(s), c.b(tb)]]
                if new_sents and secs(review + new + build + check + q) > MAX_SECONDS:
                    break
                taught_pieces |= seen
                new += build
                check += q
                new_sents.append(sents[i])
                i += 1
            taught.append(new_sents)
            k_in_lesson += 1
            steps = review + new + check
            parts.append({"lesson": lid, "level": level, "n": n, "title": title, "k": k_in_lesson,
                          "dur": round(part_seconds(c, steps, False)), "durSlow": round(part_seconds(c, steps, True)),
                          "steps": steps})
    return parts


def write_pauses():
    sample = next(p for p in CLIPS.glob("*.mp3") if not p.stem.startswith("pause")).read_bytes()
    for name, sec in PAUSE_SECONDS.items():
        (CLIPS / f"{name}.mp3").write_bytes(silence(sample, sec))


async def main():
    args = sys.argv[1:]
    pairs = [tuple(args[:2])] if len(args) >= 2 else \
        [(t, b) for t in FOREIGN if (BUILDUPS / t).is_dir() for b in BASE if b != t]
    OUT.mkdir(exist_ok=True)
    write_pauses()
    for learn, base in pairs:
        c, lessons = plan(learn, base)
        if not lessons:
            continue
        made = await c.make_all()
        parts = pack(c, lessons)
        data = {"learn": learn, "from": base, "T": c.T, "B": c.B, "kinds": KINDS, "parts": parts}
        out = OUT / f"{learn}_{base}.json"
        out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        durs = [p["dur"] for p in parts]
        print(f"{learn} from {base}: {len(lessons)} lessons -> {len(parts)} parts, "
              f"{min(durs)}-{max(durs)} s each, {sum(durs) / 3600:.1f} h; {made} new clips; "
              f"{out.name} {out.stat().st_size / 1e3:.0f} kB")


if __name__ == "__main__":
    asyncio.run(main())
