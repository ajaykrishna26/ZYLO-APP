# backend/config.py
import os

class Config:
    SECRET_KEY = 'dyslexia-assistant-secret-key'
    DEBUG = False  # Optimized for production
    
    # Use absolute paths to avoid issues with relative paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    SELECTIONS_FOLDER = os.path.join(BASE_DIR, 'static', 'selections')
    
    # Performance optimizations
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    SPEECH_RATE = 80
    
    # Similarity threshold for pronunciation accuracy
    # Improved algorithm uses weighted metrics, so threshold can be adjusted
    # 0.7 = 70% similarity required (allows for minor pronunciation variations)
    # Adjust based on user feedback
    SIMILARITY_THRESHOLD = 0.72
    
    JSON_SORT_KEYS = False
    PROPAGATE_EXCEPTIONS = True

# Create directories
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(Config.SELECTIONS_FOLDER, exist_ok=True)