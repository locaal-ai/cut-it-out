from PySide6.QtCore import QObject, Signal, QThread
import time

from utils.audio_processor import AudioProcessor
from utils.video_processor import VideoProcessor


class VideoLoadWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(
        self,
        video_processor: VideoProcessor,
        audio_processor: AudioProcessor,
        file_path,
    ):
        super().__init__()
        self.video_processor = video_processor
        self.audio_processor = audio_processor
        self.file_path = file_path

    def run(self):
        try:
            # Check video metadata
            self.progress.emit(10, "Checking video file...")
            duration = self.video_processor.get_duration(self.file_path)

            # Extract audio data
            self.progress.emit(30, "Extracting audio...")
            audio_data = self.audio_processor.extract_audio(self.file_path)

            # Process video (check frames, generate thumbnails, etc.)
            self.progress.emit(60, "Processing video...")
            fps = self.video_processor.get_fps(self.file_path)

            # Final verification
            self.progress.emit(90, "Finalizing...")

            result = {
                "duration": duration,
                "audio_data": audio_data,
                "fps": fps,
                "path": self.file_path,
            }

            self.progress.emit(100, "Complete!")
            self.finished.emit(result)

        except Exception as e:
            self.error.emit(str(e))
