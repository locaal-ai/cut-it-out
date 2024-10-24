import sys
import vlc
from PySide6.QtWidgets import QFrame, QVBoxLayout
from PySide6.QtCore import Qt, Signal

class VideoPlayer(QFrame):
    position_changed = Signal(float)  # Emits position in seconds
    duration_changed = Signal(float)  # Emits duration in seconds
    
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(400)
        self.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        
        # Create VLC instance and player
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()
        self.current_video_path = None
        
        # Create a widget to hold the video
        if sys.platform == "darwin":  # macOS
            from PyQt6.QtWidgets import QMacCocoaViewContainer
            self.video_widget = QMacCocoaViewContainer(0)
        else:  # Windows/Linux
            from PySide6.QtWidgets import QWidget
            self.video_widget = QWidget()
        
        # Set black background
        self.video_widget.setStyleSheet("background-color: black;")
        
        # Create layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.video_widget)
        
        # Ensure video widget gets focus
        self.video_widget.setAttribute(Qt.WA_OpaquePaintEvent)
        
        # Platform-specific setup
        if sys.platform.startswith('linux'):
            self.player.set_xwindow(int(self.video_widget.winId()))
        elif sys.platform == "win32":
            self.player.set_hwnd(int(self.video_widget.winId()))
        elif sys.platform == "darwin":
            self.player.set_nsobject(int(self.video_widget.winId()))
            
        # Set up media player events
        self.player.event_manager().event_attach(
            vlc.EventType.MediaPlayerTimeChanged,
            self._on_time_changed
        )
        self.player.event_manager().event_attach(
            vlc.EventType.MediaPlayerLengthChanged,
            self._on_length_changed
        )
    
    def load_video(self, file_path):
        """Load a video file"""
        self.current_video_path = file_path
        media = self.instance.media_new(file_path)
        self.player.set_media(media)
        # Auto-resize video
        self.player.video_set_aspect_ratio(None)
        self.player.video_set_scale(0)
        self.player.play()  # Start playing
        self.player.pause()  # Immediately pause
    
    def play(self):
        """Start playback"""
        self.player.play()
    
    def pause(self):
        """Pause playback"""
        self.player.pause()
    
    def toggle_play(self):
        """Toggle between play and pause"""
        if self.player.is_playing():
            self.pause()
        else:
            self.play()
    
    def seek(self, position):
        """Seek to position in seconds"""
        if self.player.get_length() > 0:
            # Convert position to milliseconds
            ms_position = int(position * 1000)
            self.player.set_time(ms_position)
    
    def get_position(self):
        """Get current position in seconds"""
        return self.player.get_time() / 1000.0 if self.player.get_time() >= 0 else 0
    
    def get_duration(self):
        """Get video duration in seconds"""
        return self.player.get_length() / 1000.0
    
    def _on_time_changed(self, event):
        """Handle time changed events"""
        self.position_changed.emit(self.get_position())
    
    def _on_length_changed(self, event):
        """Handle length changed events"""
        self.duration_changed.emit(self.get_duration())