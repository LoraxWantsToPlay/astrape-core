import concurrent.futures
import re
import string
from enum import Enum
from core.system.logger import ThreadedLoggerManager
from setup.config_loader import ConfigLoader
from core.system.utils.system_tools import SystemTools

class EventType(Enum):
    EMERGENCY = "emergency"
    WAKE = "wake"
    SLEEP = "sleep"
    SHUTDOWN = "shutdown"
    CONTINUE = "continue"
    ERROR = "error"

EVENT_PRIORITY = {
    EventType.EMERGENCY: 1,
    EventType.WAKE: 2,
    EventType.SLEEP: 3,
    EventType.SHUTDOWN: 4,
    EventType.CONTINUE: 5,
    EventType.ERROR: 99,
}

class EventManager:
    def __init__(self, config=None, logger=None):
        self.config = config or ConfigLoader().load_config()
        self.logger = logger or ThreadedLoggerManager.get_instance(__name__).get_logger()
        self.debug = self.config['system_settings'].get('debug_mode', False)
        self.system_tools = SystemTools(config=self.config, logger=self.logger)

    def check_for_event_words(self, text: str) -> dict:
        if not text:
            self.logger.info("No text provided for event word check.")
            return {}

        self.logger.info(f"Checking for event words in: {text}")

        results = {}

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                EventType.EMERGENCY: executor.submit(self.check_for_emergency_word, text),
                EventType.WAKE: executor.submit(self.check_for_wake_word, text),
                EventType.SLEEP: executor.submit(self.check_for_sleep_word, text),
                EventType.SHUTDOWN: executor.submit(self.check_for_shutdown_word, text),
            }

            for key, future in futures.items():
                try:
                    matches = future.result()
                    if matches:
                        results[key] = matches
                except Exception as e:
                    self.logger.error(f"Error checking for {key.value} words: {e}")

        if not results:
            self.logger.info("No event words detected.")
        return results

    def normalize_input(self, text):
        text = text.lower().strip()
        # Remove punctuation but keep spaces
        text_cleaned  = re.sub(rf"[{re.escape(string.punctuation)}]", "", text)
        text_final  = re.sub(r"\s+", " ", text_cleaned)
        if self.debug:
            self.logger.debug(f"[NORMALIZED] Raw: '{text}' :> Normalized: '{text_final}'")
        return text_final

    def check_for_word(self, keywords: list, text: str):
        text_clean = self.normalize_input(text)
        matches = []

        for phrase in keywords:
            phrase_clean = self.normalize_input(phrase) #NOTE: This could be cached for performance becomes an issue... like in the future
            if self.debug:
                self.logger.debug(f"[MATCH] Checking if '{phrase_clean}' in '{text_clean}'")
            if phrase_clean in text_clean:
                matches.append(phrase)

        if matches:
            self.logger.info(f"Matched event keywords: {matches} in '{text}'")
            return matches
        self.logger.debug("No matches found.")
        return None
    
    def check_for_emergency_word(self, text: str):
        emergency_words =  self.check_for_word(self.system_tools.get_emergency_words(), text)
        if self.debug:
            self.logger.debug(f"Emergency Words:{emergency_words}'")
        return emergency_words

    def check_for_wake_word(self, text: str):
        wake_words = self.check_for_word(self.system_tools.get_wake_words(), text)
        if self.debug:
            self.logger.debug(f"Wake Words:{wake_words}'")
        return wake_words

    def check_for_sleep_word(self, text: str):
        sleep_words = self.check_for_word(self.system_tools.get_sleep_words(), text)
        if self.debug:
            self.logger.debug(f"Sleep Words:{sleep_words}'")
        return sleep_words

    def check_for_shutdown_word(self, text: str):
        shutdown_words = self.check_for_word(self.system_tools.get_shutdown_words(), text)
        if self.debug:
            self.logger.debug(f"Shutdown Words:{shutdown_words}'")
        return shutdown_words

    @staticmethod
    def resolve_event_priority(events: list[dict]) -> dict | None:
        if not events:
            return None
        sorted_events = sorted(events, key=lambda e: EVENT_PRIORITY.get(e['type'], 99))
        return sorted_events[0]

    def determine_event_action(self, text: str) -> dict:
        self.logger.info(f"Determining event action for text: {text}")
        events = self.check_for_event_words(text)
        if not events:
            return {'event_type': EventType.CONTINUE, 'matches': []}

        structured_events = [{'type': k, 'matches': v} for k, v in events.items()]
        highest_priority_event = self.resolve_event_priority(structured_events)
        if not highest_priority_event:
            return {'event_type': EventType.CONTINUE, 'matches': []}

        return {
            'event_type': highest_priority_event['type'],
            'matches': highest_priority_event['matches']
        }
