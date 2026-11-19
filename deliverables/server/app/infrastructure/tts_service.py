from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Dict, List, Optional

import edge_tts

from app.domain.repositories import ITtsService
from app.infrastructure.config import logger, settings

AVAILABLE_VOICES: List[Dict[str, str]] = [
    {
        "id": "es-CO-SalomeNeural",
        "label": "Salomé — Español (Colombia · Femenina)",
        "accent": "Colombia",
        "gender": "Femenina",
        "provider": "Neural (Edge TTS)",
    },
    {
        "id": "gtts-es-co",
        "label": "Voz Colombia Estándar — Español (Colombia · Femenina)",
        "accent": "Colombia",
        "gender": "Femenina",
        "provider": "Google TTS",
    },
    {
        "id": "es-CO-GonzaloNeural",
        "label": "Gonzalo — Español (Colombia · Masculina)",
        "accent": "Colombia",
        "gender": "Masculina",
        "provider": "Neural (Edge TTS)",
    },
    {
        "id": "es-MX-DaliaNeural",
        "label": "Dalia — Español (México · Femenina)",
        "accent": "México",
        "gender": "Femenina",
        "provider": "Neural (Edge TTS)",
    },
    {
        "id": "es-ES-ElviraNeural",
        "label": "Elvira — Español (España · Femenina)",
        "accent": "España",
        "gender": "Femenina",
        "provider": "Neural (Edge TTS)",
    },
    {
        "id": "es-AR-ElenaNeural",
        "label": "Elena — Español (Argentina · Femenina)",
        "accent": "Argentina",
        "gender": "Femenina",
        "provider": "Neural (Edge TTS)",
    },
    {
        "id": "es-VE-PaolaNeural",
        "label": "Paola — Español (Venezuela · Femenina)",
        "accent": "Venezuela",
        "gender": "Femenina",
        "provider": "Neural (Edge TTS)",
    },
]

SPANISH_VOICE_TOKENS = (
    "es-co",
    "es_co",
    "es-mx",
    "es_mx",
    "es-es",
    "es_es",
    "es-419",
    "spanish",
    "español",
    "espanol",
    "sabina",
    "helena",
    "paloma",
    "salome",
    "raul",
    "pablo",
)


def _slugify_voice(voice_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", voice_id.strip()) or "default"


class HybridSpanishTtsService(ITtsService):
    """
    Motor de Voz Centralizado en Español:
    1. Usa la voz configurada por el Administrador (por defecto: es-CO-SalomeNeural,
       voz femenina colombiana).
    2. Si Edge TTS no está disponible, realiza fallback automático a Google TTS en español
       colombiano (tld='com.co', voz femenina clara).
    3. Si no hay conexión a internet, busca voces SAPI5 en español instaladas en Windows
       (evitando leer español con voces en inglés como Microsoft David/Zira).
    """

    def __init__(self, audio_dir: str = settings.AUDIO_DIR, voice: str = settings.TTS_VOICE) -> None:
        self._audio_dir = Path(audio_dir)
        self._audio_dir.mkdir(parents=True, exist_ok=True)
        self._voice = voice

    async def synthesize_deposit_phrase(
        self,
        phrase: str,
        tx_hash: str,
        voice: Optional[str] = None,
    ) -> Optional[str]:
        selected_voice = (voice or self._voice or settings.TTS_VOICE).strip()
        short_id = tx_hash[:16]
        voice_slug = _slugify_voice(selected_voice)

        mp3_name = f"pago_{short_id}_{voice_slug}.mp3"
        mp3_path = self._audio_dir / mp3_name
        wav_name = f"pago_{short_id}_{voice_slug}.wav"
        wav_path = self._audio_dir / wav_name

        if mp3_path.exists() and mp3_path.stat().st_size > 0:
            return mp3_name
        if wav_path.exists() and wav_path.stat().st_size > 0:
            return wav_name

        # Intento 1: Voz neural seleccionada (por defecto es-CO-SalomeNeural, femenina colombiana)
        if selected_voice != "gtts-es-co":
            try:
                communicate = edge_tts.Communicate(phrase, selected_voice, rate="-4%")
                await asyncio.wait_for(
                    communicate.save(str(mp3_path)),
                    timeout=settings.TTS_TIMEOUT_SECONDS,
                )
                if mp3_path.exists() and mp3_path.stat().st_size > 0:
                    logger.info("Audio TTS neural (%s) generado: %s", selected_voice, mp3_name)
                    return mp3_name
            except Exception as exc:
                logger.warning(
                    "Edge TTS no disponible para '%s' (%s). Intentando respaldo en español.",
                    selected_voice,
                    exc,
                )

        # Intento 2: Respaldo online gTTS en español colombiano femenino (tld='com.co')
        try:
            await asyncio.wait_for(
                asyncio.to_thread(self._synthesize_gtts_blocking, phrase, mp3_path),
                timeout=max(settings.TTS_TIMEOUT_SECONDS, 6.0),
            )
            if mp3_path.exists() and mp3_path.stat().st_size > 0:
                logger.info("Audio TTS español colombiano (gTTS) generado: %s", mp3_name)
                return mp3_name
        except Exception as exc:
            logger.warning("gTTS no disponible (%s). Activando fallback SAPI5 offline.", exc)

        # Intento 3: SAPI5 offline en Windows (únicamente si existe una voz en español instalada)
        try:
            generated = await asyncio.to_thread(self._synthesize_sapi5_blocking, phrase, wav_path)
            if generated and wav_path.exists() and wav_path.stat().st_size > 0:
                logger.info("Audio TTS offline SAPI5 en español generado: %s", wav_name)
                return wav_name
        except Exception as exc:
            logger.error("Fallo en motor TTS offline SAPI5: %s", exc)

        return None

    @staticmethod
    def _synthesize_gtts_blocking(phrase: str, target_mp3: Path) -> None:
        from gtts import gTTS

        tts = gTTS(text=phrase, lang="es", tld="com.co", slow=False)
        tts.save(str(target_mp3))

    @staticmethod
    def _synthesize_sapi5_blocking(phrase: str, target_wav: Path) -> bool:
        import pyttsx3

        engine = pyttsx3.init()
        engine.setProperty("rate", 155)
        engine.setProperty("volume", 1.0)

        voices = engine.getProperty("voices") or []
        chosen_voice = None

        # Priorizar voces femeninas en español (Sabina, Helena, Paloma, etc.)
        for voice in voices:
            voice_name = (getattr(voice, "name", "") or "").lower()
            voice_id = (getattr(voice, "id", "") or "").lower()
            languages = " ".join(str(lang).lower() for lang in (getattr(voice, "languages", None) or []))
            haystack = f"{voice_name} {voice_id} {languages}"
            if any(token in haystack for token in SPANISH_VOICE_TOKENS):
                chosen_voice = voice
                if any(fem in haystack for fem in ("sabina", "helena", "paloma", "salome", "female")):
                    break

        if chosen_voice is None:
            logger.warning(
                "Windows no tiene paquetes de voz SAPI5 en español instalados. "
                "Se omite SAPI5 para evitar pronunciación en inglés; el navegador usará síntesis local."
            )
            engine.stop()
            return False

        engine.setProperty("voice", chosen_voice.id)
        engine.save_to_file(phrase, str(target_wav))
        engine.runAndWait()
        engine.stop()
        return True
