"""Look for broken clips: an MP3 file is a chain of frames, each starting with a 4-byte header that says
how long the frame is. If a clip ends in the middle of a frame (or has extra bytes), the next clip joined
after it starts inside a "frame", and the phone's player hears a click or crackle there.

Run:  C:\\Users\\Eliza\\anaconda3\\python.exe check_clips.py        (all clips the page uses)
"""
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
BITRATES = {1: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
            2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]}
RATES = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}


def walk(data):
    """(frames, leftover bytes at the end, bytes skipped before the first frame, formats seen)."""
    i, frames, formats = 0, 0, Counter()
    start = data.find(b"\xff")
    while start >= 0 and not (start + 1 < len(data) and data[start + 1] & 0xE0 == 0xE0):
        start = data.find(b"\xff", start + 1)
    i = max(start, 0)
    while i + 4 <= len(data):
        h = data[i:i + 4]
        if h[0] != 0xFF or h[1] & 0xE0 != 0xE0:
            break
        version = (h[1] >> 3) & 3
        bi, ri, pad = h[2] >> 4, (h[2] >> 2) & 3, (h[2] >> 1) & 1
        if version == 1 or bi in (0, 15) or ri == 3:
            break
        bitrate = BITRATES[1 if version == 3 else 2][bi] * 1000
        rate = RATES[version][ri]
        length = (144 if version == 3 else 72) * bitrate // rate + pad
        formats[(version, bitrate, rate, h[3] >> 6)] += 1
        if i + length > len(data):
            break
        i += length
        frames += 1
    return frames, len(data) - i, max(start, 0), formats


def used_clips():
    used = {"pause15", "pause2", "pause3", "pause35"}
    used |= set(re.findall(r'"([0-9a-f]{16})"', (HERE / "index.html").read_text(encoding="utf-8")))
    for f in (HERE / "data").glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        for row in d["T"] + d["B"]:
            used |= set(row[1:])
    return sorted(used)


def main():
    bad, formats, tiny = [], Counter(), []
    names = used_clips()
    for k in names:
        data = (HERE / "clips" / f"{k}.mp3").read_bytes()
        frames, left, skipped, f = walk(data)
        formats.update(f)
        if left or skipped:
            bad.append((k, len(data), frames, left, skipped))
        if frames < 10 and not k.startswith("pause"):
            tiny.append((k, frames))
    print(f"{len(names)} clips checked")
    print("frame formats (MPEG version, bit rate, sample rate, channel mode):", dict(formats))
    print(f"clips that do not end on a whole frame, or start with extra bytes: {len(bad)}")
    for row in bad[:20]:
        print("   ", row)
    print(f"clips shorter than 10 frames (0.24 s): {len(tiny)}", tiny[:10])


if __name__ == "__main__":
    main()
