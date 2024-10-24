import numpy as np
from pydub import AudioSegment
import tempfile
import subprocess

class AudioProcessor:
    def __init__(self):
        self.sample_rate = 44100
    
    def extract_audio(self, video_path):
        """Extract audio from video file and return normalized samples"""
        # Extract audio using ffmpeg
        temp_audio = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        subprocess.run([
            'ffmpeg', '-i', video_path,
            '-vn',  # No video
            '-acodec', 'pcm_s16le',  # PCM format
            '-ar', str(self.sample_rate),  # Sample rate
            '-ac', '1',  # Mono
            '-loglevel', 'quiet',  # No logging
            '-y',  # Overwrite output
            temp_audio.name
        ], check=True)
        
        # Load audio file
        audio = AudioSegment.from_wav(temp_audio.name)
        
        # Convert to numpy array and normalize
        samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
        samples = samples / np.max(np.abs(samples))
        
        # Generate time array
        duration = len(samples) / self.sample_rate
        time = np.linspace(0, duration, len(samples))
        
        # Downsample for display if necessary
        if len(samples) > 10000:
            target_size = 10000
            samples = self._downsample(samples, target_size)
            time = np.linspace(0, duration, target_size)
        
        return {
            'samples': samples,
            'time': time,
            'duration': duration,
            'sample_rate': self.sample_rate
        }
    
    def _downsample(self, samples, target_size):
        """Downsample array to target size using max values to preserve peaks"""
        samples = abs(samples)  # Use absolute values to preserve peaks
        chunk_size = len(samples) // target_size
        return np.array([
            np.max(samples[i:i + chunk_size])
            for i in range(0, len(samples), chunk_size)
        ])[:target_size]