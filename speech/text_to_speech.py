import requests
import concurrent.futures
import time
import asyncio
import os
from uuid import uuid4
import simpleaudio as sa
from pydub import AudioSegment
from edge_tts import Communicate
import inspect

from setup.config_loader import ConfigLoader
from core.system.utils.basic_tools import BasicTools
from core.system.logger import ThreadedLoggerManager


class TextToSpeech:
    def __init__(self, config=None, logger=None):
        self.config = config or ConfigLoader().load_config()
        self.logger = logger or ThreadedLoggerManager.get_instance(__name__).get_logger()
        self.debug = self.config['system_settings'].get('debug_mode', False)

    async def give_text_to_speech(self, text, model_config):
        text_config = self.config.get('text_to_speech', False)
        if not text_config:
            self.logger.warning("Text-to-speech is disabled in the configuration.")
            return None

        mode = text_config.get('mode', 1)
        primary = text_config.get('primary_service', 'edge_tts')
        secondary = text_config.get('secondary_service', 'edge_tts')

        if mode == 1:
            audio_path = await self.tts_trusted_call(primary, text, model_config)
        elif mode == 2:
            audio_path = await self.tts_reliable_call(primary, secondary, text, model_config)
        elif mode == 3:
            audio_path = await self.tts_no_trust_call(primary, secondary, text, model_config)
        else:
            self.logger.error("Invalid TTS mode specified - Aborting.")
            return None

        return await self.speak(audio_path)

    async def tts_trusted_call(self, service, text, model_config):
        self.logger.info(f"TTS Strategy: TRUSTED CALL - using service '{service}'")

        try:
            audio_path = await self.tts_service(service, text, model_config)
            if audio_path:
                self.logger.info(f"Service '{service}' succeeded.")
            else:
                self.logger.warning(f"Service '{service}' returned no audio.")
            return audio_path

        except Exception as e:
            self.logger.exception(f"Trusted TTS call failed: {e}")
            return None

    async def tts_reliable_call(self, primary, secondary, text, model_config):
        self.logger.info("TTS Strategy: RELIABLE CALL (failover)")

        try:
            self.logger.info(f"Trying primary TTS service: {primary}")
            audio_path = await self.tts_service(primary, text, model_config)
            if audio_path:
                self.logger.info(f"Primary service '{primary}' succeeded.")
                return audio_path

            self.logger.warning(f"Primary service '{primary}' failed. Attempting fallback to '{secondary}'.")
            fallback_audio = await self.tts_service(secondary, text, model_config)

            if fallback_audio:
                self.logger.info(f"Secondary service '{secondary}' succeeded.")
                return fallback_audio
            else:
                self.logger.error("Both primary and secondary TTS services failed.")
                return None

        except Exception as e:
            self.logger.exception(f"Reliable TTS call crashed unexpectedly: {e}")
            return None

    async def tts_no_trust_call(self, primary, secondary, text, model_config):
        self.logger.info("TTS Strategy: NO TRUST (racing services with validation)")

        try:
            results = await asyncio.gather(
                self.tts_service(primary, text, model_config),
                self.tts_service(secondary, text, model_config),
                return_exceptions=True
            )

            for result in results:
                if isinstance(result, str) and os.path.exists(result):
                    return result

            self.logger.error("No valid TTS responses in zero-trust mode.")
            return None

        except Exception as e:
            self.logger.exception(f"Concurrent TTS call failed: {e}")
            return None

    async def tts_service(self, service, text, model_config):
        self.logger.debug(f"Using {service} for: {text}")
        if BasicTools.is_url(service):
            if self.debug:
                self.logger.debug(f"[TTS] API URL: {service}")
            return await self.text_to_speech_api(service, text)
        elif service == 'edge_tts':
            if self.debug:
                self.logger.debug("[TTS] Using Edge TTS service")
            return await self.text_to_speech_edge(text, model_config)

        self.logger.error(f"Unknown TTS service: {service}")
        return None

    async def speak(self, audio_path):
        if not audio_path or not os.path.exists(audio_path):
            self.logger.warning("Audio path invalid or file missing.")
            return None

        self.logger.info(f"Playing audio: {audio_path}")
        try:
            wave_obj = sa.WaveObject.from_wave_file(audio_path)
            play_obj = wave_obj.play()
            play_obj.wait_done()
            if self.debug:
                self.logger.debug(f"Audio playback completed: {audio_path}")
        except Exception as e:
            self.logger.error(f"Audio playback error: {e}")
        finally:
            try:
                os.remove(audio_path)
                if self.debug:
                    self.logger.debug(f"Temporary audio file deleted: {audio_path}")
            except Exception as e:
                self.logger.warning(f"Failed to delete audio file: {e}")

    async def text_to_speech_api(self, api, text):
        text_config = self.config.get('text_to_speech', {})
        retries = text_config.get('retry_attempts', 3)
        delay = text_config.get('retry_delay', 5)
        timeout = text_config.get('timeout', 5)

        uid = uuid4().hex[:8]
        output_path = os.path.join(os.getcwd(), "temp_audio", f"{uid}.wav")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        for attempt in range(retries or 1):
            try:
                response = requests.post(api, params={"text": text}, timeout=timeout)
                if self.debug:
                    self.logger.debug(f"[TTS API] Attempt {attempt + 1}: {response.status_code}")
                if response.status_code == 200:
                    with open(output_path, "wb") as f:
                        f.write(response.content)
                    self.logger.info(f"Audio saved to {output_path}")
                    return output_path
                else:
                    self.logger.warning(f"API error: {response.status_code} - {response.text}")
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"API request failed: {e}")
                await asyncio.sleep(delay * (attempt + 1))
        self.logger.error("TTS API retries exhausted.")
        return None

    async def text_to_speech_edge(self, text, model_config):
        temp_dir = os.path.join(os.getcwd(), "temp_audio")
        os.makedirs(temp_dir, exist_ok=True)

        uid = uuid4().hex[:8]
        mp3_path = os.path.join(temp_dir, f"{uid}.mp3")
        wav_path = mp3_path.replace(".mp3", ".wav")

        self.logger.debug(f"[Edge TTS] Saving audio to {mp3_path}")
        try:
            if self.debug:
                self.logger.debug(f"[Edge TTS] Text to convert: {text}")
            communicate = Communicate(text=text, voice=model_config.get('voice', 'en-IE-EmilyNeural'))
            await communicate.save(mp3_path)

            if not os.path.exists(mp3_path):
                self.logger.warning("[Edge TTS] MP3 file not created!")
                return None

            self.logger.debug(f"[Edge TTS] Converting to WAV: {wav_path}")
            sound = AudioSegment.from_file(mp3_path, format="mp3")
            sound.export(wav_path, format="wav")

            if not os.path.exists(wav_path):
                self.logger.warning("[Edge TTS] WAV export failed!")
                return None

            os.remove(mp3_path)
            if self.debug:
                self.logger.debug(f"[Edge TTS] WAV file created: {wav_path}")    
            return wav_path
        except Exception as e:
            self.logger.error(f"[Edge TTS] Exception: {e}")
            return None
