"""Voice input/output. Backends are optional and tried in order:
   1. faster-whisper (offline)  2. SpeechRecognition + Google (online)  3. none -> use typed commands."""
from __future__ import annotations
import re
import threading


class VoiceListener:
    def __init__(self, wake_word: str | None = None, model_size: str = "base.en", seconds_max: float = 8.0):
        self.wake = wake_word.lower() if wake_word else None
        self.backend = None
        self.seconds_max = seconds_max
        try:
            import numpy as np                       # noqa
            import sounddevice as sd                 # noqa
            from faster_whisper import WhisperModel
            self._model = WhisperModel(model_size, device="cpu", compute_type="int8")
            self.backend = "whisper"
        except Exception:
            try:
                import speech_recognition as sr
                self._sr = sr
                self._rec = sr.Recognizer()
                self.backend = "sr"
            except Exception:
                self.backend = None

    @property
    def available(self) -> bool:
        return self.backend is not None

    # ---------------------------------------------------------------- capture
    def _record_vad(self, rate: int = 16000):
        import numpy as np
        import sounddevice as sd
        block = int(rate * 0.1)
        frames, silent, started = [], 0, False
        with sd.InputStream(samplerate=rate, channels=1, dtype="float32", blocksize=block) as st:
            for _ in range(int(self.seconds_max / 0.1) + 30):
                data, _ = st.read(block)
                level = float(np.sqrt(np.mean(data ** 2)))
                if level > 0.015:
                    started, silent = True, 0
                elif started:
                    silent += 1
                if started:
                    frames.append(data.copy())
                if started and silent > 8:
                    break
        return np.concatenate(frames)[:, 0] if frames else None

    def listen(self) -> str | None:
        """Block until one utterance is captured. Returns lowercase text, or None."""
        text = None
        if self.backend == "whisper":
            audio = self._record_vad()
            if audio is None:
                return None
            segs, _ = self._model.transcribe(audio, language="en", vad_filter=True, beam_size=1)
            text = " ".join(s.text for s in segs).strip()
        elif self.backend == "sr":
            with self._sr.Microphone() as src:
                self._rec.adjust_for_ambient_noise(src, 0.3)
                try:
                    audio = self._rec.listen(src, timeout=6, phrase_time_limit=self.seconds_max)
                    text = self._rec.recognize_google(audio)
                except Exception:
                    return None
        if not text:
            return None
        text = text.lower().strip()
        if self.wake:
            if self.wake not in text:
                return None
            text = re.sub(rf"^.*?{re.escape(self.wake)}[ ,]*", "", text)
        return text or None


class Speaker:
    def __init__(self):
        self._lock = threading.Lock()
        try:
            import pyttsx3
            self._engine = pyttsx3.init()
        except Exception:
            self._engine = None

    def __call__(self, text: str):
        if self._engine is None:
            return
        with self._lock:
            self._engine.say(text)
            self._engine.runAndWait()
