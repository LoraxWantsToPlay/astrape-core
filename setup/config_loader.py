from pathlib import Path
from omegaconf import OmegaConf
import yaml

from core.system.logger import ThreadedLoggerManager

class ConfigLoader:
    def __init__(self, config_path=None, default_path=None, logger=None):
        base_path = Path(__file__).parent
        self.config_path = config_path or base_path / "config.yaml"
        self.default_path = default_path or base_path / "config_defaults.yaml"
        self.logger = logger or ThreadedLoggerManager.get_instance(__name__).get_logger()

    def load_config(self):
        try:
            with open(self.default_path, "r") as f:
                default_cfg = OmegaConf.create(yaml.safe_load(f))
                self.logger.debug(f"Loaded default config from {self.default_path}")
        except Exception as e:
            self.logger.error(f"Failed to load default config: {e}")
            return None

        try:
            with open(self.config_path, "r") as f:
                user_cfg = OmegaConf.create(yaml.safe_load(f))
                self.logger.debug(f"Loaded user config from {self.config_path}")
        except FileNotFoundError:
            self.logger.warning(f"No user config found at {self.config_path}, using defaults.")
            user_cfg = OmegaConf.create({})
        except Exception as e:
            self.logger.error(f"Failed to load user config: {e}")
            return None

        final_cfg = OmegaConf.merge(default_cfg, user_cfg)
        self.logger.info("Configuration successfully merged and loaded.")
        return final_cfg


# Optional CLI/Direct use
if __name__ == "__main__":
    loader = ConfigLoader()
    config = loader.load_config()
    if config:
        loader.logger.info("Configuration loaded successfully.")
    else:
        loader.logger.error("Failed to load configuration.")
