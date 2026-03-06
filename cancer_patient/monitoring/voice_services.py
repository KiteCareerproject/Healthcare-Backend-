import os
import base64
import io
import wave
import uuid
import tempfile
import speech_recognition as sr
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
    
    def speech_to_text(self, audio_file, language='en-IN'):
        """
        Convert voice to text
        Supports: 'en-IN' (English), 'ta-IN' (Tamil)
        """
        temp_path = None
        try:
            # Create temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp:
                for chunk in audio_file.chunks():
                    tmp.write(chunk)
                temp_path = tmp.name
            
            # Reset file pointer for future use
            if hasattr(audio_file, 'seek'):
                audio_file.seek(0)
            
            # Convert speech to text
            with sr.AudioFile(temp_path) as source:
                audio = self.recognizer.record(source)
                
            try:
                text = self.recognizer.recognize_google(audio, language=language)
                return {'success': True, 'text': text}
            except sr.UnknownValueError:
                return {'success': False, 'error': 'Could not understand audio'}
            except sr.RequestError as e:
                return {'success': False, 'error': f'Speech service error: {e}'}
            
        except Exception as e:
            logger.error(f"Speech to text error: {str(e)}")
            return {'success': False, 'error': str(e)}
        finally:
            # Cleanup temp file
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
    
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
            # ===== STEP 1: Save file first (always works) =====
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
            
            # ===== STEP 2: Try to get duration (optional) =====
            try:
                # Reset file pointer
                if hasattr(audio_file, 'seek'):
                    audio_file.seek(0)
                duration = self.voice_service.get_audio_duration(audio_file)
                voice_message.voice_duration = duration
            except Exception as e:
                logger.warning(f"Could not get duration: {e}")
            
            # ===== STEP 3: Try speech to text (optional) =====
            try:
                # Reset file pointer again
                if hasattr(audio_file, 'seek'):
                    audio_file.seek(0)
                
                text_result = self.voice_service.speech_to_text(audio_file)
                if text_result['success']:
                    voice_message.voice_text = text_result['text']
                    
                    # ===== STEP 4: Try Tamil translation (optional) =====
                    # FIX: Check patient language correctly
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