import speech_recognition as sr
from datetime import datetime
import uuid
import os
from core.system.logger import ThreadedLoggerManager
from setup.config_loader import ConfigLoader

class MicInput:
    def __init__(self, config=None, logger=None):
        self.config = config or ConfigLoader().load_config()
        self.logger = logger or ThreadedLoggerManager.get_instance(__name__).get_logger()
        self.debug = self.config['system_settings'].get('debug_mode', False)
        self.recognizer = sr.Recognizer()

    def listen_with_mic(self):
        """
        Blocking function — must be called using `await asyncio.to_thread(...)`.
        """
        system_config = self.config.get('system_settings', {})
        
        if not (system_config):
            self.logger.info("System settings configuration is missing.")
            return None

        try:
            self.logger.info("Listening for audio input...")
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source)
                audio_data = self.recognizer.listen(
                    source,
                    timeout=system_config.get('mic_ingest_timeout', 5),
                    phrase_time_limit=system_config.get('phrase_timeout', 15)
                )
            self.logger.info("Audio data captured.")
        except sr.WaitTimeoutError:
            self.logger.info("No speech detected within the timeout.")
            return None
        except Exception as e:
            self.logger.error(f"Error during microphone input: {e}")
            return None

        wav_data = self.convert_audio_to_wav(audio_data)
        if not wav_data:
            self.logger.warning("WAV conversion failed.")
            return None

        return {'audio_data': audio_data, 'wav_data': wav_data}

    def convert_audio_to_wav(self, audio_data):
        if not audio_data:
            return None

        try:
            wav_data = audio_data.get_wav_data()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_dir = os.path.join(os.getcwd(), "temp_audio")
            os.makedirs(temp_dir, exist_ok=True)

            file_path = os.path.join(temp_dir, f"output_{timestamp}_{uuid.uuid4().hex[:6]}.wav")
            with open(file_path, "wb") as f:
                f.write(wav_data)

            return file_path
        except Exception as e:
            self.logger.error(f"Error converting audio to WAV: {e}")
            return None
