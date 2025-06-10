import logging
import logging.handlers
import os
from queue import Queue
from threading import Lock

class ThreadedLoggerManager:
    _instances = {}
    _lock = Lock()

    def __init__(self, name, log_level=logging.DEBUG, log_dir=None):
        self.name = name
        self.log_level = log_level
        self.log_dir = log_dir or os.path.join(os.getcwd(), "logs")
        os.makedirs(self.log_dir, exist_ok=True)

        self.logger = logging.getLogger(name)
        self.logger.setLevel(log_level)

        self.log_queue = Queue(-1)
        self.queue_handler = logging.handlers.QueueHandler(self.log_queue)

        formatter = logging.Formatter('%(asctime)s [%(name)s] [%(levelname)s] %(message)s')

        self.file_handler = logging.FileHandler(os.path.join(self.log_dir, f"{name}.log"))
        self.file_handler.setFormatter(formatter)

        self.stream_handler = logging.StreamHandler()
        self.stream_handler.setFormatter(formatter)

        self.listener = logging.handlers.QueueListener(
            self.log_queue, self.file_handler, self.stream_handler
        )

        self._initialized = False
        self._setup_logger()

    def _setup_logger(self):
        if not self._initialized:
            if not any(isinstance(h, logging.handlers.QueueHandler) for h in self.logger.handlers):
                self.logger.addHandler(self.queue_handler)
            self.listener.start()
            self._initialized = True

    def get_logger(self):
        return self.logger

    def shutdown(self):
        try:
            if hasattr(self.listener, "_thread") and self.listener._thread:
                self.listener.stop()
        except Exception as e:
            print(f"[Logger Warning] Failed to stop listener: {e}")

        for handler in [self.file_handler, self.stream_handler]:
            try:
                handler.flush()
                handler.close()
            except Exception:
                pass
        self.logger.handlers.clear()


    @classmethod
    def get_instance(cls, name, log_level=logging.DEBUG, log_dir=None):
        with cls._lock:
            if name not in cls._instances:
                cls._instances[name] = cls(name, log_level, log_dir)
            return cls._instances[name]

    @classmethod
    def shutdown_all(cls):
        with cls._lock:
            for instance in cls._instances.values():
                instance.shutdown()
            cls._instances.clear()
