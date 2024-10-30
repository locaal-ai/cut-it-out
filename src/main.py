from pathlib import Path
import sys
from typing import List
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt, QThread
from PySide6.QtMultimedia import QMediaPlayer
from components.unified_timeline import UnifiedTimeline
from components.video_player import VideoPlayer
from utils.audio_processor import AudioProcessor
from utils.transcription_worker import TranscriptionWorker
from utils.video_processor import VideoProcessor
from components.progress_dialog import ProgressDialog
from utils.async_worker import VideoLoadWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cut-It-Out Video Editor")
        self.setGeometry(100, 100, 800, 600)
        self.setMinimumWidth(500)

        self.video_processor = VideoProcessor()
        self.audio_processor = AudioProcessor()

        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Video player
        self.video_player = VideoPlayer()
        layout.addWidget(self.video_player)

        self.timeline = UnifiedTimeline()
        layout.addWidget(self.timeline)

        # Controls
        controls_layout = QHBoxLayout()

        self.load_button = QPushButton("Load Video")
        self.load_button.clicked.connect(self.load_video)

        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self.export_video)
        self.export_button.setEnabled(False)

        self.transcribe_button = QPushButton("Transcribe")
        self.transcribe_button.clicked.connect(self.transcribe_video)
        self.transcribe_button.setEnabled(False)

        controls_layout.addWidget(self.load_button)
        controls_layout.addWidget(self.export_button)
        controls_layout.addWidget(self.transcribe_button)
        controls_layout.addStretch()

        layout.addLayout(controls_layout)

    def load_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Video File",
            "",
            "Video Files (*.mp4 *.avi *.mkv *.mov);;All Files (*.*)",
        )

        if file_path:
            # Create and show progress dialog
            self.progress_dialog = ProgressDialog(self, "Loading Video...")
            self.progress_dialog.show()

            # Create worker and thread
            self.loading_thread = QThread()
            self.worker = VideoLoadWorker(
                self.video_processor, self.audio_processor, file_path
            )
            self.worker.moveToThread(self.loading_thread)

            # Connect signals
            self.loading_thread.started.connect(self.worker.run)
            self.worker.progress.connect(self.update_progress)
            self.worker.finished.connect(self.on_video_loaded)
            self.worker.error.connect(self.on_load_error)
            self.worker.finished.connect(self.loading_thread.quit)
            self.worker.finished.connect(self.worker.deleteLater)
            self.loading_thread.finished.connect(self.loading_thread.deleteLater)

            # Start loading
            self.loading_thread.start()

    def transcribe_video(self):
        # Get video path
        video_path = self.video_player.current_video_path
        if not video_path:
            QMessageBox.warning(self, "Warning", "No video loaded")
            return

        # Create and show progress dialog
        self.progress_dialog = ProgressDialog(self, "Transcribing Video...")
        self.progress_dialog.show()

        # Create worker and thread
        self.transcription_thread = TranscriptionWorker(video_path)

        # Connect signals
        self.transcription_thread.transcription_progress.connect(
            self.progress_dialog.set_progress
        )
        self.transcription_thread.transcription_done.connect(self.progress_dialog.close)
        self.transcription_thread.transcription_result.connect(
            self.handle_transcription_results
        )
        self.transcription_thread.start()

    def handle_transcription_results(self, tokens: List[dict]):
        """Handle transcription results from worker"""
        # Store results
        if not hasattr(self, "transcription_results"):
            self.transcription_results = []
        self.transcription_results.extend(tokens)

        # Update timeline UI
        if hasattr(self, "timeline_widget"):
            self.timeline_widget.update_transcription(tokens)

    def update_progress(self, value, status):
        """Update progress dialog"""
        if self.progress_dialog:
            self.progress_dialog.set_progress(value, status)

    def on_video_loaded(self, result):
        """Handle successful video load"""
        # Clean up progress dialog
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

        try:
            # Update video player
            self.video_player.load_video(result["path"])

            # Update waveform
            self.timeline.set_audio_data(result["audio_data"])

            # Enable export
            self.export_button.setEnabled(True)

            # Enable transcription
            self.transcribe_button.setEnabled(True)

            # Show success message
            self.statusBar().showMessage(
                f"Loaded video: {Path(result['path']).name} "
                f"({result['duration']:.1f}s, {result['fps']:.2f} fps)",
                5000,
            )

            # Once video is loaded, ensure it's paused initially
            self.video_player.player.pause()

            # Add keyboard event handler if not already present
            self.video_player.setFocusPolicy(Qt.StrongFocus)

        except Exception as e:
            self.on_load_error(str(e))

    def on_load_error(self, error_message):
        """Handle loading errors"""
        # Clean up progress dialog
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

        # Show error message
        QMessageBox.critical(self, "Error", f"Failed to load video: {error_message}")

        # Reset UI state
        self.export_button.setEnabled(False)

    def export_video(self):
        """Handle video export with deleted segments"""
        if not self.timeline.get_deleted_segments():
            QMessageBox.warning(self, "Warning", "No sections marked for deletion")
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self, "Export Video", "", "Video Files (*.mp4);;All Files (*.*)"
        )

        if output_path:
            try:
                # Get all segments marked for deletion
                deleted_segments = self.timeline.get_deleted_segments()

                # Convert deleted segments into kept segments
                kept_segments = self._calculate_kept_segments(deleted_segments)

                # Export video with only kept segments
                self.video_processor.export_with_cuts(
                    self.video_player.current_video_path, output_path, kept_segments
                )
                QMessageBox.information(self, "Success", "Video exported successfully!")

                # Optionally clear deleted segments after successful export
                self.timeline.clear_deleted_segments()

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export video: {str(e)}")

    def _calculate_kept_segments(self, deleted_segments):
        """Calculate segments to keep based on deleted segments"""
        if not deleted_segments:
            return []

        # Sort deleted segments by start time
        deleted_segments.sort(key=lambda x: x[0])

        # Get video duration
        duration = self.video_processor.get_duration(
            self.video_player.current_video_path
        )

        # Calculate kept segments
        kept_segments = []
        current_pos = 0

        for start, end in deleted_segments:
            # Add segment before deletion if it exists
            if start > current_pos:
                kept_segments.append((current_pos, start))
            current_pos = end

        # Add final segment if there's remaining video
        if current_pos < duration:
            kept_segments.append((current_pos, duration))

        return kept_segments

    def setup_connections(self):
        """Set up signal/slot connections between components"""
        # Timeline position changes update video position
        self.timeline.position_changed.connect(self.on_timeline_position_changed)

        # Timeline edit markers trigger video processing
        self.timeline.section_deleted.connect(self.on_section_deleted)

        # Connect video player signals
        self.video_player.position_changed.connect(self.timeline.set_position)
        # self.video_player.duration_changed.connect(self.timeline.set_duration)

        # Connect timeline signals
        self.timeline.position_changed.connect(self.video_player.seek)
        self.timeline.marker_removed.connect(self.on_marker_removed)
        self.timeline.play_toggled.connect(self.video_player.toggle_play)

    def on_timeline_position_changed(self, position):
        """Handle timeline position changes"""
        # Convert position in seconds to VLC position (0-1)
        if self.video_player.current_video_path:
            duration = self.video_processor.get_duration(
                self.video_player.current_video_path
            )
            vlc_pos = position / duration
            self.video_player.seek(vlc_pos)

    def on_video_position_changed(self, position):
        """Handle video position changes"""
        if self.video_player.current_video_path:
            duration = self.video_processor.get_duration(
                self.video_player.current_video_path
            )
            time_pos = position * duration
            self.timeline.set_position(time_pos)
            self.waveform_view.update_position(time_pos)

    def on_section_deleted(self, section):
        """Handle deletion of a timeline section"""
        start, end = section
        # Optionally auto-save or preview the edit
        self.statusBar().showMessage(f"Section deleted: {start:.1f}s - {end:.1f}s")

    def on_marker_removed(self, position):
        """Handle marker removal"""
        self.statusBar().showMessage(f"Removed marker at {position:.2f}s", 2000)

        # If no markers left, disable export
        if not self.timeline.has_markers():
            self.export_button.setEnabled(False)

    def keyPressEvent(self, event):
        # Handle space bar press to play/pause
        if event.key() == Qt.Key_Space:
            if self.video_player.player.state() == QMediaPlayer.PlayingState:
                self.video_player.player.pause()
            else:
                self.video_player.player.play()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
