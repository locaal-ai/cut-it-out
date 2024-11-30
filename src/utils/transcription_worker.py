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
    transcription_result = Signal(List[dict])
    transcription_progress = Signal(int)

    def __init__(self, video_path, start=None, end=None):
        super().__init__()
        self.start_time = start
        self.end_time = end
        self.video_path = video_path
        self.sample_rate = 16000
        self.chunk_ids = []
        self.total_chunks = 0
        self.chunk_timestamps = {}  # Map chunk_ids to start times

    def handle_result(
        self, chunk_id: int, segments: List[WhisperSegment], is_partial: bool
    ):
        # Get chunk start time
        chunk_start_time = self.chunk_timestamps.get(chunk_id, 0)

        tokens = []

        # Process each segment
        for segment in segments:
            # Process each token in the segment
            for token in segment.tokens:
                # Calculate absolute time for token
                token_start = chunk_start_time + token.t0
                token_end = chunk_start_time + token.t1

                # Append token to list
                tokens.append(
                    {
                        "text": token.text,
                        "start": token_start,
                        "end": token_end,
                    }
                )

        self.chunk_ids.remove(chunk_id)
        self.transcription_result.emit(tokens)
        self.transcription_progress.emit(
            (self.total_chunks - len(self.chunk_ids)) * 100 // self.total_chunks
        )

    def run(self):
        print(
            f"Transcribing {self.video_path} from {self.start_time} to {self.end_time}"
        )
        audio_sample = self.extract_audio(
            self.video_path, self.start_time, self.end_time
        )
        chunk_size = self.sample_rate * 30  # 30 seconds of audio @ 16 kHz
        print("Load whisper model")
        whisper_model = AsyncWhisperModel(
            R"data\ggml-small.en-q5_1.bin",
            callback=self.handle_result,
            use_gpu=True,
        )
        print("Starting whisper model")
        whisper_model.start()

        print("Transcribing audio")
        self.total_chunks = len(audio_sample) // chunk_size + 1

        for start in range(0, len(audio_sample), chunk_size):
            chunk = audio_sample[start : start + chunk_size]
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)), "constant")
            # convert from int16 to float32 [-1, 1]
            chunk = chunk.astype(np.float32) / 32768.0

            # Calculate timestamp in seconds
            start_time = start / self.sample_rate

            print(f"Transcribing chunk starting at {start_time:.2f}s")
            chunk_id = whisper_model.transcribe(chunk)
            # Store start time for this chunk
            self.chunk_timestamps[chunk_id] = start_time

            print(f"Queuing chunk {chunk_id} starting at {start_time:.2f}s")
            print(
                f"Chunk size: {len(chunk)}, {len(chunk) / self.sample_rate} seconds, {chunk.dtype}"
            )
            self.chunk_ids.append(chunk_id)

        # wait for all chunks to be processed
        while self.chunk_ids:
            time.sleep(0.1)

        print("Stopping whisper model")
        whisper_model.stop()
        self.transcription_done.emit("Transcription done")

    def extract_audio(self, video_path, start=None, end=None):
        """
        Extract audio from video file and return samples.

        Args:
            video_path (str): Path to video file
            start (float, optional): Start time in seconds
            end (float, optional): End time in seconds
        """
        # Extract audio using ffmpeg
        temp_audio = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)

        # Base command
        cmd = [
            "ffmpeg",
            "-i",
            video_path,
        ]

        # Add seek argument if start time provided
        if start is not None:
            cmd.extend(["-ss", str(start)])

        # Add duration argument if both start and end provided
        if start is not None and end is not None:
            duration = end - start
            cmd.extend(["-t", str(duration)])

        # Add output options
        cmd.extend(
            [
                "-vn",  # No video
                "-acodec",
                "pcm_s16le",  # PCM format
                "-ar",
                str(self.sample_rate),  # Sample rate
                "-ac",
                "1",  # Mono
                "-y",  # Overwrite output file
                temp_audio.name,
            ]
        )

        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Load audio file
        audio: AudioSegment = AudioSegment.from_wav(temp_audio.name)

        # Convert to numpy array and normalize
        return np.array(audio.get_array_of_samples(), dtype=np.float32)
