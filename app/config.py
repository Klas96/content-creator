import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Keys
ANTHROPIC_KEY = os.getenv('ANTHROPIC_KEY')
OPENAI_KEY = os.getenv('OPENAI_KEY')
if not ANTHROPIC_KEY and not OPENAI_KEY:
    raise ValueError("Either ANTHROPIC_KEY or OPENAI_KEY must be set in environment variables")

STABILITY_KEY = os.getenv('STABILITY_KEY')
if not STABILITY_KEY:
    raise ValueError("STABILITY_KEY not found in environment variables")

ELEVENLABS_KEY = os.getenv('ELEVENLABS_KEY')
if not ELEVENLABS_KEY:
    raise ValueError("ELEVENLABS_KEY not found in environment variables")

SUNO_API_KEY = os.getenv('SUNO_API_KEY')
# SUNO_API_KEY is optional for now, as it's a new feature

# Configuration
TEST_MODE = os.getenv('TEST_MODE', 'False').lower() == 'true'
OUTPUT_DIR = os.getenv('OUTPUT_DIR', 'output')

# LLM Provider Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
OLLAMA_API_BASE_URL = os.getenv("OLLAMA_API_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL_NAME = os.getenv("OLLAMA_MODEL_NAME", "llama2")

# OpenAI Configuration
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "4000"))

# ElevenLabs Voice Configuration
ELEVENLABS_VOICES = {
    "rachel": "21m00Tcm4TlvDq8ikWAM",  # Professional female voice
    "domi": "AZnzlk1XvdvUeBnXmlld",    # Professional female voice
    "bella": "EXAVITQu4vr4xnSDxMaL",   # Professional female voice
    "antoni": "ErXwobaYiN019PkySvjV",  # Professional male voice
    "elli": "MF3mGyEYCl7XYWbV9V6O",    # Professional female voice
    "josh": "TxGEqnHWrfWFTfGW9XjX",    # Professional male voice
    "arnold": "VR6AewLTigWG4xSOukaG",  # Professional male voice
    "adam": "pNInz6obpgDQGcFmaJgB",    # Professional male voice
    "sam": "yoZ06aMxZJJ28mfd3POQ",     # Professional male voice
}

# Default voice to use if none specified
DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", "rachel")
