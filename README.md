# Two-Voice Lessons

Short audio lessons for learning German, Chinese (Mandarin), Spanish and Italian.
Each sentence is spoken in the language you learn, then in your own language, and the pair is played twice.
Choose both on the page ("I want to learn" / "I speak"). Ready: every course from English,
German for Chinese speakers and Chinese for German speakers (Levels 0-2).
About 4 minutes per lesson, 12 lessons per level.

Listen: https://elizaclaude.github.io/Language-learning-project/

- `lessons/<language>/level<N>/lesson<MM>.txt`: the sentences (`foreign | English`)
- `translations/<learn>/<from>/level<N>/lesson<MM>.txt`: the sentences in the learner's language
- `make_clips.py`: speaks every sentence into `clips/` with edge-tts voices
- `build_page.py`: builds `index.html` (the player page) from `page_template.html`;
  the page joins a lesson's clips into one MP3 on your phone
- `make_lessons.py`: the older ready-made lesson MP3s in `audio/` (from English)

The sentences are original, written for this project.
