import os
import numpy as np
from scipy.io import wavfile
from elevenlabs import ElevenLabs
from ..config import ELEVENLABS_KEY, TEST_MODE, ELEVENLABS_VOICES, DEFAULT_VOICE
import asyncio
from pydub import AudioSegment

eleven_client = ElevenLabs(api_key=ELEVENLABS_KEY)

def create_mock_audio(duration=5, sample_rate=44100):
    """Create a simple sine wave audio file."""
    t = np.linspace(0, duration, int(sample_rate * duration))
    audio = np.sin(2 * np.pi * 440 * t)  # 440 Hz sine wave
    audio = (audio * 32767).astype(np.int16)  # Convert to 16-bit PCM
    return audio, sample_rate

async def generate_voice_over(text: str, output_path: str, voice_name: str = None):
    """
    Generate voice-over for the text.
    
    Args:
        text (str): The text to convert to speech
        output_path (str): Where to save the audio file
        voice_name (str, optional): Name of the voice to use
    """
    if TEST_MODE:
        audio, sample_rate = create_mock_audio(duration=10)  # 10 seconds of audio
        wavfile.write(output_path, sample_rate, audio)
        return
    
    # Get the voice ID
    voice_name = voice_name.lower() if voice_name else DEFAULT_VOICE
    if voice_name not in ELEVENLABS_VOICES:
        print(f"Warning: Unknown voice '{voice_name}'. Using default voice '{DEFAULT_VOICE}'.")
        voice_name = DEFAULT_VOICE
    
    voice_id = ELEVENLABS_VOICES[voice_name]
    
    # Generate audio using the text-to-speech endpoint
    audio_stream = eleven_client.text_to_speech.convert(
        text=text,
        voice_id=voice_id
    )
    
    # Convert generator to bytes
    audio_data = b''.join(chunk for chunk in audio_stream)
    
    # Save the audio
    with open(output_path, 'wb') as f:
        f.write(audio_data)

async def generate_dialogue(dialogues: list, output_path: str, voice1: str = "rachel", voice2: str = "josh"):
    """
    Generate a dialogue between two speakers.
    
    Args:
        dialogues (list): List of tuples containing (speaker_number, text)
            speaker_number should be 1 or 2
        output_path (str): Where to save the final audio file
        voice1 (str): Voice to use for speaker 1
        voice2 (str): Voice to use for speaker 2
    """
    if TEST_MODE:
        audio, sample_rate = create_mock_audio(duration=len(dialogues) * 5)  # 5 seconds per dialogue
        wavfile.write(output_path, sample_rate, audio)
        return

    # Create temporary directory for individual audio files
    temp_dir = os.path.join(os.path.dirname(output_path), "temp_audio")
    os.makedirs(temp_dir, exist_ok=True)

    try:
        # Generate individual audio files for each dialogue
        audio_files = []
        for i, (speaker, text) in enumerate(dialogues):
            temp_path = os.path.join(temp_dir, f"dialogue_{i}.mp3")
            voice = voice1 if speaker == 1 else voice2
            await generate_voice_over(text, temp_path, voice)
            audio_files.append(temp_path)

        # Combine all audio files with a small pause between them
        combined = AudioSegment.empty()
        pause = AudioSegment.silent(duration=500)  # 500ms pause between speakers

        for audio_file in audio_files:
            segment = AudioSegment.from_mp3(audio_file)
            combined += segment + pause

        # Export the final audio
        combined.export(output_path, format="mp3")

    finally:
        # Clean up temporary files
        for file in audio_files:
            if os.path.exists(file):
                os.remove(file)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)

async def generate_background_music(duration: int, output_path: str):
    """Generate background music."""
    if TEST_MODE:
        audio, sample_rate = create_mock_audio(duration=duration)
        wavfile.write(output_path, sample_rate, audio)
        return
    
    # TODO: Implement real background music generation
    # For now, just create a mock audio file
    audio, sample_rate = create_mock_audio(duration=duration)
    wavfile.write(output_path, sample_rate, audio)

async def generate_music(music_prompt: str, output_path: str):
    """
    Generate music based on a prompt.
    This will eventually integrate with Suno API or similar.
    """
    if TEST_MODE:
        audio, sample_rate = create_mock_audio(duration=60) # Mock 60 seconds of music
        wavfile.write(output_path, sample_rate, audio)
        print(f"Test mode: Generated mock music for prompt: '{music_prompt}'")
        return

    # TODO: Integrate with Suno API or another music generation service
    # For now, it will just create a mock audio file if not in TEST_MODE
    print(f"Warning: Suno API integration not yet implemented. Generating mock music for prompt: '{music_prompt}'")
    audio, sample_rate = create_mock_audio(duration=60) # Mock 60 seconds of music
    wavfile.write(output_path, sample_rate, audio)

async def generate_audiobook(text: str, output_path: str, voice_name: str = None):
    """
    Generate an audiobook from text using ElevenLabs.
    """
    if TEST_MODE:
        audio, sample_rate = create_mock_audio(duration=len(text) / 10) # Estimate duration based on text length
        wavfile.write(output_path, sample_rate, audio)
        print(f"Test mode: Generated mock audiobook for text (first 50 chars): '{text[:50]}...'")
        return
    
    print(f"Generating audiobook for text (first 50 chars): '{text[:50]}...'")
    await generate_voice_over(text, output_path, voice_name)
    print(f"Audiobook generated at: {output_path}")