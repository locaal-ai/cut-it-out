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
        temp_audio = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                video_path,
                "-vn",  # No video
                "-acodec",
                "pcm_s16le",  # PCM format
                "-ar",
                str(self.sample_rate),  # Sample rate
                "-ac",
                "1",  # Mono
                "-y",  # Overwrite output file
                temp_audio.name,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Load audio file
        audio: AudioSegment = AudioSegment.from_wav(temp_audio.name)

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
            "samples": samples,
            "time": time,
            "duration": duration,
            "sample_rate": self.sample_rate,
        }

    def _downsample(self, samples, target_size):
        """Downsample array to target size preserving peaks and troughs"""
        # Calculate chunk size
        chunk_size = len(samples) // target_size

        result = np.zeros(target_size)
        for i in range(target_size):
            chunk = samples[i * chunk_size : (i + 1) * chunk_size]
            if len(chunk) > 0:
                # Find both max and min in the chunk
                max_val = np.max(chunk)
                min_val = np.min(chunk)

                # Use the value with larger absolute magnitude
                result[i] = max_val if abs(max_val) > abs(min_val) else min_val

        return result
