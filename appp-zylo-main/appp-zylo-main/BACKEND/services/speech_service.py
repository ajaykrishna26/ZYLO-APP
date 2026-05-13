# backend/services/speech_service.py
import pyttsx3
import speech_recognition as sr
from difflib import SequenceMatcher
import time
import re
import PyPDF2
import io
import uuid
import whisper
import numpy as np
import librosa
import textdistance
from config import Config
# ==========================================
# 0. TTS & SPEECH UTILS
# ==========================================

class SpeechService:
    # ==========================================
    # 1. INITIALIZATION & SETUP
    # ==========================================
    def __init__(self):
        self.engine = self._init_tts()
        self.recognizer = sr.Recognizer()
        self._configure_recognizer()
        self.microphone_available = self._check_microphone()
        self.current_sentence_index = 0
        self.sentences = []
        self.correct_count = 0
        self.total_practiced = 0
        self.is_reading = False
        self.current_pdf = None
        self.whisper_model = self._init_whisper()
        self.last_confidence_score = 0.0
    
    def _init_tts(self):
        """Initialize text-to-speech engine"""
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', Config.SPEECH_RATE)
            return engine
        except Exception as e:
            print(f"Warning: TTS initialization failed: {e}")
            return None
    
    def _check_microphone(self):
        """Check if microphone is available"""
        try:
            with sr.Microphone() as source:
                return True
        except:
            print("Warning: Microphone not available. Speech recognition will be disabled.")
            return False
    
    def _configure_recognizer(self):
        """Configure speech recognition settings"""
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 1.5
        self.recognizer.energy_threshold = 300

    def _init_whisper(self):
        """Initialize Whisper model for speech recognition"""
        try:
            print("[WHISPER] Loading Whisper model (base)...")
            # Use 'base' model for balance between speed and accuracy
            # Options: tiny, base, small, medium, large
            model = whisper.load_model("base")
            print("[WHISPER] Whisper model loaded successfully")
            return model
        except Exception as e:
            print(f"[WHISPER] Warning: Failed to load Whisper model: {e}")
            print("[WHISPER] Falling back to Google Speech Recognition")
            return None

    # ==========================================
    # 2. PDF TEXT EXTRACTION
    # ==========================================
    def extract_text_from_pdf(self, pdf_file) -> list:
        """Extract text from PDF and split into sentences line by line"""
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            all_sentences = []
            
            for page_num, page in enumerate(pdf_reader.pages):
                text = page.extract_text()
                
                # Split by lines first, then by sentences within each line
                lines = text.split('\n')
                
                for line_num, line in enumerate(lines):
                    line = line.strip()
                    if line:  # Only process non-empty lines
                        # Split each line into sentences
                        sentences_in_line = self._split_into_sentences(line)
                        
                        for sentence in sentences_in_line:
                            if sentence and len(sentence.strip()) > 5:  # Minimum length
                                all_sentences.append({
                                    'text': sentence.strip(),
                                    'page': page_num,
                                    'line': line_num,
                                    'original_line': line
                                })
            
            print(f"[PDF] Extracted {len(all_sentences)} sentences from PDF")
            return all_sentences
            
        except Exception as e:
            print(f"PDF extraction error: {e}")
            return []

    def _split_into_sentences(self, text: str) -> list:
        """Split text into sentences using multiple delimiters"""
        # Improved regex to handle common abbreviations and maintain sentence integrity
        # Split by . ! ? followed by whitespace, but avoid splitting on common abbreviations
        text = text.replace('\n', ' ').strip()
        sentence_endings = re.compile(r'(?<!\b(?:Mr|Mrs|Ms|Dr|Jr|Sr|vs|Prof|St|i\.e|e\.g)\.)(?<=[.!?])\s+')
        sentences = sentence_endings.split(text)
        
        # Filter out empty sentences and short fragments
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 3]
        
        return sentences

    # ==========================================
    # 3. SESSION MANAGEMENT
    # ==========================================
    def start_practice_from_pdf(self, pdf_file):
        """Start a new practice session from PDF"""
        self.sentences = self.extract_text_from_pdf(pdf_file)
        self.current_sentence_index = 0
        self.correct_count = 0
        self.total_practiced = 0
        
        print(f"[SESSION] Started practice session with {len(self.sentences)} sentences")
        return {
            'success': True,
            'total_sentences': len(self.sentences),
            'sentences': self.sentences
        }

    def get_current_sentence(self):
        """Get the current sentence for display"""
        if not self.sentences or self.current_sentence_index >= len(self.sentences):
            return {
                'available': False,
                'session_complete': True,
                'message': 'Practice session completed'
            }
            
        current_sentence = self.sentences[self.current_sentence_index]
        return {
            'available': True,
            'sentence': current_sentence['text'],
            'full_data': current_sentence,
            'current_index': self.current_sentence_index + 1,
            'total_sentences': len(self.sentences),
            'session_complete': False
        }

    # ==========================================
    # 4. TTS OPERATIONS (SPEAKING)
    # ==========================================
    def speak_sentence(self, sentence: str = None):
        """Speak a specific sentence"""
        if sentence is None:
            if not self.sentences or self.current_sentence_index >= len(self.sentences):
                return {'error': 'No sentence available'}
            sentence = self.sentences[self.current_sentence_index]['text']
        
        self.is_reading = True
        self.speak(sentence)
        self.is_reading = False
        
        return {'success': True, 'sentence': sentence}

    def stop_speaking(self):
        """Stop the current TTS reading"""
        if self.engine and self.is_reading:
            self.engine.stop()
            self.is_reading = False
            return {'success': True, 'message': 'Reading stopped'}
        return {'success': False, 'message': 'No active reading'}

    # ==========================================
    # 5. CORE PRACTICE LOGIC
    # ==========================================
    def practice_sentence(self, sentence: str):
        """Practice a specific sentence provided as argument"""
        try:
            print(f"[PRACTICE] Practicing specific sentence: {sentence}")
            
            # Speak the sentence to the user
            self.speak("Listen carefully:")
            time.sleep(0.3)
            self.speak(sentence)
            time.sleep(0.5)
            
            # Listen to user's attempt
            if self.microphone_available:
                try:
                    print("[MIC] Listening for student's reading...")
                    audio = self.listen_once()
                    spoken_text = self.transcribe(audio)
                    similarity = self.calculate_similarity(sentence, spoken_text)
                    is_correct = similarity >= Config.SIMILARITY_THRESHOLD
                    
                    # Generate feedback
                    feedback = self._generate_feedback(is_correct, similarity)
                    
                    result = {
                        'success': True,
                        'original_sentence': sentence,
                        'spoken_text': spoken_text,
                        'score': round(similarity * 100, 2),
                        'is_correct': is_correct,
                        'feedback': feedback,
                        'word_feedback': self._get_word_level_feedback(sentence, spoken_text),
                        'mode': 'practice_sentence'
                    }
                    
                    return result
                    
                except Exception as listen_error:
                    print(f"[ERROR] Listening failed: {listen_error}")
                    return self._simulate_practice(sentence, f"Listening failed: {listen_error}")
            else:
                return self._simulate_practice(sentence, "Microphone not available")
                
        except Exception as e:
            print(f"[ERROR] Practice session error: {e}")
            return {
                'success': False,
                'error': str(e),
                'spoken_text': None,
                'score': 0.0,
                'is_correct': False,
                'feedback': "Error occurred during practice",
                'mode': 'error'
            }

    def _has_word_errors(self, word_feedback):
        """Check if there are any word-level errors in the feedback"""
        if not word_feedback:
            return False
        
        # Check if any word has an error status
        error_statuses = {'mispronounced', 'missed', 'article-error'}
        for feedback_item in word_feedback:
            if feedback_item.get('status') in error_statuses:
                return True
        
        return False

    def practice_current_sentence(self):
        """Practice the current sentence with strict word-level accuracy requirement"""
        if not self.sentences or self.current_sentence_index >= len(self.sentences):
            return {
                'success': False,
                'error': 'No sentences available',
                'session_complete': True
            }

        current_sentence_data = self.sentences[self.current_sentence_index]
        current_sentence = current_sentence_data['text']
        
        try:
            # Re-use the new generic method but add session management
            result = self.practice_sentence(current_sentence)
            
            if result.get('success'):
                self.total_practiced += 1
                
                # Check for word-level errors - if any word is mispronounced, don't advance
                word_feedback = result.get('word_feedback', [])
                has_errors = self._has_word_errors(word_feedback)
                
                if not has_errors:
                    # All words are correct - advance to next sentence
                    self.correct_count += 1
                    self.current_sentence_index += 1
                    result['message'] = "[OK] Perfect! All words pronounced correctly. Moving to next sentence."
                    result['next_sentence_available'] = self.current_sentence_index < len(self.sentences)
                else:
                    # At least one word is mispronounced - stay on same sentence
                    result['message'] = "Try again, you're so close! Focus on the words that sound different."
                    result['next_sentence_available'] = self.current_sentence_index < len(self.sentences)
                    result['should_retry'] = True
                
                # Add session stats
                accuracy = (self.correct_count / self.total_practiced) * 100 if self.total_practiced > 0 else 0
                result['accuracy'] = round(accuracy, 1)
                result['correct_count'] = self.correct_count
                result['total_practiced'] = self.total_practiced
                result['session_complete'] = False
                
                return result
            else:
                return result

        except Exception as e:
            # Fallback for outer exception
            print(f"[ERROR] Session practice error: {e}")
            return {
                'success': False,
                'error': str(e),
                'spoken_text': None,
                'score': 0.0,
                'is_correct': False,
                'feedback': "Error occurred during practice",
                'session_complete': False
            }

    def _generate_feedback(self, is_correct: bool, similarity: float) -> str:
        """Generate gentle feedback based on performance"""
        if is_correct:
            if similarity >= 0.95:
                return "Outstanding! That was perfect pronunciation."
            elif similarity >= 0.85:
                return "Great job! Your pronunciation is very clear."
            else:
                return "Well done! You got the sentence right."
        else:
            if similarity >= 0.7:
                return "You're very close! A few words sounded a bit different. Let's try one more time."
            elif similarity >= 0.5:
                return "Good effort! Some words were tricky. Listen to the example again and take your time."
            else:
                return "It's okay! This is a tough one. Listen to the smooth reading again, then try to match that rhythm."

    def generate_word_feedback_message(self, word_feedback: list) -> str:
        """Generate a readable feedback message highlighting mispronounced words.
        
        Example: "You said 'wurld' but the word is 'world'. Try again!"
        """
        if not word_feedback:
            return ""
        
        mispronounced = []
        missed = []
        extra_words = []
        
        for item in word_feedback:
            status = item.get('status')
            word = item.get('word', '')
            correct_word = item.get('correct_word', '')
            spoken = item.get('spoken', '')
            
            if status == 'mispronounced' and spoken:
                # Show what they said vs what it should be
                mispronounced.append(f"'{spoken}' → '{correct_word}'")
            elif status == 'missed':
                missed.append(f"'{correct_word}'")
            elif status == 'extra':
                # Additional word spoken that's not in the original
                extra_words.append(f"'{word}'")
        
        feedback_parts = []
        
        if mispronounced:
            feedback_parts.append(f"Try these words again: {', '.join(mispronounced)}")
        
        if missed:
            feedback_parts.append(f"You skipped: {', '.join(missed)}")
        
        if extra_words:
            feedback_parts.append(f"Additional words: {', '.join(extra_words)}")
        
        return " | ".join(feedback_parts) if feedback_parts else ""

    # ==========================================
    # 6. HELPERS & SIMULATION
    # ==========================================
    def _simulate_practice(self, sentence: str, reason: str):
        """Simulate practice session without microphone"""
        print(f"[SIM] Simulation mode: {reason}")
        
        self.total_practiced += 1
        self.correct_count += 1
        accuracy = (self.correct_count / self.total_practiced) * 100
        
        result = {
            'success': True,
            'original_sentence': sentence,
            'spoken_text': f"[SIMULATION] {sentence}",
            'score': 85.0,
            'is_correct': True,
            'accuracy': round(accuracy, 1),
            'correct_count': self.correct_count,
            'total_practiced': self.total_practiced,
            'feedback': "Simulation mode - Good job!",
            'message': "[OK] Correct! Moving to next sentence.",
            'next_sentence_available': self.current_sentence_index + 1 < len(self.sentences),
            'session_complete': False
        }
        
        self.current_sentence_index += 1
        return result

    def skip_to_next_sentence(self):
        """Skip to the next sentence"""
        if self.current_sentence_index + 1 < len(self.sentences):
            self.current_sentence_index += 1
            return {
                'success': True,
                'message': 'Moved to next sentence',
                'current_sentence': self.sentences[self.current_sentence_index]['text']
            }
        else:
            return {
                'success': False,
                'message': 'No more sentences available'
            }

    def get_session_progress(self):
        """Get current session progress"""
        accuracy = (self.correct_count / self.total_practiced) * 100 if self.total_practiced > 0 else 0
        
        return {
            'current_sentence_index': self.current_sentence_index + 1,
            'total_sentences': len(self.sentences),
            'accuracy': round(accuracy, 1),
            'correct_count': self.correct_count,
            'total_practiced': self.total_practiced,
            'session_complete': self.current_sentence_index >= len(self.sentences)
        }
    
    # ==========================================
    # 7. LOW-LEVEL AUDIO IO
    # ==========================================
    def _remove_reading_symbols(self, text):
        """Remove symbols that shouldn't be read aloud
        
        Removes: /, ,, ., ?, !, ;, :, -, (, ), [, ], {, }, ", ', |, ~, `, @, #, $, %, ^, &, * etc.
        But keeps the text structure for natural reading flow
        """
        # Replace common punctuation with space to preserve word boundaries
        symbols_to_remove = r'[/,.\?!;:\-\(\)\[\]\{\}"\'\|~`@#$%^&*+=<>\\]'
        cleaned = re.sub(symbols_to_remove, ' ', text)
        
        # Remove extra spaces created by symbol removal
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned
    
    def speak(self, text):
        """Speak text using TTS"""
        if self.engine is None:
            print(f"TTS Simulation: {text}")
            return
        
        try:
            # Remove symbols before speaking
            clean_text = self._remove_reading_symbols(text)
            
            # Only speak if there's meaningful content after cleaning
            if clean_text:
                self.engine.say(clean_text)
                self.engine.runAndWait()
            time.sleep(0.3)
        except Exception as e:
            print(f"TTS Error: {e}")

    def generate_tts_audio(self, text):
        """Generate TTS audio and return as bytes"""
        if not text:
            return None
            
        import tempfile
        import os
        
        try:
            temp_dir = tempfile.gettempdir()
            filename = os.path.join(temp_dir, f"tts_{uuid.uuid4()}.wav")
            
            # Use a separate engine instance if possible to avoid state issues in multi-threaded env
            # But pyttsx3 is often finicky with multiple instances.
            self.engine.save_to_file(text, filename)
            self.engine.runAndWait()
            
            with open(filename, 'rb') as f:
                audio_data = f.read()
                
            # Cleanup
            try: os.remove(filename)
            except: pass
            
            return audio_data
        except Exception as e:
            print(f"[ERROR] TTS Generation failed: {e}")
            return None
    
    def listen_once(self, calibrate_seconds=1.0):
        """Listen to microphone and return audio"""
        if not self.microphone_available:
            raise RuntimeError("Microphone not available")
            
        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=calibrate_seconds)
                audio = self.recognizer.listen(source, timeout=10, phrase_time_limit=10)
                return audio
        except sr.WaitTimeoutError:
            raise RuntimeError("No speech detected within timeout period")
        except Exception as e:
            raise RuntimeError(f"Microphone error: {e}")
    
    def transcribe(self, audio):
        """Convert speech to text using Whisper model with confidence scores"""
        try:
            # Convert AudioData to WAV format for Whisper
            print("[TRANSCRIBE] Converting audio to WAV format...")
            wav_data = audio.get_wav_data()
            
            # Save to temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_file.write(wav_data)
                tmp_file_path = tmp_file.name
            
            # Use Whisper for transcription
            if self.whisper_model:
                print("[TRANSCRIBE] Using Whisper for speech recognition...")
                try:
                    result = self.whisper_model.transcribe(tmp_file_path, language="en")
                    text = result["text"].strip()
                    
                    # Extract confidence metrics
                    # Whisper doesn't provide per-word confidence by default, but we can use probability
                    segments = result.get("segments", [])
                    if segments:
                        # Average probability from all segments
                        probs = []
                        for segment in segments:
                            if "no_speech_prob" in segment:
                                # Inverse of no_speech_prob gives us confidence
                                probs.append(1 - segment["no_speech_prob"])
                        
                        self.last_confidence_score = sum(probs) / len(probs) if probs else 0.8
                    else:
                        self.last_confidence_score = 0.8
                    
                    print(f"[TRANSCRIBE] Whisper success: '{text}' (confidence: {self.last_confidence_score:.2f})")
                    
                    # Cleanup
                    import os
                    os.unlink(tmp_file_path)
                    
                    return text.lower()
                except Exception as whisper_error:
                    print(f"[TRANSCRIBE] Whisper error: {whisper_error}")
                    print("[TRANSCRIBE] Falling back to Google Speech Recognition...")
                    # Cleanup
                    import os
                    os.unlink(tmp_file_path)
                    # Fallback to Google Speech Recognition
                    return self._transcribe_with_google(audio)
            else:
                print("[TRANSCRIBE] Whisper not available, using Google Speech Recognition...")
                # Cleanup
                import os
                os.unlink(tmp_file_path)
                return self._transcribe_with_google(audio)
                
        except Exception as e:
            print(f"[TRANSCRIBE] Unexpected error: {type(e).__name__}: {e}")
            return ""
    
    def _transcribe_with_google(self, audio):
        """Fallback: Convert speech to text using Google Speech Recognition"""
        try:
            print("[TRANSCRIBE] Attempting Google Speech Recognition...")
            text = self.recognizer.recognize_google(audio)
            self.last_confidence_score = 0.85  # Google doesn't provide confidence
            print(f"[TRANSCRIBE] Google success: '{text}'")
            return text.lower()
        except sr.UnknownValueError as e:
            print(f"[TRANSCRIBE] Could not understand audio: {e}")
            return ""
        except sr.RequestError as e:
            print(f"[TRANSCRIBE] API request error: {e}")
            if "Failed to connect" in str(e) or "connection" in str(e).lower():
                print("[TRANSCRIBE] Network error detected")
            return ""
        except Exception as e:
            print(f"[TRANSCRIBE] Unexpected Google error: {type(e).__name__}: {e}")
            return ""
    
    def calculate_similarity(self, original, spoken):
        """Calculate similarity between original and spoken text with improved accuracy.
        
        Uses multiple metrics:
        1. Word-level matching with dynamic thresholds
        2. Phonetic similarity (Jaro-Winkler)
        3. Character-level matching (SequenceMatcher)
        4. Confidence scoring from Whisper
        
        Returns a score from 0 to 1 where 1 is perfect match.
        """
        if not original or not spoken:
            return 0.0
            
        original_clean = self._clean_text(original)
        spoken_clean = self._clean_text(spoken)
        
        # If either is empty after cleaning, return 0
        if not original_clean or not spoken_clean:
            return 0.0
        
        # Get word lists
        orig_words = original_clean.split()
        spoken_words = spoken_clean.split()
        
        # Calculate word-level similarity (most important for pronunciation)
        word_level_similarity = self._calculate_word_level_similarity(orig_words, spoken_words)
        
        # Character-level similarity
        char_similarity = SequenceMatcher(None, original_clean, spoken_clean).ratio()
        
        # Jaro-Winkler for phonetic similarity
        phonetic_similarity = textdistance.jaro_winkler.similarity(original_clean, spoken_clean)
        
        # Weighted average (word-level is most important for pronunciation)
        # Weight: 50% word-level, 30% phonetic, 20% character
        similarity = (word_level_similarity * 0.5 + 
                     phonetic_similarity * 0.3 + 
                     char_similarity * 0.2)
        
        # Apply confidence adjustment - higher confidence = more strict matching required
        # Lower confidence = more lenient (allow more variation)
        confidence = self.last_confidence_score
        if confidence < 0.7:
            # Low confidence transcription - be more lenient
            similarity = min(1.0, similarity * 1.15)
        elif confidence > 0.9:
            # High confidence transcription - be more strict
            similarity = similarity * 0.95
        
        return min(1.0, similarity)
    
    def _calculate_word_level_similarity(self, orig_words, spoken_words):
        """Calculate similarity at the word level using intelligent alignment.
        
        Handles cases where words are:
        - Correctly pronounced
        - Slightly mispronounced (Jaro-Winkler > 0.7)
        - Significantly mispronounced
        - Missing or extra
        """
        if not orig_words:
            return 0.0
        
        if not spoken_words:
            return 0.0
        
        # Use SequenceMatcher to align words
        matcher = SequenceMatcher(None, orig_words, spoken_words)
        
        total_similarity = 0.0
        matched_count = 0
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                # Perfect word matches
                matched_count += (i2 - i1)
                total_similarity += (i2 - i1)
            elif tag == 'replace':
                # Mismatched words - calculate similarity for each pair
                num_comparisons = min(i2 - i1, j2 - j1)
                for idx in range(num_comparisons):
                    orig_word = orig_words[i1 + idx]
                    spoken_word = spoken_words[j1 + idx]
                    
                    # Use multiple metrics for word similarity
                    jaro_sim = textdistance.jaro_winkler.similarity(orig_word, spoken_word)
                    leven_sim = textdistance.levenshtein.normalized_similarity(orig_word, spoken_word)
                    seq_sim = SequenceMatcher(None, orig_word, spoken_word).ratio()
                    
                    # Average of multiple metrics (jaro-winkler is best for typos/pronunciation)
                    word_similarity = jaro_sim * 0.5 + leven_sim * 0.3 + seq_sim * 0.2
                    
                    total_similarity += word_similarity
                    matched_count += 1
                
                # Extra or missing words reduce score less harshly
                extra_words = abs((i2 - i1) - (j2 - j1))
                if extra_words > 0:
                    # Penalize extra/missing words but not as much
                    total_similarity -= extra_words * 0.15
            elif tag == 'delete':
                # Words in original not in spoken (missed words)
                # Penalty: 0.3 per word (allows some tolerance)
                total_similarity -= (i2 - i1) * 0.3
                matched_count += (i2 - i1)
            elif tag == 'insert':
                # Extra words in spoken not in original
                # Penalty: 0.2 per word (less harsh than missing)
                total_similarity -= (j2 - j1) * 0.2
        
        # Normalize by number of words in original sentence
        if matched_count == 0:
            matched_count = len(orig_words)
        
        word_similarity = total_similarity / matched_count
        return max(0.0, min(1.0, word_similarity))  # Clamp between 0 and 1

    def _clean_text(self, text):
        """Remove punctuation, numbers, and symbols. Keep only letters and spaces.
        
        This ensures we only compare actual words, excluding:
        - Numbers (0-9)
        - Symbols: , _ # @ $ % ^ & * ( ) [ ] { } / \ | ~ ` ! ? . , ; : ' " - + = < >
        - Special characters
        """
        # First convert to lowercase
        text = text.lower()
        # Replace non-letter/non-space characters with space to preserve word boundaries
        cleaned = re.sub(r'[^a-z\s]', ' ', text)
        # Remove extra spaces
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    def _get_word_level_feedback(self, original, spoken):
        """Generate word-by-word feedback with enhanced phonetic matching.
        
        Detects:
        - Correctly pronounced words ('correct')
        - Mispronounced words ('mispronounced') - includes what was said
        - Missed words ('missed') - not said at all
        - Article errors ('article-error') - a vs an, the confusion
        - Extra/additional words ('extra') - words spoken that aren't in original
        
        Uses Whisper confidence scores and Jaro-Winkler distance for better accuracy.
        """
        if not original:
            return []
            
        from difflib import SequenceMatcher
        
        orig_words = original.split()
        spoken_words = spoken.lower().split() if spoken else []
        
        # Clean words: remove numbers and symbols
        clean_orig = [self._clean_text(w) for w in orig_words]
        clean_spoken = [self._clean_text(w) for w in spoken_words]
        
        matcher = SequenceMatcher(None, clean_orig, clean_spoken)
        feedback = []
        
        # Articles that need careful checking
        articles = {'a', 'an', 'the'}
        
        # Apply Whisper confidence threshold for stricter mispronunciation detection
        confidence_threshold = max(0.5, self.last_confidence_score)
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                # Perfectly matched words
                for i in range(i1, i2):
                    feedback.append({
                        'word': orig_words[i],
                        'correct_word': orig_words[i],
                        'status': 'correct',
                        'confidence': 1.0
                    })
            elif tag == 'replace':
                # Words that don't match - use advanced similarity metrics
                for i in range(i1, i2):
                    spoken_idx = j1 + (i - i1)
                    if spoken_idx < j2:
                        orig_lower = clean_orig[i]
                        spoken_lower = clean_spoken[spoken_idx]
                        
                        if orig_lower in articles and spoken_lower in articles:
                            # Article/grammar error - needs correction
                            feedback.append({
                                'word': orig_words[i],
                                'correct_word': orig_words[i],
                                'status': 'article-error',
                                'spoken': spoken_words[spoken_idx],
                                'type': 'article',
                                'confidence': self.last_confidence_score
                            })
                        else:
                            # Regular mispronunciation - use multiple similarity metrics
                            spoken_word = spoken_words[spoken_idx] if spoken_idx < len(spoken_words) else ''
                            
                            # Calculate multiple similarity metrics
                            sequence_similarity = SequenceMatcher(None, orig_lower, spoken_lower).ratio()
                            jaro_similarity = textdistance.jaro_winkler.similarity(orig_lower, spoken_lower)
                            levenshtein_distance = textdistance.levenshtein.normalized_similarity(orig_lower, spoken_lower)
                            
                            # Average of all metrics for more robust detection
                            avg_similarity = (sequence_similarity + jaro_similarity + levenshtein_distance) / 3
                            
                            feedback.append({
                                'word': orig_words[i],
                                'correct_word': orig_words[i],
                                'status': 'mispronounced',
                                'spoken': spoken_word,
                                'similarity': avg_similarity,
                                'sequence_similarity': sequence_similarity,
                                'phonetic_similarity': jaro_similarity,
                                'confidence': self.last_confidence_score
                            })
                    else:
                        # No spoken token at all -> truly missed the word
                        feedback.append({
                            'word': orig_words[i],
                            'correct_word': orig_words[i],
                            'status': 'missed',
                            'confidence': self.last_confidence_score
                        })
            elif tag == 'delete':
                # Words in original that weren't spoken
                for i in range(i1, i2):
                    feedback.append({
                        'word': orig_words[i],
                        'correct_word': orig_words[i],
                        'status': 'missed',
                        'confidence': self.last_confidence_score
                    })
            elif tag == 'insert':
                # Extra spoken words that weren't in the original
                for j in range(j1, j2):
                    feedback.append({
                        'word': spoken_words[j],
                        'status': 'extra',
                        'note': 'Additional word not in the sentence',
                        'confidence': self.last_confidence_score
                    })
            
        return feedback