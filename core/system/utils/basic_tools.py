import re
import os
import time
from core.system.logger import ThreadedLoggerManager

class BasicTools:
    logger = ThreadedLoggerManager("basic_tools").get_logger()

    @staticmethod
    def is_url(text):
        url_pattern = re.compile(
            r'^(https?:\/\/)'                   # required scheme
            r'(([\da-z\.-]+)\.([a-z\.]{2,6})|'   # domain
            r'(\d{1,3}\.){3}\d{1,3})'            # OR ipv4
            r'(:\d+)?'                           # optional port
            r'(\/[^\s]*)?$',                     # optional path
            re.IGNORECASE
        )
        return bool(url_pattern.match(text))

    @staticmethod
    def get_timeout(value, unit='seconds'):
        unit = unit.lower()
        if unit == 'seconds':
            return value
        elif unit == 'minutes':
            return value * 60
        elif unit == 'hours':
            return value * 3600
        else:
            raise ValueError("Invalid time unit. Use 'seconds', 'minutes', or 'hours'.")

    @staticmethod
    def cleanup_temp_audio(age_limit_secs=300):
        temp_dir = os.path.join(os.getcwd(), "temp_audio")
        if not os.path.exists(temp_dir):
            BasicTools.logger.debug(f"Temp directory not found: {temp_dir}")
            return

        now = time.time()
        for f in os.listdir(temp_dir):
            path = os.path.join(temp_dir, f)
            try:
                if os.path.isfile(path) and now - os.path.getmtime(path) > age_limit_secs:
                    os.remove(path)
                    BasicTools.logger.info(f"Deleted old temp file: {path}")
            except Exception as e:
                BasicTools.logger.warning(f"Failed to delete {path}: {e}")
