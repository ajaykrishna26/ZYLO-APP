import os
from pymongo import MongoClient
from dotenv import load_dotenv
import certifi
import logging

load_dotenv()
logger = logging.getLogger(__name__)

client = None
db = None

def init_db():
    global client, db
    mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/dyslexia_assistant')
    
    try:
        # Masked URI for logging
        masked_uri = mongo_uri.split('@')[-1] if '@' in mongo_uri else 'unknown'
        logger.info(f'Attempting to connect to MongoDB cluster: {masked_uri}')
        
        client = MongoClient(
            mongo_uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
            socketTimeoutMS=30000,
            retryWrites=True,
            tlsCAFile=certifi.where()
        )
        
        db = client.get_database()
        logger.info(f'Connected to MongoDB successfully! Database: {db.name}')
        return db
    except Exception as e:
        logger.error(f'CRITICAL: Failed to connect to MongoDB: {str(e)}')
        return None

def get_db():
    global db, client
    
    if db is None:
        init_db()
        
    if db is None:
        error_msg = "MongoDB is not running or accessible. Please ensure: 1) MongoDB service is running, 2) Connection URI is correct, 3) Network connection is available."
        logger.error(error_msg)
        raise ConnectionError(error_msg)
    
    try:
        # Verify connection is still alive with a ping
        db.command('ping')
    except Exception as e:
        logger.error(f"Database ping failed: {e}")
        db = None
        raise ConnectionError(f"Database connection lost: {e}")
    
    return db

def get_users_collection():
    return get_db()['users']

def get_history_collection():
    return get_db()['history']
