"""
Voice & Conversational Engine for J.A.R.V.I.S.
Robust Audio Processing with:
1. SoundDevice microphone streaming (cross-platform, zero C++ compilation).
2. Bilingual Speech-to-Text (Google SpeechRecognition) supporting both Bengali (বাংলা) and English.
3. Natural Neural Text-to-Speech (Microsoft Edge-TTS) with automatic Bengali/English voice selection
   and native Windows Multimedia (MCI) low-latency playback.
"""

from __future__ import annotations
import os
import sys
import time
import io
import wave
import asyncio
import logging
import threading
import ctypes
from pathlib import Path
from typing import Callable, Optional, Tuple, List
import numpy as np
import sounddevice as sd
import speech_recognition as sr
from config import config

logger = logging.getLogger("JARVIS.VoiceEngine")


class SpeechToTextEngine:
    """
    High-accuracy bilingual Speech-to-Text supporting:
    - Bengali (bn-BD / বাংলা)
    - English (en-US)
    - Auto-detection
    """

    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.preferred_language = "bn" # "bn", "en", or "auto"

    def transcribe_wav_bytes(self, wav_bytes: bytes, preferred_lang: Optional[str] = None) -> Tuple[str, str]:
        """
        Transcribes raw WAV audio bytes into text.
        Returns (transcription_text, detected_language).
        """
        target_lang = preferred_lang or self.preferred_language
        audio_file = io.BytesIO(wav_bytes)

        try:
            with sr.AudioFile(audio_file) as source:
                audio_data = self.recognizer.record(source)

            # Case A: User prefers Bengali (bn)
            if target_lang in ["bn", "bn-BD"]:
                try:
                    text_bn = self.recognizer.recognize_google(audio_data, language="bn-BD")
                    if text_bn and text_bn.strip():
                        return text_bn.strip(), "bn"
                except sr.UnknownValueError:
                    pass

                # Fallback to English if Bengali speech was not detected
                try:
                    text_en = self.recognizer.recognize_google(audio_data, language="en-US")
                    if text_en and text_en.strip():
                        return text_en.strip(), "en"
                except sr.UnknownValueError:
                    pass

            # Case B: User prefers English (en)
            elif target_lang in ["en", "en-US"]:
                try:
                    text_en = self.recognizer.recognize_google(audio_data, language="en-US")
                    if text_en and text_en.strip():
                        return text_en.strip(), "en"
                except sr.UnknownValueError:
                    pass

                # Fallback to Bengali
                try:
                    text_bn = self.recognizer.recognize_google(audio_data, language="bn-BD")
                    if text_bn and text_bn.strip():
                        return text_bn.strip(), "bn"
                except sr.UnknownValueError:
                    pass

            # Case C: Auto
            else:
                for lang_code, lang_name in [("bn-BD", "bn"), ("en-US", "en")]:
                    try:
                        text = self.recognizer.recognize_google(audio_data, language=lang_code)
                        if text and text.strip():
                            return text.strip(), lang_name
                    except sr.UnknownValueError:
                        continue

            return "", "en"

        except Exception as e:
            logger.error(f"Speech recognition error: {e}")
            return "", "en"


