"""
Simulation Module for Testing

This module provides synthetic SER, FER, and Vitals signals for testing purposes.
It includes signal storage, generation, and demo mode management.
"""

__version__ = "1.0.0"

# Export main modules
from . import config
from . import demo_mode
from . import signal_storage
from . import signal_generator
from . import api
from . import dashboard
from . import emotion_bias
from . import generation_interval

__all__ = ["config", "demo_mode", "signal_storage", "signal_generator", "api", "dashboard", "emotion_bias", "generation_interval"]

