# backend/routes/online_books_routes.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from routes.auth_middleware import jwt_required_custom
from services.online_books_service import OnlineBooksService
from services.online_book_processor import OnlineBookProcessor
from models.pdf_history import PdfHistory

online_books_bp = Blueprint('online_books', __name__)

@online_books_bp.route('', methods=['GET'])
@jwt_required_custom
def get_default_books():
    """Get default/featured books - called when no specific endpoint is specified"""
    try:
        limit = request.args.get('limit', 20, type=int)
        limit = min(limit, 50)  # Cap at 50
        
        result = OnlineBooksService.get_featured_books(limit)
        return jsonify(result), 200 if result['success'] else 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@online_books_bp.route('/featured', methods=['GET'])
@jwt_required_custom
def get_featured_books():
    """Get featured/most downloaded books from Project Gutenberg"""
    try:
        limit = request.args.get('limit', 20, type=int)
        limit = min(limit, 50)  # Cap at 50
        
        result = OnlineBooksService.get_featured_books(limit)
        return jsonify(result), 200 if result['success'] else 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@online_books_bp.route('/search', methods=['GET', 'POST'])
@jwt_required_custom
def search_books():
    """Search for books by title or author with fallback strategies"""
    try:
        if request.method == 'POST':
            data = request.get_json()
            query = data.get('query', '').strip()
        else:
            query = request.args.get('query', '').strip()
        
        if not query:
            return jsonify({'success': False, 'error': 'Search query required'}), 400
        
        limit = request.args.get('limit', 20, type=int)
        limit = min(limit, 50)
        
        result = OnlineBooksService.search_books(query, limit)
        return jsonify(result), 200 if result['success'] else 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@online_books_bp.route('/genre/<genre>', methods=['GET'])
@jwt_required_custom
def get_books_by_genre(genre):
    """Get books by genre/category"""
    try:
        genre = genre.strip()
        if not genre:
            return jsonify({'success': False, 'error': 'Genre required'}), 400
        
        limit = request.args.get('limit', 20, type=int)
        limit = min(limit, 50)
        
        result = OnlineBooksService.get_books_by_genre(genre, limit)
        return jsonify(result), 200 if result['success'] else 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@online_books_bp.route('/process', methods=['POST'])
@jwt_required_custom
def process_online_book():
    """Process online book - fetch text, extract sentences, and add to history"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        text_url = data.get('text_url', '').strip()
        if not text_url:
            return jsonify({'success': False, 'error': 'Text URL required'}), 400
        
        # Extract book metadata
        book_title = data.get('title', 'Online Book')
        book_author = data.get('author', 'Unknown')
        book_id = data.get('id', '')
        
        # Process the online book
        result = OnlineBookProcessor.extract_text_from_url(text_url)
        
        if result['success']:
            # Add to user's history
            try:
                history_id = PdfHistory.add_to_history(
                    user_id=user_id,
                    pdf_name=book_title,  # Use title as name
                    pdf_path=text_url,  # Use URL as path
                    total_pages=0,  # Online books don't have pages
                    total_sentences=result.get('sentence_count', 0),
                    file_size=result.get('character_count', 0),
                    # Additional metadata for online books
                    isOnlineBook=True,
                    text_url=text_url,
                    book_id=book_id,
                    author=book_author,
                    source='Project Gutenberg'
                )
                
                result['history_id'] = history_id
                result['added_to_history'] = True
            except Exception as history_error:
                print(f"[ERROR] Failed to add online book to history: {history_error}")
                result['warning'] = 'Book processed but could not save to history'
        
        return jsonify(result), 200 if result['success'] else 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@online_books_bp.route('/<int:book_id>/to-history', methods=['POST'])
@jwt_required_custom
def add_online_book_to_history(book_id):
    """Add an online book to user's history"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        book_title = data.get('title', f'Book {book_id}')
        book_author = data.get('author', 'Unknown')
        text_url = data.get('text_url', '')
        sentence_count = data.get('sentence_count', 0)
        character_count = data.get('character_count', 0)
        
        if not text_url:
            return jsonify({'success': False, 'error': 'Text URL required'}), 400
        
        history_id = PdfHistory.add_to_history(
            user_id=user_id,
            pdf_name=book_title,
            pdf_path=text_url,
            total_pages=0,
            total_sentences=sentence_count,
            file_size=character_count,
            # Additional metadata for online books
            isOnlineBook=True,
            text_url=text_url,
            book_id=str(book_id),
            author=book_author,
            source='Project Gutenberg'
        )
        
        return jsonify({
            'success': True,
            'message': 'Added to history',
            'history_id': history_id
        }), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