class TextToSpeechEngine:
    """
    Natural neural TTS using Microsoft Edge-TTS with bilingual English/Bengali voice switching
    and native Windows Multimedia (MCI) low-latency playback.
    """

    def __init__(self):
        self._offline_engine = None
        self._is_speaking = False
        self._current_mci_alias: Optional[str] = None
        self._init_offline_fallback()

    def _init_offline_fallback(self) -> None:
        try:
            import pyttsx3
            self._offline_engine = pyttsx3.init()
            self._offline_engine.setProperty('rate', 170)
        except Exception as e:
            logger.debug(f"pyttsx3 not initialized: {e}")

    def is_bengali(self, text: str) -> bool:
        """Determines if the text contains Bengali Unicode characters (U+0980 to U+09FF)."""
        return any('\u0980' <= char <= '\u09ff' for char in text)

    async def _generate_edge_tts_audio(self, text: str, output_path: str) -> bool:
        """Generates speech MP3 file using edge-tts."""
        try:
            import edge_tts
            voice = config.audio.tts_voice_bn if self.is_bengali(text) else config.audio.tts_voice_en
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate=config.audio.tts_rate,
                pitch=config.audio.tts_pitch
            )
            await communicate.save(output_path)
            return True
        except Exception as e:
            logger.warning(f"Edge-TTS failed ({e}). Attempting offline fallback.")
            return False

    def speak(self, text: str, on_start: Optional[Callable] = None, on_finish: Optional[Callable] = None) -> None:
        """
        Synthesizes and plays back speech audio synchronously on the current thread.
        """
        clean_text = text.strip()
        if not clean_text:
            return

        self._is_speaking = True
        if on_start:
            on_start()

        ts = int(time.time() * 1000)
        out_file = str(config.storage.temp_audio_dir / f"tts_{ts}.mp3")

        edge_success = False
        try:
            edge_success = asyncio.run(self._generate_edge_tts_audio(clean_text, out_file))
        except Exception as e:
            logger.error(f"Edge TTS async loop error: {e}")
            edge_success = False

        if edge_success and os.path.exists(out_file):
            try:
                if sys.platform == "win32":
                    # Native Windows Multimedia Player (MCI)
                    alias = f"jarvis_mci_{ts}"
                    self._current_mci_alias = alias
                    ctypes.windll.winmm.mciSendStringW(f'open "{out_file}" type mpegvideo alias {alias}', None, 0, None)
                    ctypes.windll.winmm.mciSendStringW(f'play {alias}', None, 0, None)

                    status_buf = ctypes.create_unicode_buffer(128)
                    while self._is_speaking:
                        ctypes.windll.winmm.mciSendStringW(f'status {alias} mode', status_buf, len(status_buf), None)
                        if status_buf.value != "playing":
                            break
                        time.sleep(0.05)

                    ctypes.windll.winmm.mciSendStringW(f'stop {alias}', None, 0, None)
                    ctypes.windll.winmm.mciSendStringW(f'close {alias}', None, 0, None)
                    self._current_mci_alias = None

            except Exception as e:
                logger.error(f"Native audio playback error: {e}")
            finally:
                try:
                    os.remove(out_file)
                except OSError:
                    pass
        else:
            # Fallback to offline pyttsx3
            if self._offline_engine:
                try:
                    self._offline_engine.say(clean_text)
                    self._offline_engine.runAndWait()
                except Exception as e:
                    logger.error(f"Offline pyttsx3 error: {e}")

        self._is_speaking = False
        if on_finish:
            on_finish()

    def stop(self) -> None:
        """Interrupts and stops ongoing speech output immediately."""
        self._is_speaking = False
        if sys.platform == "win32" and self._current_mci_alias:
            try:
                ctypes.windll.winmm.mciSendStringW(f'stop {self._current_mci_alias}', None, 0, None)
                ctypes.windll.winmm.mciSendStringW(f'close {self._current_mci_alias}', None, 0, None)
            except Exception:
                pass
            self._current_mci_alias = None
        if self._offline_engine:
            try:
                self._offline_engine.stop()
            except Exception:
                pass


