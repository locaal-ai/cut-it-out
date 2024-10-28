import time
from typing import List
import numpy as np
from simpler_whisper.whisper import AsyncWhisperModel, WhisperSegment
from PySide6.QtCore import QThread, Signal
from pydub import AudioSegment
import subprocess
import tempfile


class TranscriptionWorker(QThread):
    transcription_done = Signal(str)
    transcription_result = Signal(str)
    transcription_progress = Signal(int)

    def __init__(self, video_path):
        super().__init__()
        self.video_path = video_path
        self.sample_rate = 16000
        self.chunk_ids = []
        self.total_chunks = 0

    def handle_result(
        self, chunk_id: int, segments: List[WhisperSegment], is_partial: bool
    ):
        text = " ".join([seg.text for seg in segments])
        print(
            f"Chunk {chunk_id} results ({'partial' if is_partial else 'final'}): {text}"
        )
        self.chunk_ids.remove(chunk_id)
        # self.transcription_result.emit(" ".join([s.text for s in transcription]))
        self.transcription_progress.emit(
            (self.total_chunks - len(self.chunk_ids)) * 100 // self.total_chunks
        )

    def run(self):
        audio_sample = self.extract_audio(self.video_path)
        chunk_size = self.sample_rate * 30  # 30 seconds of audio @ 16 kHz
        whisper_model = AsyncWhisperModel(
            R"data\ggml-small.en-q5_1.bin",
            callback=self.handle_result,
            use_gpu=False,
        )
        whisper_model.start()

        self.total_chunks = len(audio_sample) // chunk_size + 1

        for start in range(0, len(audio_sample), chunk_size):
            chunk = audio_sample[start : start + chunk_size]
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)), "constant")
            chunk_id = whisper_model.transcribe(chunk)
            print(f"Queuing chunk {chunk_id}")
            print(
                f"Chunk size: {len(chunk)}, {len(chunk) / self.sample_rate} seconds, {chunk.dtype}"
            )
            self.chunk_ids.append(chunk_id)

        # wait for all chunks to be processed
        while self.chunk_ids:
            time.sleep(0.1)

    def extract_audio(self, video_path):
        """Extract audio from video file and return samples"""
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
        )

        # Load audio file
        audio: AudioSegment = AudioSegment.from_wav(temp_audio.name)

        # Convert to numpy array and normalize
        return np.array(audio.get_array_of_samples(), dtype=np.float32)
