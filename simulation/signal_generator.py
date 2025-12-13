#!/usr/bin/env python3
"""
Signal Generator Script

Generates synthetic SER, FER, and Vitals signals for testing.
Can run continuously (every N seconds) or one-time.
Respects demo mode - only generates when demo mode is enabled.

Usage:
    python -m simulation.signal_generator --modality all --interval 30 --cloud-url http://localhost:8008
    python -m simulation.signal_generator --modality ser --once --user-id <uuid>
"""

import sys
import os
import argparse
import time
import random
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional
import httpx

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import ModelSignal
from app.database import insert_voice_emotion, insert_face_emotion_synthetic, insert_vitals_emotion_synthetic
from simulation.config import MODALITY_MAP, VALID_EMOTIONS, DEFAULT_GENERATION_INTERVAL, DEFAULT_SIGNAL_COUNT
from simulation.demo_mode import DemoModeManager
from simulation.emotion_bias import EmotionBiasManager
from simulation.modality_toggle import ModalityToggleManager
from simulation.user_id import UserIdManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_malaysia_timezone():
    """Get Malaysia timezone (UTC+8)."""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("Asia/Kuala_Lumpur")
    except (ImportError, Exception):
        try:
            import pytz
            return pytz.timezone("Asia/Kuala_Lumpur")
        except ImportError:
            from datetime import timezone, timedelta
            return timezone(timedelta(hours=8))


def generate_random_signals(
    user_id: str,
    modality: str,
    timestamp: datetime,
    count: int = 1,
    bias_emotion: Optional[str] = None
) -> List[ModelSignal]:
    """
    Generate random ModelSignal objects for a given modality.
    
    Args:
        user_id: User ID for signals
        modality: Modality name ("ser", "fer", "vitals")
        timestamp: Base timestamp for signals
        count: Number of signals to generate
        bias_emotion: Optional emotion to bias toward ("Happy", "Sad", "Fear", "Angry")
                     If set, biased emotion has 75% probability, others share 25%
        
    Returns:
        List of ModelSignal objects
    """
    modality_lower = modality.lower()
    
    # Map modality to ModelSignal modality string
    if modality_lower == "ser":
        signal_modality = "speech"
    elif modality_lower == "fer":
        signal_modality = "face"
    elif modality_lower == "vitals":
        signal_modality = "vitals"
    else:
        raise ValueError(f"Unknown modality: {modality}")
    
    # Get valid emotions for this modality
    emotions = VALID_EMOTIONS.get(modality_lower, ["Happy", "Sad", "Angry", "Fear"])
    
    # Validate bias_emotion is in the valid emotions list
    if bias_emotion and bias_emotion not in emotions:
        logger.warning(f"Bias emotion {bias_emotion} not in valid emotions for {modality}, ignoring bias")
        bias_emotion = None
    
    # Create weighted selection if bias is set
    if bias_emotion:
        # 75% probability for biased emotion, 25% split among others
        other_emotions = [e for e in emotions if e != bias_emotion]
        weights = [0.75] + [0.25 / len(other_emotions)] * len(other_emotions)
        weighted_emotions = [bias_emotion] + other_emotions
    else:
        # Equal probability for all emotions
        weighted_emotions = emotions
        weights = [1.0 / len(emotions)] * len(emotions)
    
    signals = []
    malaysia_tz = get_malaysia_timezone()
    
    for i in range(count):
        # Weighted random emotion selection
        emotion = random.choices(weighted_emotions, weights=weights, k=1)[0]
        confidence = round(random.uniform(0.5, 0.95), 2)
        
        # Add small time offset for multiple signals
        signal_timestamp = timestamp + timedelta(seconds=i * random.uniform(1, 10))
        
        # Ensure timestamp is timezone-aware
        if signal_timestamp.tzinfo is None:
            signal_timestamp = malaysia_tz.localize(signal_timestamp)
        
        signal = ModelSignal(
            user_id=user_id,
            timestamp=signal_timestamp.isoformat(),
            modality=signal_modality,
            emotion_label=emotion,
            confidence=confidence
        )
        signals.append(signal)
    
    return signals


async def check_demo_mode(cloud_url: str) -> bool:
    """
    Check if demo mode is enabled on the cloud service.
    
    Args:
        cloud_url: Base URL of the cloud service
        
    Returns:
        True if demo mode is enabled, False otherwise
    """
    try:
        demo_mode_url = f"{cloud_url}/simulation/demo-mode"
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(demo_mode_url)
            response.raise_for_status()
            data = response.json()
            return data.get("enabled", False)
    except Exception as e:
        logger.warning(f"Could not check demo mode status: {e}. Assuming demo mode is OFF.")
        return False


