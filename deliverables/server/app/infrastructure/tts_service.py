from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import edge_tts

from app.domain.repositories import ITtsService
from app.infrastructure.config import logger, settings


class HybridSpanishTtsService(ITtsService):
    """
    Motor de Voz Centralizado:
    1. Intenta síntesis neural natural en español colombiano (edge-tts).
    2. Si la red LAN está aislada sin internet o falla el timeout, cambia
       automáticamente a SAPI5 offline (pyttsx3) generando WAV estándar.
    3. Almacena los archivos en /static/audio para reproducción inmediata en Windows 7.
    """

    def __init__(self, audio_dir: str = settings.AUDIO_DIR, voice: str = settings.TTS_VOICE) -> None:
        self._audio_dir = Path(audio_dir)
        self._audio_dir.mkdir(parents=True, exist_ok=True)
        self._voice = voice

    async def synthesize_deposit_phrase(self, phrase: str, tx_hash: str) -> Optional[str]:
        short_id = tx_hash[:16]
        mp3_name = f"pago_{short_id}.mp3"
        mp3_path = self._audio_dir / mp3_name
        wav_name = f"pago_{short_id}.wav"
        wav_path = self._audio_dir / wav_name

        if mp3_path.exists():
            return mp3_name
        if wav_path.exists():
            return wav_name

        # Intento 1: Voz natural neuronal (requiere salida a internet)
        try:
            communicate = edge_tts.Communicate(phrase, self._voice, rate="-4%")
            await asyncio.wait_for(
                communicate.save(str(mp3_path)),
                timeout=settings.TTS_TIMEOUT_SECONDS,
            )
            if mp3_path.exists() and mp3_path.stat().st_size > 0:
                logger.info("Audio TTS neural generado: %s", mp3_name)
                return mp3_name
        except Exception as exc:
            logger.warning("TTS online no disponible (%s). Activando fallback SAPI5 offline.", exc)

        # Intento 2: SAPI5 offline (Windows 10/11 Server sin acceso a internet)
        try:
            await asyncio.to_thread(self._synthesize_sapi5_blocking, phrase, wav_path)
            if wav_path.exists() and wav_path.stat().st_size > 0:
                logger.info("Audio TTS offline SAPI5 generado: %s", wav_name)
                return wav_name
        except Exception as exc:
            logger.error("Fallo crítico en motor TTS offline SAPI5: %s", exc)

        return None

    @staticmethod
    def _synthesize_sapi5_blocking(phrase: str, target_wav: Path) -> None:
        import pyttsx3

        engine = pyttsx3.init()
        engine.setProperty("rate", 155)
        engine.setProperty("volume", 1.0)
        for voice in engine.getProperty("voices"):
            voice_name = (getattr(voice, "name", "") or "").lower()
            voice_id = (getattr(voice, "id", "") or "").lower()
            if "spanish" in voice_name or "español" in voice_name or "es-" in voice_id or "helena" in voice_name or "sabina" in voice_name:
                engine.setProperty("voice", voice.id)
                break
        engine.save_to_file(phrase, str(target_wav))
        engine.runAndWait()
        engine.stop()
