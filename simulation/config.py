"""
Simulation Module Configuration

Configuration settings for the simulation module.
"""

import os
from pathlib import Path

# Base directory for simulation data
SIMULATION_DATA_DIR = Path(__file__).parent.parent / "data" / "simulation"

# Ensure data directory exists
SIMULATION_DATA_DIR.mkdir(parents=True, exist_ok=True)

# JSONL file paths for each modality
SER_SIGNALS_FILE = SIMULATION_DATA_DIR / "SER_signals.jsonl"
FER_SIGNALS_FILE = SIMULATION_DATA_DIR / "FER_signals.jsonl"
VITALS_SIGNALS_FILE = SIMULATION_DATA_DIR / "Vitals_signals.jsonl"

# Default signal generation settings
DEFAULT_GENERATION_INTERVAL = 30  # seconds
DEFAULT_SIGNAL_COUNT = 1  # signals per generation

# Modality mappings
MODALITY_MAP = {
    "ser": "speech",
    "fer": "face",
    "vitals": "vitals"
}

# Valid emotion labels for each modality
VALID_EMOTIONS = {
    "ser": ["Happy", "Sad", "Angry", "Fear"],
    "fer": ["Happy", "Sad", "Angry", "Fear"],
    "vitals": ["Happy", "Sad", "Angry", "Fear"]
}


