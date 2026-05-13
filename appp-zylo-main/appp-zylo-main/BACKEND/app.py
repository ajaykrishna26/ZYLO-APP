# backend/app.py
from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from datetime import timedelta
from config import Config
from dotenv import load_dotenv
import os
import shutil
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Import database and blueprints
from db import init_db
from routes.pdf_routes import pdf_bp
from routes.practice_routes import practice_bp
from routes.selection_routes import selection_bp
from routes.auth_routes import auth_bp
from routes.history_routes import history_bp
from routes.admin_routes import admin_bp
from routes.online_books_routes import online_books_bp

# Check dependencies
if shutil.which("ffmpeg"):
    logger.info("FFmpeg found in system PATH")

if not (shutil.which("espeak") or shutil.which("espeak-ng")):
    logger.warning("eSpeak not available - Pronunciation features will be limited")


def create_app():
    """Initialize Flask application with optimized configuration."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # JWT Configuration
    app.config['JWT_SECRET_KEY'] = os.getenv(
        'JWT_SECRET_KEY',
        'zylo-jwt-secret-key-default-change-me'
    )
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=30)
    app.config['JSON_SORT_KEYS'] = False

    JWTManager(app)
    init_db()

    # CORS configuration for web and mobile apps
    CORS(app,
         origins=[
             "http://localhost:5000",
             "http://localhost:3000",
             "http://127.0.0.1:3000",
             "http://127.0.0.1:5000",
             "http://192.168.1.6:5000",
             "https://*.hf.space",      # Allow all Hugging Face Spaces
             "https://huggingface.co",   # Allow HF main domain
         ],
         supports_credentials=True,
         max_age=3600
    )

    # Register blueprints
    app.register_blueprint(pdf_bp, url_prefix='/api/pdf')
    app.register_blueprint(practice_bp, url_prefix='/api/practice')
    app.register_blueprint(selection_bp, url_prefix='/api/selection')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(history_bp, url_prefix='/api/history')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(online_books_bp, url_prefix='/api/online-books')

    # Initialize SpeechService to load Whisper model on startup
    try:
        from services.speech_service import SpeechService
        logger.info("[STARTUP] Pre-loading SpeechService...")
        speech_service = SpeechService()
        logger.info("[STARTUP] SpeechService initialized successfully")
    except Exception as e:
        logger.error(f"[STARTUP] Warning: Failed to initialize SpeechService: {e}")
        logger.error("[STARTUP] Speech features may be unavailable")

    # Home page route
    @app.route('/', methods=['GET'])
    def home():
        return jsonify({
            'message': 'Welcome to the Dyslexia Reading Assistant API!',
            'health_check': '/api/health',
            'status': 'online'
        })

    # Health check endpoint (minimal overhead)
    @app.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({
            'status': 'healthy',
            'service': 'Dyslexia Reading Assistant API',
            'version': '1.0.0'
        })

    # Debug endpoint - shows connection info
    @app.route('/api/debug/connection', methods=['GET'])
    def debug_connection():
        from flask import request
        return jsonify({
            'status': 'connected',
            'client_ip': request.remote_addr,
            'server_ip': '192.168.1.6',
            'port': 5000,
            'api_base': 'http://192.168.1.6:5000',
            'message': 'If you can see this, the connection is working!'
        })

    return app


if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get("PORT", 7860))
    logger.info(f"API starting at http://0.0.0.0:{port}")
    app.run(debug=False, host='0.0.0.0', port=port)
