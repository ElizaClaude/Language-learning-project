# Two-Voice Lessons

Short audio lessons for learning German, Chinese (Mandarin), Spanish and Italian.
Each sentence is spoken in the language, then in English, and the pair is played twice.
About 4 minutes per lesson, 12 lessons per level.

Listen: https://elizaclaude.github.io/Language-learning-project/

- `lessons/<language>/level<N>/lesson<MM>.txt`: the sentences (`foreign | English`)
- `make_lessons.py`: turns the text into MP3s (`audio/`) with edge-tts voices
- `build_page.py`: builds `index.html` (the player page) from `page_template.html`

The sentences are original, written for this project.
