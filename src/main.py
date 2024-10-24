from pathlib import Path
import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QFileDialog, QMessageBox)
from PySide6.QtCore import Qt
from components.unified_timeline import UnifiedTimeline
from components.video_player import VideoPlayer
from components.waveform import WaveformView
from components.timeline import TimelineWidget
from utils.audio_processor import AudioProcessor
from utils.video_processor import VideoProcessor
from PySide6.QtCore import QThread
from components.progress_dialog import ProgressDialog
from utils.async_worker import VideoLoadWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Editor")
        self.setGeometry(100, 100, 1200, 800)
        
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
        
        controls_layout.addWidget(self.load_button)
        controls_layout.addWidget(self.export_button)
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)

    def on_video_loaded(self, result):
        """Handle successful video load"""
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
        
        try:
            # Update video player
            self.video_player.load_video(result['path'])
            
            # Update unified timeline
            self.timeline.set_audio_data(result['audio_data'])
            
            # Enable export
            self.export_button.setEnabled(True)
            
            # Show success message
            self.statusBar().showMessage(
                f"Loaded video: {Path(result['path']).name} "
                f"({result['duration']:.1f}s, {result['fps']:.2f} fps)",
                5000
            )
            
        except Exception as e:
            self.on_load_error(str(e))
        
    def load_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Video File",
            "",
            "Video Files (*.mp4 *.avi *.mkv *.mov);;All Files (*.*)"
        )
        
        if file_path:
            # Create and show progress dialog
            self.progress_dialog = ProgressDialog(self)
            self.progress_dialog.show()
            
            # Create worker and thread
            self.loading_thread = QThread()
            self.worker = VideoLoadWorker(
                self.video_processor,
                self.audio_processor,
                file_path
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
            self.video_player.load_video(result['path'])
            
            # Update waveform
            self.timeline.set_audio_data(result['audio_data'])
            
            # Enable export
            self.export_button.setEnabled(True)
            
            # Show success message
            self.statusBar().showMessage(
                f"Loaded video: {Path(result['path']).name} "
                f"({result['duration']:.1f}s, {result['fps']:.2f} fps)",
                5000
            )
            
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
        if not self.timeline.has_markers():
            QMessageBox.warning(self, "Warning", "Please set edit markers before exporting")
            return
            
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Video",
            "",
            "Video Files (*.mp4);;All Files (*.*)"
        )
        
        if output_path:
            try:
                markers = self.timeline.get_markers()
                self.video_processor.export_with_cuts(
                    self.video_player.current_video_path,
                    output_path,
                    markers
                )
                QMessageBox.information(self, "Success", "Video exported successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export video: {str(e)}")

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
            duration = self.video_processor.get_duration(self.video_player.current_video_path)
            vlc_pos = position / duration
            self.video_player.seek(vlc_pos)

    def on_video_position_changed(self, position):
        """Handle video position changes"""
        if self.video_player.current_video_path:
            duration = self.video_processor.get_duration(self.video_player.current_video_path)
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

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()