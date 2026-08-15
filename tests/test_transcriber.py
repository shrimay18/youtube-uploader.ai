"""P3: transcription behind an interface (API parsers + factory + a mocked call)."""
from youtube_manager import transcriber as T
from youtube_manager.transcribe import Transcript


def test_parse_openai_verbose_json():
    payload = {"text": "Hello world", "language": "en", "duration": 12.0,
               "segments": [{"start": 0.0, "end": 2.0, "text": " Hello"},
                            {"start": 2.0, "end": 4.0, "text": " world"}]}
    t = T._parse_openai(payload)
    assert isinstance(t, Transcript)
    assert t.text == "Hello world" and t.language == "en" and t.duration == 12.0
    assert len(t.segments) == 2 and t.segments[0].text == "Hello"


def test_parse_deepgram_groups_words_into_segments():
    words = [{"start": i * 0.5, "end": i * 0.5 + 0.5, "punctuated_word": f"w{i}"} for i in range(25)]
    payload = {"metadata": {"duration": 13.0},
               "results": {"channels": [{"detected_language": "en",
                           "alternatives": [{"transcript": "full text here", "words": words}]}]}}
    t = T._parse_deepgram(payload)
    assert t.text == "full text here" and t.language == "en" and t.duration == 13.0
    assert len(t.segments) == 2                      # 25 words / 20 per chunk
    assert t.segments[0].text.startswith("w0")


def test_parse_deepgram_empty_is_safe():
    assert T._parse_deepgram({}).text == ""


def test_openai_transcriber_posts_correctly(monkeypatch, tmp_path):
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFFfakeaudio")
    captured = {}

    class R:
        def raise_for_status(self): pass
        def json(self): return {"text": "hi", "language": "en", "segments": []}

    def fake_post(url, headers=None, files=None, data=None, timeout=600):
        captured.update(url=url, data=data, headers=headers)
        return R()

    monkeypatch.setattr(T.requests, "post", fake_post)
    t = T.OpenAITranscriber("sk-test").transcribe(str(audio))
    assert t.text == "hi"
    assert captured["url"].endswith("/audio/transcriptions")
    assert captured["data"]["model"] == "whisper-1"
    assert captured["headers"]["Authorization"] == "Bearer sk-test"


def test_get_transcriber_factory(monkeypatch):
    monkeypatch.setenv("TM_TRANSCRIBER", "deepgram")
    monkeypatch.setenv("DEEPGRAM_API_KEY", "dg")
    assert isinstance(T.get_transcriber({}), T.DeepgramTranscriber)
    monkeypatch.setenv("TM_TRANSCRIBER", "openai")
    assert isinstance(T.get_transcriber({}), T.OpenAITranscriber)
    monkeypatch.setenv("TM_TRANSCRIBER", "local")
    assert isinstance(T.get_transcriber({}), T.LocalWhisperTranscriber)