class VoiceEngine:
    """
    Microphone Capture & Voice Interaction Engine using SoundDevice.
    Supports continuous listening, interactive button trigger, and bilingual recognition.
    """

    def __init__(self):
        self.stt = SpeechToTextEngine()
        self.tts = TextToSpeechEngine()

        self._running = False
        self._is_muted = False
        self._is_recording = False
        self.preferred_language = "bn" # Bengali default

        # Callbacks for UI updates
        self.on_state_change: Optional[Callable[[str], None]] = None
        self.on_transcription: Optional[Callable[[str, str], None]] = None
        self.on_audio_level: Optional[Callable[[float], None]] = None

    def set_preferred_language(self, lang: str) -> None:
        """Set language: 'bn' (Bengali), 'en' (English), or 'auto'."""
        self.preferred_language = lang
        self.stt.preferred_language = lang
        logger.info(f"VoiceEngine preferred speech recognition language set to: {lang}")

    def toggle_mute(self) -> bool:
        self._is_muted = not self._is_muted
        if self._is_muted:
            self.tts.stop()
            self._set_state("Muted")
        else:
            self._set_state("Idle")
        return self._is_muted

    def _set_state(self, state: str) -> None:
        if self.on_state_change:
            self.on_state_change(state)

    def trigger_voice_input(self, on_user_query_callback: Callable[[str], None]) -> None:
        """
        Manually triggered by the Mic button in UI.
        Listens immediately and records the user's voice command.
        """
        if self._is_recording:
            return

        thread = threading.Thread(
            target=self._record_and_transcribe_once,
            args=(on_user_query_callback,),
            daemon=True
        )
        thread.start()

    def _record_and_transcribe_once(self, on_user_query_callback: Callable[[str], None]) -> None:
        """Records a single voice command until silence is detected, then transcribes."""
        self._is_recording = True
        self._set_state("Listening")
        logger.info("Microphone activated: Listening for user command...")

        sample_rate = 16000
        chunk_size = 1024
        silence_threshold = 300
        silence_chunks = 0
        silence_limit = int(1.4 * sample_rate / chunk_size)
        max_chunks = int(15.0 * sample_rate / chunk_size) # 15s max

        audio_frames = []

        try:
            with sd.InputStream(samplerate=sample_rate, channels=1, dtype='int16') as stream:
                for _ in range(max_chunks):
                    if not self._is_recording:
                        break

                    data, _ = stream.read(chunk_size)
                    audio_frames.append(data.tobytes())

                    # Calculate RMS energy for UI waveform
                    rms = np.sqrt(np.mean(data.astype(np.float64)**2))
                    norm_level = min(1.0, float(rms) / 2500.0)

                    if self.on_audio_level:
                        self.on_audio_level(norm_level)

                    # Silence check after user has started speaking
                    if rms < silence_threshold:
                        silence_chunks += 1
                    else:
                        silence_chunks = 0

                    if silence_chunks > silence_limit and len(audio_frames) > 25:
                        break

            self._set_state("Thinking")

            # Convert to WAV bytes
            wav_io = io.BytesIO()
            with wave.open(wav_io, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2) # 16-bit
                wf.setframerate(sample_rate)
                wf.writeframes(b''.join(audio_frames))

            wav_bytes = wav_io.getvalue()

            # Transcribe with bilingual engine
            text, lang = self.stt.transcribe_wav_bytes(wav_bytes, self.preferred_language)

            if self.on_transcription:
                self.on_transcription(text, lang)

            logger.info(f"Transcribed Audio: '{text}' [Language: {lang}]")

            if text.strip():
                on_user_query_callback(text)
            else:
                self._set_state("Idle")

        except Exception as e:
            logger.error(f"Error recording voice input: {e}")
            self._set_state("Idle")
        finally:
            self._is_recording = False

    def start_listening_loop(self, on_user_query_callback: Callable[[str], None]) -> None:
        """Starts background continuous listening loop."""
        self._running = True
        thread = threading.Thread(
            target=self._background_listening_loop,
            args=(on_user_query_callback,),
            daemon=True
        )
        thread.start()

    def _background_listening_loop(self, on_user_query_callback: Callable[[str], None]) -> None:
        """Background continuous acoustic monitor."""
        sample_rate = 16000
        chunk_size = 1024
        energy_trigger_threshold = 1200 # Higher threshold to distinguish speech from ambient noise

        while self._running:
            if self._is_muted or self._is_recording:
                time.sleep(0.2)
                continue

            try:
                # Monitor mic stream for activation
                with sd.InputStream(samplerate=sample_rate, channels=1, dtype='int16') as stream:
                    while self._running and not self._is_muted and not self._is_recording:
                        data, _ = stream.read(chunk_size)
                        rms = np.sqrt(np.mean(data.astype(np.float64)**2))

                        if self.on_audio_level and not self.tts._is_speaking:
                            self.on_audio_level(min(1.0, float(rms) / 3000.0))

                        # If user speaks loudly while idle
                        if rms > energy_trigger_threshold and not self.tts._is_speaking:
                            self._record_and_transcribe_once(on_user_query_callback)
                            break

            except Exception as e:
                logger.debug(f"Audio monitor loop reset: {e}")
                time.sleep(0.5)


# Global VoiceEngine singleton
voice_engine = VoiceEngine()
