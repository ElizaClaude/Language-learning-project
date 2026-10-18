"""TEST (17 Oct): Pimsleur-style lessons of at most 3 minutes, made from a build-up file.

Eliza's structure: each new sentence is played whole, then word by word, then phrase by phrase,
then whole again. Unlike Pimsleur, one part lasts at most MAX_SECONDS, so she can stop anytime.
And, like Pimsleur, later parts come back to what was learned before and test it:

  part = [review]  quiz on sentences from earlier parts (the last part, and spaced older ones)
         [new]     2-4 new sentences, each built up:  whole, words, phrases, whole
         [check]   quiz on today's new sentences
  quiz item  = your language, a long pause (you say it in the new language), then the answer.

Build-up file: buildups/<learn>/<from>/level<N>/lesson<MM>.txt
  "German sentence = Chinese sentence", then indented "piece = translation" lines.
Run:   C:\\Users\\Eliza\\anaconda3\\python.exe make_pimsleur.py de zh level1 lesson01
Writes reports/test_audio/<learn>_from_<from>_<level>_<lesson>_part<K>.mp3 (git-ignored, for listening only)
"""
import asyncio
import sys
from pathlib import Path

from make_clips import BASE
from make_lessons import FOREIGN, silence, speak

HERE = Path(__file__).resolve().parent
OUT = HERE / "reports" / "test_audio"
MAX_SECONDS = 180
BYTES_PER_SECOND = 48000 / 8          # edge-tts MP3s are 48 kbit/s
# (pause after the new language, pause after your language), in seconds
SENTENCE = (2.0, 3.0)
PIECE = (1.5, 2.0)
QUIZ = (3.5, 2.0)                      # pause after the question (your turn to speak), after the answer
REVIEW_CAP = 50                        # seconds of review at the start of a part, at most
SPACED = [2, 4, 8]                     # also review one sentence from 2, 4 and 8 parts back


def read_buildup(path):
    """[(target, base, [(piece, piece_base), ...]), ...] and the title."""
    title, sentences = path.stem, []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        if raw.startswith("#"):
            if title == path.stem:
                title = raw.lstrip("#").strip()
            continue
        t, b = (x.strip() for x in raw.split("="))
        if raw[0] in " \t":
            sentences[-1][2].append((t, b))
        else:
            sentences.append((t, b, []))
    return title, sentences


class Maker:
    def __init__(self, learn, base):
        self.tv, self.tr = FOREIGN[learn]
        self.bv, self.br = BASE[base]
        self.fmt = None                 # one clip, to copy the MP3 frame format for silence

    async def pair(self, t, b, pauses):
        """new language, pause, your language, pause."""
        ct, cb = await speak(t, self.tv, self.tr), await speak(b, self.bv, self.br)
        self.fmt = ct
        return [ct, silence(ct, pauses[0]), cb, silence(cb, pauses[1])]

    async def quiz(self, t, b):
        """your language, long pause for you to answer, then the new language."""
        ct, cb = await speak(t, self.tv, self.tr), await speak(b, self.bv, self.br)
        return [cb, silence(cb, QUIZ[0]), ct, silence(ct, QUIZ[1])]

    async def buildup(self, sentence):
        t, b, pieces = sentence
        out = await self.pair(t, b, SENTENCE)
        for pt, pb in pieces:
            out += await self.pair(pt, pb, PIECE)
        return out + await self.pair(t, b, SENTENCE)


def seconds(chunks):
    return sum(len(c) for c in chunks) / BYTES_PER_SECOND


async def make_parts(learn, base, sentences):
    """Pack the sentences into parts of at most MAX_SECONDS. Returns [(chunks, plan text), ...]."""
    m = Maker(learn, base)
    parts, taught = [], []              # taught[k] = the sentences that were new in part k
    i = 0
    while i < len(sentences):
        k = len(parts)
        # review: everything from the last part, then one sentence from 2, 4, 8 parts back
        review_items = list(taught[k - 1]) if k >= 1 else []
        for back in SPACED:
            if k - back >= 0 and taught[k - back]:
                review_items.append(taught[k - back][k % len(taught[k - back])])
        review, plan = [], []
        for s in review_items:
            q = await m.quiz(s[0], s[1])
            if seconds(review + q) > REVIEW_CAP:
                break
            review += q
            plan.append(f"  review quiz: {s[1]} -> {s[0]}")
        new, check, new_sents = [], [], []
        while i < len(sentences):
            b = await m.buildup(sentences[i])
            q = await m.quiz(sentences[i][0], sentences[i][1])
            if new_sents and seconds(review + new + b + check + q) > MAX_SECONDS:
                break
            new += b
            check += q
            new_sents.append(sentences[i])
            plan.append(f"  new: {sentences[i][0]}  ({len(sentences[i][2])} pieces)")
            i += 1
        plan.append(f"  check quiz on the {len(new_sents)} new sentences")
        taught.append(new_sents)
        parts.append((review + new + check, plan, (seconds(review), seconds(new), seconds(check))))
    return parts


async def main():
    learn, base, level, lesson = sys.argv[1:5]
    path = HERE / "buildups" / learn / base / level / f"{lesson}.txt"
    title, sentences = read_buildup(path)
    OUT.mkdir(parents=True, exist_ok=True)
    for k, (chunks, plan, (r, n, c)) in enumerate(await make_parts(learn, base, sentences), 1):
        out = OUT / f"{learn}_from_{base}_{level}_{lesson}_part{k}.mp3"
        out.write_bytes(b"".join(chunks))
        total = seconds(chunks)
        print(f"{out.name}: {int(total // 60)}:{total % 60:04.1f}  (review {r:.0f} s, new {n:.0f} s, check {c:.0f} s)")
        print("\n".join(plan))


if __name__ == "__main__":
    asyncio.run(main())
