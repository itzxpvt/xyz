from dotenv import load_dotenv
import os

# Load .env file
load_dotenv(dotenv_path="config.env")

# Access environment variables
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

BINARY_PATH = "./bin"  # Path to your binary file
DEFAULT_THREADS = 100  # Integer, not string

# For list values, you typically load them separately or parse as needed
# You can also hard-code them if they are not sensitive
BOT_ADMINS = [6397654988, 9876543210]
