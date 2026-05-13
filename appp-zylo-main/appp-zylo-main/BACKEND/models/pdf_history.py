from datetime import datetime
from bson import ObjectId
from db import get_history_collection

class PdfHistory:
    """Model for managing PDF reading history and progress"""
    
    @staticmethod
    def cleanup_duplicates(user_id):
        """Remove all duplicate entries for a user, keeping only the most recent one per book
        
        Handles both uploaded PDFs (matched by pdf_name) and online books (matched by text_url)
        
        Args:
            user_id: User's MongoDB ObjectId
            
        Returns:
            Number of entries deleted
        """
        history = get_history_collection()
        user_id_obj = ObjectId(user_id) if isinstance(user_id, str) else user_id
        
        # Get all entries for this user
        all_entries = list(history.find({'user_id': user_id_obj}).sort('updated_at', -1))
        
        deleted_count = 0
        seen_uploaded_pdfs = {}  # Track by pdf_name
        seen_online_books = {}   # Track by text_url or book_id
        
        # Sort entries by: online books first, then uploaded PDFs
        online_books = [e for e in all_entries if e.get('isOnlineBook')]
        uploaded_pdfs = [e for e in all_entries if not e.get('isOnlineBook')]
        
        # Process online books - deduplicate by text_url (primary) or book_id (secondary)
        for entry in online_books:
            # Use text_url if available, otherwise use book_id
            unique_key = entry.get('text_url') or entry.get('book_id') or entry.get('pdf_name')
            
            if unique_key and unique_key not in seen_online_books:
                # First occurrence - keep this one
                seen_online_books[unique_key] = entry['_id']
            else:
                # Duplicate - delete it
                result = history.delete_one({'_id': entry['_id']})
                deleted_count += result.deleted_count
        
        # Process uploaded PDFs - deduplicate by pdf_name
        for entry in uploaded_pdfs:
            pdf_name = entry.get('pdf_name', '')
            
            if pdf_name not in seen_uploaded_pdfs:
                # First occurrence - keep this one
                seen_uploaded_pdfs[pdf_name] = entry['_id']
            else:
                # Duplicate - delete it
                result = history.delete_one({'_id': entry['_id']})
                deleted_count += result.deleted_count
        
        return deleted_count
    
    @staticmethod
    def find_existing_entry(user_id, pdf_name, pdf_path=None):
        """Check if a book already exists in user's history
        
        Uses pdf_name for matching (original filename) to detect re-uploads
        Only matches uploaded PDFs, not online books
        
        Args:
            user_id: User's MongoDB ObjectId
            pdf_name: Name of the PDF/book (original filename)
            pdf_path: Path to the file (optional, not used for matching)
            
        Returns:
            Existing entry dict if found, None if not found
        """
        history = get_history_collection()
        # Only check pdf_name, not pdf_path (since UUID changes on each upload)
        existing = history.find_one({
            'user_id': ObjectId(user_id) if isinstance(user_id, str) else user_id,
            'pdf_name': pdf_name,
            'isOnlineBook': {'$ne': True}  # Only match uploaded PDFs, not online books
        })
        return existing
    
    @staticmethod
    def find_existing_online_book(user_id, text_url=None, book_id=None):
        """Check if an online book already exists in user's history
        
        Uses text_url (primary) or book_id (secondary) for matching
        Only matches online books, not uploaded PDFs
        
        Args:
            user_id: User's MongoDB ObjectId
            text_url: URL of the online book text
            book_id: Book ID from the source (e.g., Project Gutenberg ID)
            
        Returns:
            Existing entry dict if found, None if not found
        """
        history = get_history_collection()
        user_id_obj = ObjectId(user_id) if isinstance(user_id, str) else user_id
        
        # Try to match by text_url first (most reliable)
        if text_url:
            existing = history.find_one({
                'user_id': user_id_obj,
                'text_url': text_url,
                'isOnlineBook': True
            })
            if existing:
                return existing
        
        # Try to match by book_id if text_url didn't match
        if book_id:
            existing = history.find_one({
                'user_id': user_id_obj,
                'book_id': book_id,
                'isOnlineBook': True
            })
            if existing:
                return existing
        
        return None
    

    
    @staticmethod
    def add_to_history(user_id, pdf_name, pdf_path=None, total_pages=0, total_sentences=0, file_size=0, **kwargs):
        """Add a new entry to user's history or update if already exists
        
        Automatically deduplicates entries:
        - For uploaded PDFs: matches by pdf_name
        - For online books: matches by text_url (primary) or book_id (secondary)
        
        Args:
            user_id: User's MongoDB ObjectId
            pdf_name: Name of the PDF/book (original filename)
            pdf_path: Path to the file or identifier
            total_pages: Number of pages
            total_sentences: Number of sentences
            file_size: File size in bytes
            **kwargs: Additional metadata (text_url, isOnlineBook, author, source, book_id, etc.)
            
        Returns:
            history_id: ID of the entry (new or existing)
        """
        history = get_history_collection()
        user_id_obj = ObjectId(user_id) if isinstance(user_id, str) else user_id
        
        is_online_book = kwargs.get('isOnlineBook', False)
        
        # Determine which entry to match based on book type
        existing = None
        if is_online_book:
            # For online books, match by text_url or book_id
            text_url = kwargs.get('text_url')
            book_id = kwargs.get('book_id')
            existing = PdfHistory.find_existing_online_book(user_id_obj, text_url, book_id)
        else:
            # For uploaded PDFs, match by pdf_name
            existing = PdfHistory.find_existing_entry(user_id_obj, pdf_name, pdf_path)
        
        if existing:
            # Update existing entry with new metadata
            update_data = {
                'pdf_path': pdf_path,
                'total_pages': total_pages,
                'total_sentences': total_sentences,
                'file_size': file_size,
                'updated_at': datetime.utcnow()
            }
            
            # Update metadata fields if provided (but don't override tracking fields)
            for key, value in kwargs.items():
                if key not in ['last_page', 'status', 'created_at', 'current_sentence', 'completed_sentences', 'total_attempts', 'correct_attempts']:
                    update_data[key] = value
            
            history.update_one(
                {'_id': existing['_id']},
                {'$set': update_data}
            )
            return str(existing['_id'])
        
        else:
            # Create new entry
            entry = {
                'user_id': user_id_obj,
                'pdf_name': pdf_name,
                'pdf_path': pdf_path,
                'total_pages': total_pages,
                'total_sentences': total_sentences,
                'file_size': file_size,
                'last_page': 1,
                'status': 'in_progress',
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            # Add any additional metadata
            for key, value in kwargs.items():
                if key not in entry:  # Don't override core fields
                    entry[key] = value
            
            result = history.insert_one(entry)
            history_id = str(result.inserted_id)
            
            # Clean up any other duplicates for this user
            # This helps with cleaning up old duplicates from before this fix
            PdfHistory.cleanup_duplicates(user_id_obj)
            
            return history_id


    @staticmethod
    def get_user_history(user_id, limit=20):
        """Get history for a specific user with limit
        
        Automatically cleans up duplicates before returning
        """
        history = get_history_collection()
        user_id_obj = ObjectId(user_id) if isinstance(user_id, str) else user_id
        
        # Clean up duplicates first
        PdfHistory.cleanup_duplicates(user_id_obj)
        
        # Now fetch the cleaned history
        cursor = history.find({'user_id': user_id_obj}).sort('updated_at', -1).limit(limit)
        
        results = []
        for entry in cursor:
            entry['id'] = str(entry.pop('_id'))
            entry['user_id'] = str(entry['user_id'])
            if 'created_at' in entry and isinstance(entry['created_at'], datetime):
                entry['created_at'] = entry['created_at'].isoformat()
            if 'updated_at' in entry and isinstance(entry['updated_at'], datetime):
                entry['updated_at'] = entry['updated_at'].isoformat()
            results.append(entry)
            
        return results

    @staticmethod
    def delete_from_history(history_id, user_id):
        """Delete a history entry"""
        history = get_history_collection()
        
        query = {
            '_id': ObjectId(history_id) if isinstance(history_id, str) else history_id,
            'user_id': ObjectId(user_id) if isinstance(user_id, str) else user_id
        }
        
        result = history.delete_one(query)
        return result.deleted_count > 0

    @staticmethod
    def update_progress(history_id, user_id, last_page):
        """Update progress for a document"""
        history = get_history_collection()
        
        query = {
            '_id': ObjectId(history_id) if isinstance(history_id, str) else history_id,
            'user_id': ObjectId(user_id) if isinstance(user_id, str) else user_id
        }
        
        update = {
            '$set': {
                'last_page': last_page,
                'updated_at': datetime.utcnow()
            }
        }
        
        result = history.update_one(query, update)
        return result.modified_count > 0

    @staticmethod
    def update_progress_stats(history_id, user_id, current_sentence=1, completed_sentences=0, total_attempts=0, correct_attempts=0):
        """Update detailed reading progress statistics"""
        history = get_history_collection()
        
        query = {
            '_id': ObjectId(history_id) if isinstance(history_id, str) else history_id,
            'user_id': ObjectId(user_id) if isinstance(user_id, str) else user_id
        }
        
        update = {
            '$set': {
                'current_sentence': current_sentence,
                'completed_sentences': completed_sentences,
                'total_attempts': total_attempts,
                'correct_attempts': correct_attempts,
                'updated_at': datetime.utcnow()
            }
        }
        
        print(f"[DB] Updating progress stats for {history_id}. Query: {query}")
        result = history.update_one(query, update)
        print(f"[DB] Update result: matched={result.matched_count}, modified={result.modified_count}")
        return result.matched_count > 0
