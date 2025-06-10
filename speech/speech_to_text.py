import requests
import concurrent.futures
import time
import speech_recognition as sr

from setup.config_loader import ConfigLoader
from core.system.utils.basic_tools import BasicTools
from core.system.logger import ThreadedLoggerManager

class SpeechToText:
    def __init__(self, config=None, logger=None):
        self.config = config or ConfigLoader().load_config()
        self.logger = logger or ThreadedLoggerManager.get_instance(__name__).get_logger()
        self.debug = self.config['system_settings'].get('debug_mode', False)

    def get_speech_to_text(self, audio_file):
        speech_config = self.config.get('speech_to_text', False)

        if not speech_config:
            self.logger.warning("Speech to text is disabled in the configuration.")
            return None

        mode = speech_config.get('mode', 3)
        primary = speech_config.get('primary_service', 'google')
        secondary = speech_config.get('secondary_service', 'google')

        if mode == 1:
            return self.stt_trusted_call(primary, audio_file)
        elif mode == 2:
            return self.stt_reliable_call(primary, secondary, audio_file)
        elif mode == 3:
            return self.stt_no_trust_call(primary, secondary, audio_file)
        else:
            self.logger.error("Invalid STT mode selected in the configuration.")
            return None

    def stt_trusted_call(self, service, audio_file):
        self.logger.info("Running STT Mode 1 Trusted Call: Primary only")
        try:
            text = self.stt_service(service, audio_file)
            if not text:
                self.logger.warning("Primary service failed in Mode 1.")
            if self.debug:
                self.logger.debug(f"[STT Mode 1] Result: {text}")
            return text
        except Exception as e:
            self.logger.exception(f"Error in STT Mode 1: {e}")
            return None

    def stt_reliable_call(self, primary, secondary, audio_file):
        self.logger.info("Running STT Mode 2 Reliable Call: Primary with failover")
        try:
            text = self.stt_service(primary, audio_file)
            if text:
                return text

            self.logger.warning("Primary failed. Trying secondary.")
            text = self.stt_service(secondary, audio_file)
            if not text:
                self.logger.error("Both services failed in Mode 2.")
            if self.debug:
                self.logger.debug(f"[STT Mode 2] Result: {text}")
            return text
        except Exception as e:
            self.logger.exception(f"Error in STT Mode 2 Reliable Call: {e}")
            return None

    def stt_no_trust_call(self, primary, secondary, audio_file):
        self.logger.info("Running STT Mode 3 Zero Trust: Concurrent fallback (first valid wins)")
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future_map = {
                    executor.submit(self.stt_service, primary, audio_file): primary,
                    executor.submit(self.stt_service, secondary, audio_file): secondary,
                }

                valid_result = None

                while future_map and not valid_result:
                    done_batch, _ = concurrent.futures.wait(
                        future_map.keys(),
                        return_when=concurrent.futures.FIRST_COMPLETED
                    )

                    for completed_future in done_batch:
                        service_name = future_map.pop(completed_future)
                        try:
                            result = completed_future.result(timeout=2)

                            if result and isinstance(result, str) and result.strip():
                                self.logger.info(f"[STT Mode 3] Winner: {service_name} | Result: {result}")
                                valid_result = result
                                break
                            else:
                                self.logger.warning(f"[STT Mode 3] {service_name} returned empty or invalid transcription.")
                        except Exception as e:
                            self.logger.warning(f"[STT Mode 3] {service_name} failed: {e}")

                # Cancel any leftovers
                for future in future_map:
                    future.cancel()

                if valid_result:
                    return valid_result

                self.logger.error("Both STT services failed in Mode 3.")
                return None

        except Exception as e:
            self.logger.exception("Fatal error in Mode 3 Zero Trust STT.")
            return None

    def stt_service(self, service, audio_file):
        self.logger.debug(f"[STT] Calling service: {service}")
        text = None
        try:
            if BasicTools.is_url(service):
                if self.debug:
                    self.logger.debug(f"URL detected for STT service: {service}")
                text = self.speech_to_text_api(service, audio_file)
            elif service == "google":
                if self.debug:
                    self.logger.debug(f"Google detected for STT service: {service}")
                text = self.speech_to_text_google(audio_file)
            else:
                self.logger.error(f"Unknown STT service: {service}")
        except Exception as e:
            self.logger.exception(f"Exception while invoking STT service '{service}': {e}")
        return text

    def speech_to_text_api(self, api, audio_file):
        speech_cfg = self.config['speech_to_text']
        RE_ATTEMPS = speech_cfg.get('retry_attempts', 3)
        RE_DELAY = speech_cfg.get('retry_delay', 5)
        TIMEOUT = speech_cfg.get('timeout', 5)
        retry_attempts = 0

        while RE_ATTEMPS == 0 or retry_attempts < RE_ATTEMPS:
            if self.debug:
                self.logger.debug(f"[STT API] Attempting to call API: {api} (Attempt {retry_attempts + 1})")
            try:
                with open(audio_file, 'rb') as f:
                    response = requests.post(api, files={'audio': f}, timeout=TIMEOUT)

                if response.status_code == 200:
                    if self.debug:
                        self.logger.debug(f"[STT API] Response from {api}: {response.json()}")
                    return response.json().get("transcript")

            except requests.RequestException as e:
                self.logger.warning(f"[STT API] Request error: {e}")

            retry_attempts += 1
            self.logger.info(f"[STT API] Retrying in {RE_DELAY * retry_attempts} seconds...")
            time.sleep(RE_DELAY * retry_attempts)

        self.logger.error("STT API retries exhausted.")
        return None

    def speech_to_text_google(self, audio_file):
        recognizer = sr.Recognizer()
        try:
            with sr.AudioFile(audio_file) as source:
                audio = recognizer.record(source)

            text = recognizer.recognize_google(audio)
            if self.debug:
                self.logger.debug(f"[STT Google] Recognized text: {text}")
            return text

        except sr.UnknownValueError:
            self.logger.warning("Google STT could not understand the audio.")
            return None
        except sr.RequestError as e:
            self.logger.error(f"Google STT API error: {e}")
            return None
