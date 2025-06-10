from core.system.utils.system_tools import SystemTools
from core.system.logger import ThreadedLoggerManager
from setup.config_loader import ConfigLoader

import asyncio

class SessionMemoryManager:
    def __init__(self, config=None, logger=None):
        self.config = config or ConfigLoader().load_config()
        self.logger = logger or ThreadedLoggerManager.get_instance(__name__).get_logger()
        self.debug = self.config['system_settings'].get('debug_mode', False)
        self.system_tools = SystemTools(config=self.config, logger=self.logger)
        self.session_memory = {model: [] for model in SystemTools(self.config, self.logger).get_available_models()}

    def get_session_memory(self, model):
        self.logger.debug(f"Retrieving session memory for model: {model}")
        return self.session_memory.get(model, [])

    def append_to_session_memory(self, model, message):
        if model not in self.session_memory:
            self.session_memory[model] = []
            self.logger.info(f"Created new session list for model: {model}")
        safe_message = self.system_tools.safe_append_message(message['content'])
        if isinstance(safe_message, str) and safe_message.startswith("{'error':"):
            return self.logger.warning(f"Potential malformed input Rejected: {safe_message}")
        message['content'] = safe_message
        self.session_memory[model].append(message)
        self.logger.debug(f"Appended message to {model}: {message}")

    def clear_session_memory(self, model=None):
        if model:
            self.session_memory[model] = []
            self.logger.info(f"Cleared session memory for model: {model}")
        else:
            for key in self.session_memory:
                self.session_memory[key] = []
            self.logger.info("Cleared all session memory")

    def add_to_model_memory(self, role, model, message):
        input_data = {"role": role, "content": message}
        self.append_to_session_memory(model, input_data)

    def append_tool_to_model_memory(self, model, message):
        self.add_to_model_memory('tool', model, message)
    
    def append_system_to_model_memory(self, model, message):
        self.add_to_model_memory('system', model, message)

    def append_user_to_model_memory(self, model, message):
        self.add_to_model_memory('user', model, message)

    def append_model_to_model_memory(self, model, message):
        self.add_to_model_memory('assistant', model, message)
