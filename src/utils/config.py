import yaml
from pathlib import Path
import os
import logging

logger = logging.getLogger(__name__)

def load_config(config_path: str = "config/config.yaml"):
    """Loads configuration from a YAML file."""
    config_file = Path(config_path)
    if not config_file.exists():
        logger.error(f"Configuration file not found at {config_file}")
        raise FileNotFoundError(f"Configuration file not found at {config_file}")

    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
            logger.info(f"Configuration loaded from {config_file}")
            return config
    except yaml.YAMLError as e:
        logger.error(f"Error parsing configuration file {config_file}: {e}")
        raise ValueError(f"Error parsing configuration file {config_file}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading configuration from {config_file}: {e}")
        raise 