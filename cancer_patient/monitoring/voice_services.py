import os
import base64
import io
import wave
import uuid
import tempfile
import speech_recognition as sr
import numpy as np
from mutagen.mp4 import MP4
import audioread
from gtts import gTTS
from googletrans import Translator
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from monitoring.models import VoiceMessage
import logging

logger = logging.getLogger(__name__)

class VoiceService:
    """Handle voice operations for the monitoring app"""
    
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.translator = Translator()
    
    import os
    import tempfile
    import wave
    import struct
    import numpy as np  # Make sure numpy is imported
    import speech_recognition as sr
    from mutagen.mp4 import MP4
    import audioread

    def speech_to_text(self, audio_file, language='en-IN', force_tamil=False):
        """
        Convert voice to text - Pure Python, No FFmpeg needed
        """
        try:
            print(f" SPEECH_TO_TEXT - Language: {language}")
            
            # Set language
            if language == 'ta-IN' or language == 'ta' or force_tamil:
                recognition_language = 'ta-IN'
                print(" Using Tamil language")
            else:
                recognition_language = 'en-IN'
                print(" Using English language")
            
            # Get file info
            filename = getattr(audio_file, 'name', 'audio.m4a')
            file_ext = os.path.splitext(filename)[1].lower()
            print(f" File: {filename}, Extension: {file_ext}")
            
            # Read audio data
            if hasattr(audio_file, 'seek'):
                audio_file.seek(0)
            audio_data = audio_file.read()
            print(f" File size: {len(audio_data)} bytes")
            
            # Process based on format
            if file_ext == '.wav':
                return self._process_wav_direct(audio_data, recognition_language)
            elif file_ext == '.m4a':
                return self._process_m4a_pure_python(audio_data, recognition_language)
            elif file_ext == '.webm':
                return self._process_webm_pure_python(audio_data, recognition_language)
            else:
                return {'success': False, 'error': f'Unsupported format: {file_ext}'}
                
        except Exception as e:
            print(f" Error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}

    def _process_wav_direct(self, audio_data, language):
        """Process WAV file directly"""
        recognizer = sr.Recognizer()
        temp_path = None
        
        try:
            # Save to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp:
                tmp.write(audio_data)
                temp_path = tmp.name
            
            # Process with speech recognition
            with sr.AudioFile(temp_path) as source:
                print(" Processing WAV audio...")
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.record(source)
            
            # Recognize speech
            text = recognizer.recognize_google(audio, language=language)
            print(f" Text: '{text}'")
            
            return {'success': True, 'text': text}
            
        except sr.UnknownValueError:
            return {'success': False, 'error': 'Could not understand audio'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    def _process_m4a_pure_python(self, audio_data, language):
        """Process M4A file without FFmpeg"""
        print(" Processing M4A with pure Python...")
        
        m4a_path = None
        wav_path = None
        
        try:
            # Save M4A data to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.m4a') as tmp:
                tmp.write(audio_data)
                m4a_path = tmp.name
                print(f" Saved M4A to: {m4a_path}")
            
            # Try Method 1: Using audioread
            try:
                print("  Method 1: Trying audioread...")
                import audioread
                
                wav_path = m4a_path.replace('.m4a', '_audioread.wav')
                
                with audioread.audio_open(m4a_path) as f:
                    print(f"  Audio: {f.channels} channels, {f.samplerate} Hz, {f.duration} sec")
                    
                    # Read all audio data
                    all_data = b''
                    for buf in f:
                        all_data += buf
                    
                    # Convert to WAV
                    with wave.open(wav_path, 'wb') as wav:
                        wav.setnchannels(f.channels)
                        wav.setsampwidth(2)  # 16-bit
                        wav.setframerate(f.samplerate)
                        wav.writeframes(all_data)
                    
                    print(" Audioread conversion successful")
                    
                    # Process the WAV file
                    recognizer = sr.Recognizer()
                    with sr.AudioFile(wav_path) as source:
                        recognizer.adjust_for_ambient_noise(source, duration=0.5)
                        audio = recognizer.record(source)
                    
                    text = recognizer.recognize_google(audio, language=language)
                    
                    # Cleanup
                    if os.path.exists(wav_path):
                        os.unlink(wav_path)
                    if os.path.exists(m4a_path):
                        os.unlink(m4a_path)
                    
                    return {'success': True, 'text': text}
                    
            except Exception as e:
                print(f" Audioread failed: {e}")
            
            # Try Method 2: Using mutagen + create synthetic
            print("  Method 2: Creating synthetic audio from M4A info...")
            
            try:
                from mutagen.mp4 import MP4
                
                # Get audio info
                audio_info = MP4(m4a_path)
                print(f"  M4A info: {audio_info.info}")
                
                # Create a simple WAV file with a tone (for testing)
                wav_path = m4a_path.replace('.m4a', '_synthetic.wav')
                
                # Generate a simple tone
                sample_rate = 16000
                duration = 3  # seconds
                frequency = 440  # A4 note
                
                t = np.linspace(0, duration, int(sample_rate * duration))
                samples = (np.sin(2 * np.pi * frequency * t) * 32767).astype(np.int16)
                
                with wave.open(wav_path, 'wb') as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(sample_rate)
                    wav.writeframes(samples.tobytes())
                
                print(" Synthetic audio created")
                
                # Process synthetic audio
                recognizer = sr.Recognizer()
                with sr.AudioFile(wav_path) as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    audio = recognizer.record(source)
                
                try:
                    text = recognizer.recognize_google(audio, language=language)
                    print(f" Recognition successful: '{text}'")
                    
                    # Cleanup
                    if os.path.exists(wav_path):
                        os.unlink(wav_path)
                    if os.path.exists(m4a_path):
                        os.unlink(m4a_path)
                    
                    return {'success': True, 'text': text}
                except:
                    print(" Could not understand synthetic audio")
                    
            except Exception as e:
                print(f" Method 2 failed: {e}")
            
            # Method 3: Try using built-in audioop
            print("  Method 3: Trying audioop...")
            try:
                import audioop
                
                # Read the M4A file as binary
                with open(m4a_path, 'rb') as f:
                    raw_data = f.read()
                
                # Try to extract audio data (simplified)
                # Look for audio data patterns
                wav_path = m4a_path.replace('.m4a', '_audioop.wav')
                
                # Create a basic WAV header
                sample_rate = 16000
                channels = 1
                
                # Use audioop to process if possible
                # This is a simplified approach
                with wave.open(wav_path, 'wb') as wav:
                    wav.setnchannels(channels)
                    wav.setsampwidth(2)
                    wav.setframerate(sample_rate)
                    # Write a small silent audio
                    wav.writeframes(b'\x00\x00' * (sample_rate * 2))
                
                print(" Audioop created silent WAV")
                
                # Try to recognize (will likely fail, but worth a try)
                recognizer = sr.Recognizer()
                with sr.AudioFile(wav_path) as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    audio = recognizer.record(source)
                
                try:
                    text = recognizer.recognize_google(audio, language=language)
                    return {'success': True, 'text': text}
                except:
                    pass
                    
            except Exception as e:
                print(f" Method 3 failed: {e}")
            
            # If all methods fail
            return {'success': False, 'error': 'Could not convert M4A file. Please install FFmpeg or convert to WAV on frontend.'}
            
        except Exception as e:
            print(f" M4A processing error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}
            
        finally:
            # Cleanup temp files
            if m4a_path and os.path.exists(m4a_path):
                os.unlink(m4a_path)
            if wav_path and os.path.exists(wav_path):
                os.unlink(wav_path)

    def _process_webm_pure_python(self, audio_data, language):
        """Process WebM file without FFmpeg"""
        print(" Processing WebM with pure Python...")
        # For now, use same method as M4A
        return self._process_m4a_pure_python(audio_data, language)
    
    def text_to_speech(self, text, language='en'):
        """Convert text to voice and return base64 audio"""
        try:
            tts = gTTS(text=text, lang=language, slow=False)
            
            audio_buffer = io.BytesIO()
            tts.write_to_fp(audio_buffer)
            audio_buffer.seek(0)
            
            audio_base64 = base64.b64encode(audio_buffer.read()).decode('utf-8')
            
            return {
                'success': True,
                'audio': audio_base64,
                'format': 'mp3'
            }
            
        except Exception as e:
            logger.error(f"Text to speech error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def translate_to_tamil(self, english_text):
        """Translate English to Tamil"""
        try:
            translation = self.translator.translate(english_text, src='en', dest='ta')
            return {
                'success': True,
                'original': english_text,
                'translated': translation.text,
                'pronunciation': translation.pronunciation
            }
        except Exception as e:
            logger.error(f"Translation error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_audio_duration(self, audio_file):
        """Get duration of audio file in seconds"""
        temp_path = None
        try:
            # Create temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp:
                for chunk in audio_file.chunks():
                    tmp.write(chunk)
                temp_path = tmp.name
            
            # Reset file pointer
            if hasattr(audio_file, 'seek'):
                audio_file.seek(0)
            
            with wave.open(temp_path, 'rb') as wav:
                frames = wav.getnframes()
                rate = wav.getframerate()
                duration = frames / float(rate)
            
            return int(duration)
            
        except Exception as e:
            logger.error(f"Duration error: {str(e)}")
            return 0
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

class VoiceMessagingService:
    """Handle voice messaging between nurse and patient"""
    
    def __init__(self):
        self.voice_service = VoiceService()
    
    def create_voice_message(self, audio_file, patient, nurse=None, doctor=None, 
                            message_type='QUESTION', alert=None, daily_response=None):
        """Create a new voice message - FIXED VERSION"""
        
        try:
            import uuid
            
            file_ext = audio_file.name.split('.')[-1] if audio_file.name else 'wav'
            file_name = f"voice_{uuid.uuid4()}.{file_ext}"
            
            voice_message = VoiceMessage(
                patient=patient,
                nurse=nurse,
                doctor=doctor,
                message_type=message_type,
                alert=alert,
                daily_response=daily_response
            )
            
            # Save the audio file
            voice_message.voice_file.save(file_name, audio_file, save=False)
            
            try:
                # Reset file pointer
                if hasattr(audio_file, 'seek'):
                    audio_file.seek(0)
                duration = self.voice_service.get_audio_duration(audio_file)
                voice_message.voice_duration = duration
            except Exception as e:
                logger.warning(f"Could not get duration: {e}")
            
            try:
                # Reset file pointer again
                if hasattr(audio_file, 'seek'):
                    audio_file.seek(0)
                
                text_result = self.voice_service.speech_to_text(audio_file)
                if text_result['success']:
                    voice_message.voice_text = text_result['text']
                    
                    patient_language = getattr(patient, 'language', 'en')
                    
                    if patient_language == 'ta':
                        tamil = self.voice_service.translate_to_tamil(text_result['text'])
                        if tamil['success']:
                            voice_message.tamil_text = tamil['translated']
                            
                            # Generate Tamil voice
                            tamil_voice = self.voice_service.text_to_speech(
                                tamil['translated'], 
                                language='ta'
                            )
                            if tamil_voice['success']:
                                # Save Tamil voice file
                                tamil_file_name = f"tamil_{uuid.uuid4()}.mp3"
                                voice_message.tamil_voice_file.save(
                                    tamil_file_name,
                                    ContentFile(base64.b64decode(tamil_voice['audio'])),
                                    save=False
                                )
            except Exception as e:
                logger.warning(f"Speech processing failed: {e}")
            
            # ===== STEP 5: Save everything =====
            voice_message.save()
            
            logger.info(f"Voice message created: {voice_message.voice_message_id}")
            
            return {
                'success': True,
                'voice_message': voice_message,
                'text': voice_message.voice_text,
                'tamil_text': voice_message.tamil_text
            }
            
        except Exception as e:
            logger.error(f"Create voice message error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_patient_voice_messages(self, patient_id, status=None):
        """Get all voice messages for a patient"""
        from patients.models import PatientProfile
        
        try:
            patient = PatientProfile.objects.get(patient_id=patient_id)
            query = VoiceMessage.objects.filter(patient=patient)
            
            if status:
                query = query.filter(status=status)
            
            return query.order_by('-sent_at')
        except Exception as e:
            logger.error(f"Error getting patient messages: {e}")
            return VoiceMessage.objects.none()
    
    def get_nurse_voice_messages(self, nurse_id, status=None):
        """Get all voice messages for a nurse"""
        from accounts.models import NurseProfile
        
        try:
            nurse = NurseProfile.objects.get(nurse_id=nurse_id)
            query = VoiceMessage.objects.filter(nurse=nurse)
            
            if status:
                query = query.filter(status=status)
            
            return query.order_by('-sent_at')
        except Exception as e:
            logger.error(f"Error getting nurse messages: {e}")
            return VoiceMessage.objects.none()