async def send_signals_to_cloud(
    cloud_url: str,
    modality: str,
    signals: List[ModelSignal]
) -> bool:
    """
    Send signals to cloud service via API endpoint.
    
    Args:
        cloud_url: Base URL of the cloud service
        modality: Modality name ("ser", "fer", "vitals")
        signals: List of ModelSignal objects to send
        
    Returns:
        True if successful, False otherwise
    """
    try:
        inject_url = f"{cloud_url}/simulation/inject-signals"
        payload = {
            "modality": modality.lower(),
            "signals": [signal.dict() for signal in signals]
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                inject_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            logger.info(f"Successfully sent {len(signals)} signals to cloud ({modality})")
            return True
    except Exception as e:
        logger.error(f"Error sending signals to cloud: {e}", exc_info=True)
        return False


def write_signals_locally(
    modality: str,
    signals: List[ModelSignal]
) -> None:
    """
    Write signals directly to database tables.
    
    Args:
        modality: Modality name ("ser", "fer", "vitals")
        signals: List of ModelSignal objects to write
    """
    try:
        modality_lower = modality.lower()
        success_count = 0
        
        for signal in signals:
            # Parse timestamp from ISO string
            signal_timestamp = datetime.fromisoformat(signal.timestamp.replace('Z', '+00:00'))
            malaysia_tz = get_malaysia_timezone()
            if signal_timestamp.tzinfo is None:
                signal_timestamp = signal_timestamp.replace(tzinfo=malaysia_tz)
            else:
                signal_timestamp = signal_timestamp.astimezone(malaysia_tz)
            
            if modality_lower == "ser":
                # Write to voice_emotion table
                # Create analysis_result dict from ModelSignal
                analysis_result = {
                    "emotion": signal.emotion_label.lower()[:3] if len(signal.emotion_label.lower()) >= 3 else signal.emotion_label.lower(),  # Convert "Happy" -> "hap", etc.
                    "emotion_confidence": signal.confidence,
                    "transcript": None,
                    "language": None,
                    "sentiment": None,
                    "sentiment_confidence": None
                }
                # Map fusion emotion back to SER emotion format
                emotion_map = {
                    "Happy": "hap",
                    "Sad": "sad",
                    "Angry": "ang",
                    "Fear": "fea"
                }
                analysis_result["emotion"] = emotion_map.get(signal.emotion_label, signal.emotion_label.lower()[:3])
                
                audio_metadata = {
                    "sample_rate": 16000,
                    "frame_size_ms": 25.0,
                    "frame_stride_ms": 10.0,
                    "duration_sec": 10.0
                }
                
                result = insert_voice_emotion(
                    user_id=signal.user_id,
                    timestamp=signal_timestamp,
                    analysis_result=analysis_result,
                    audio_metadata=audio_metadata,
                    is_synthetic=True
                )
                if result:
                    success_count += 1
                    
            elif modality_lower == "fer":
                # Write to face_emotion table
                result = insert_face_emotion_synthetic(
                    user_id=signal.user_id,
                    timestamp=signal_timestamp,
                    emotion_label=signal.emotion_label,
                    confidence=signal.confidence,
                    is_synthetic=True
                )
                if result:
                    success_count += 1
                    
            elif modality_lower == "vitals":
                # Write to bvs_emotion table
                result = insert_vitals_emotion_synthetic(
                    user_id=signal.user_id,
                    timestamp=signal_timestamp,
                    emotion_label=signal.emotion_label,
                    confidence=signal.confidence,
                    is_synthetic=True
                )
                if result:
                    success_count += 1
            else:
                logger.warning(f"Unknown modality: {modality}")
        
        logger.info(f"Successfully wrote {success_count}/{len(signals)} signals to database ({modality})")
    except Exception as e:
        logger.error(f"Error writing signals to database: {e}", exc_info=True)
        raise


async def generate_and_send_signals(
    modality: str,
    user_id: Optional[str] = None,
    count: int = DEFAULT_SIGNAL_COUNT,
    cloud_url: Optional[str] = None
) -> None:
    """
    Generate signals and send them (to cloud or local).
    
    Args:
        modality: Modality name ("ser", "fer", "vitals")
        user_id: User ID for signals (if None, uses UserIdManager)
        count: Number of signals to generate
        cloud_url: Optional cloud URL to send to (if None, writes locally)
    """
    # Get user_id from UserIdManager if not provided
    if user_id is None:
        user_id_manager = UserIdManager.get_instance()
        user_id = user_id_manager.get_user_id()
    
    malaysia_tz = get_malaysia_timezone()
    now = datetime.now(malaysia_tz)
    
    # Get emotion bias for this modality
    bias_manager = EmotionBiasManager.get_instance()
    bias_emotion = bias_manager.get_bias(modality)
    
    # Generate random signals with bias
    signals = generate_random_signals(user_id, modality, now, count=count, bias_emotion=bias_emotion)
    
    bias_info = f" (bias: {bias_emotion})" if bias_emotion else ""
    logger.info(
        f"Generated {len(signals)} signals for {modality}{bias_info}: "
        f"{[f'{s.emotion_label}({s.confidence:.2f})' for s in signals]}"
    )
    
    # Send to cloud or write locally
    if cloud_url:
        success = await send_signals_to_cloud(cloud_url, modality, signals)
        if not success:
            logger.warning(f"Failed to send to cloud, writing locally instead")
            write_signals_locally(modality, signals)
    else:
        write_signals_locally(modality, signals)


async def continuous_generation_loop(
    modalities: List[str],
    user_id: str,
    interval: int,
    count: int,
    cloud_url: Optional[str] = None
) -> None:
    """
    Continuously generate signals at specified intervals.
    Checks demo mode before each generation.
    
    Args:
        modalities: List of modality names to generate for
        user_id: User ID for signals
        interval: Generation interval in seconds
        count: Number of signals per generation
        cloud_url: Optional cloud URL to send to
    """
    logger.info(f"Starting continuous generation loop (interval: {interval}s)")
    
    while True:
        try:
            # Check demo mode if cloud URL is provided
            if cloud_url:
                demo_enabled = await check_demo_mode(cloud_url)
                if not demo_enabled:
                    logger.info("Demo mode is OFF. Waiting for demo mode to be enabled...")
                    await asyncio.sleep(interval)
                    continue
            
            # Generate signals for each modality (only if enabled)
            toggle_manager = ModalityToggleManager.get_instance()
            for modality in modalities:
                if toggle_manager.is_enabled(modality):
                    await generate_and_send_signals(modality, user_id, count, cloud_url)
                else:
                    logger.debug(f"Skipping {modality} generation (disabled)")
            
            # Wait for next interval
            logger.debug(f"Waiting {interval} seconds until next generation...")
            await asyncio.sleep(interval)
        
        except KeyboardInterrupt:
            logger.info("Generation loop interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in generation loop: {e}", exc_info=True)
            await asyncio.sleep(interval)


async def main():
    """Main entry point for signal generator."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic SER, FER, and Vitals signals for testing"
    )
    parser.add_argument(
        "--modality",
        choices=["ser", "fer", "vitals", "all"],
        default="all",
        help="Modality to generate signals for (default: all)"
    )
    parser.add_argument(
        "--user-id",
        type=str,
        default=os.getenv("DEV_USER_ID", "96975f52-5b05-4eb1-bfa5-530485112518"),
        help="User ID for signals (default: from DEV_USER_ID env var)"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_SIGNAL_COUNT,
        help=f"Number of signals per generation (default: {DEFAULT_SIGNAL_COUNT})"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_GENERATION_INTERVAL,
        help=f"Generation interval in seconds for continuous mode (default: {DEFAULT_GENERATION_INTERVAL})"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Generate once and exit (default: continuous mode)"
    )
    parser.add_argument(
        "--cloud-url",
        type=str,
        default=None,
        help="Cloud service URL to send signals to (default: write locally)"
    )
    
    args = parser.parse_args()
    
    # Determine modalities to generate
    if args.modality == "all":
        modalities = ["ser", "fer", "vitals"]
    else:
        modalities = [args.modality]
    
    logger.info(f"Signal Generator starting:")
    logger.info(f"  Modalities: {modalities}")
    logger.info(f"  User ID: {args.user_id}")
    logger.info(f"  Count per generation: {args.count}")
    logger.info(f"  Mode: {'one-time' if args.once else 'continuous'}")
    if args.once:
        logger.info(f"  Interval: N/A")
    else:
        logger.info(f"  Interval: {args.interval}s")
    logger.info(f"  Destination: {'cloud' if args.cloud_url else 'local'}")
    if args.cloud_url:
        logger.info(f"  Cloud URL: {args.cloud_url}")
    
    try:
        if args.once:
            # Generate once and exit
            for modality in modalities:
                await generate_and_send_signals(
                    modality,
                    args.user_id,
                    args.count,
                    args.cloud_url
                )
            logger.info("One-time generation completed")
        else:
            # Continuous generation
            await continuous_generation_loop(
                modalities,
                args.user_id,
                args.interval,
                args.count,
                args.cloud_url
            )
    except KeyboardInterrupt:
        logger.info("Signal generator interrupted by user")
    except Exception as e:
        logger.error(f"Signal generator error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())


