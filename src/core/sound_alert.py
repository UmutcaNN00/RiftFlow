import io
import math
import struct
import wave
import logging
import threading

logger = logging.getLogger(__name__)

_CHIME_WAV_BYTES = None
_INIT_LOCK = threading.Lock()

def _generate_hextech_chime_wav() -> bytes:
    """
    Generates an in-memory 16-bit mono 44.1kHz WAV containing a crisp,
    elegant 2-tone Hextech chime (D5 -> A5) with smooth envelope shaping.
    """
    sample_rate = 44100
    
    # Tone 1: 587.33 Hz (D5) for 140ms
    # Tone 2: 880.00 Hz (A5) for 280ms
    # Gap: 20ms
    samples = []
    
    # Note 1: D5
    n1_len = int(sample_rate * 0.14)
    f1 = 587.33
    for i in range(n1_len):
        t = i / sample_rate
        # Envelope: fast attack (10ms), smooth decay
        att = min(1.0, i / (sample_rate * 0.015))
        dec = math.exp(-3.5 * (i / n1_len))
        env = att * dec
        val = math.sin(2.0 * math.pi * f1 * t) * 0.75 + math.sin(4.0 * math.pi * f1 * t) * 0.15
        samples.append(val * env)
        
    # Gap
    gap_len = int(sample_rate * 0.02)
    samples.extend([0.0] * gap_len)
    
    # Note 2: A5
    n2_len = int(sample_rate * 0.28)
    f2 = 880.00
    for i in range(n2_len):
        t = i / sample_rate
        att = min(1.0, i / (sample_rate * 0.012))
        dec = math.exp(-3.0 * (i / n2_len))
        env = att * dec
        val = math.sin(2.0 * math.pi * f2 * t) * 0.80 + math.sin(4.0 * math.pi * f2 * t) * 0.20
        samples.append(val * env)
        
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wav_file:
        wav_file.setnchannels(1)       # Mono
        wav_file.setsampwidth(2)      # 16-bit
        wav_file.setframerate(sample_rate)
        # Pack to 16-bit signed little-endian integers
        packed_frames = bytearray()
        for s in samples:
            clamped = max(-1.0, min(1.0, s))
            int_val = int(clamped * 32767.0)
            packed_frames.extend(struct.pack('<h', int_val))
        wav_file.writeframes(packed_frames)
        
    return buf.getvalue()

def get_chime_wav_bytes() -> bytes:
    global _CHIME_WAV_BYTES
    if _CHIME_WAV_BYTES is None:
        with _INIT_LOCK:
            if _CHIME_WAV_BYTES is None:
                try:
                    _CHIME_WAV_BYTES = _generate_hextech_chime_wav()
                except Exception as e:
                    logger.error(f"Failed to generate chime WAV: {e}")
                    _CHIME_WAV_BYTES = b""
    return _CHIME_WAV_BYTES

def play_match_found_sound():
    """
    Plays the non-blocking chime alert on Windows.
    Safe to call from any thread.
    """
    try:
        import winsound
        wav_data = get_chime_wav_bytes()
        if wav_data:
            winsound.PlaySound(wav_data, winsound.SND_MEMORY | winsound.SND_ASYNC)
        else:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    except Exception as e:
        logger.debug(f"Could not play sound: {e}")

def test_sound():
    play_match_found_sound()
