import os
from dotenv import load_dotenv

# --- CẤU HÌNH HỆ THỐNG ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Tìm file .env ở thư mục gốc (chứ không phải trong thư mục core)
load_dotenv(os.path.join(BASE_DIR, "..", ".env"))

BASE_VIDEOS_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "videos"))
FPS = 30
HD_RES = (1920, 1080)

# --- CẤU HÌNH TẠO ẢNH (AUTOIMAGE) ---
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "")
MAX_CONCURRENT_REQUESTS = 9

# --- CẤU HÌNH TẠO ÂM THANH (AUTOAUDIO) ---
VIMIX_API_KEY = os.getenv("VIMIX_API_KEY", "")
VIMIX_BASE_URL = "https://vimix.io/api/v1"
VIMIX_VOICE_ID = "aN7cv9yXNrfIR87bDmyD"
VIMIX_PROVIDER = "ELEVENLABS"
VIMIX_MAX_CONCURRENT_JOBS = 6
