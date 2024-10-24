from PySide6.QtWidgets import QVBoxLayout, QFrame
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
import pyqtgraph as pg

class UnifiedTimeline(QFrame):
    position_changed = Signal(float)  # Emits position in seconds
    marker_added = Signal(float)      # Emits marker position
    section_deleted = Signal(tuple)   # Emits (start, end) tuple
    marker_removed = Signal(float)
    play_toggled = Signal()

    def __init__(self):
        super().__init__()
        self.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.setMinimumHeight(150)
        
        # Setup main layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Create pyqtgraph plot widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('black')
        self.plot_widget.showGrid(x=True, y=False)
        self.plot_widget.setMouseEnabled(x=True, y=False)
        self.plot_widget.setMenuEnabled(False)
        
        # Remove Y axis - we don't need amplitude values
        self.plot_widget.hideAxis('left')
        
        # Customize X axis
        self.plot_widget.getAxis('bottom').setLabel('Time (s)')
        
        # Add plot widget to layout
        self.layout.addWidget(self.plot_widget)
        
        # Initialize state
        self.duration = 0
        self.position = 0
        self.markers = []  # List of (position, is_start_marker) tuples
        self.audio_data = None
        self.waveform_item = None
        self.position_line = self.plot_widget.addLine(x=0, pen=pg.mkPen('r', width=2))
        
        # Setup marker items
        self.marker_items = []
        self.selection_region = pg.LinearRegionItem([0, 0], brush=pg.mkBrush(100, 100, 255, 50))
        self.selection_region.hide()
        self.plot_widget.addItem(self.selection_region)
        
        # Connect signals
        self.plot_widget.scene().sigMouseClicked.connect(self.on_mouse_clicked)
        self.selection_region.sigRegionChanged.connect(self.on_region_changed)
        
        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)
        self.setup_shortcuts()
    
    def set_audio_data(self, audio_data):
        """Set audio data and display waveform"""
        self.audio_data = audio_data
        
        # Clear existing waveform
        if self.waveform_item is not None:
            self.plot_widget.removeItem(self.waveform_item)
        
        # Plot new waveform
        pen = pg.mkPen('w', width=1)
        self.waveform_item = self.plot_widget.plot(
            audio_data['time'],
            audio_data['samples'],
            pen=pen
        )
        
        # Set view range
        self.plot_widget.setXRange(0, audio_data['duration'])
        self.plot_widget.setYRange(-1, 1)
        
        self.duration = audio_data['duration']
    
    def set_position(self, position):
        """Update current position marker"""
        self.position = position
        self.position_line.setValue(position)
    
    def add_marker(self, position, is_start=True):
        """Add a marker and update selection region"""
        self.markers = [(pos, is_start_) for pos, is_start_ in self.markers 
                       if is_start_ != is_start]
        self.markers.append((position, is_start))
        self.markers.sort()
        
        self._update_selection_region()
        self.marker_added.emit(position)
    
    def _update_selection_region(self):
        """Update the selection region based on markers"""
        starts = [pos for pos, is_start in self.markers if is_start]
        ends = [pos for pos, is_start in self.markers if not is_start]
        
        if starts and ends:
            self.selection_region.setRegion((starts[0], ends[0]))
            self.selection_region.show()
        else:
            self.selection_region.hide()
    
    def on_mouse_clicked(self, event):
        """Handle mouse clicks for adding markers and scrubbing"""
        if event.button() == Qt.LeftButton:
            # Get click position in scene coordinates
            scene_pos = event.scenePos()
            view_pos = self.plot_widget.plotItem.vb.mapSceneToView(scene_pos)
            click_time = view_pos.x()
            
            # Constrain to valid range
            click_time = max(0, min(self.duration, click_time))
            
            # Check if click is near existing marker
            is_near_marker = False
            threshold = self.duration / 100  # 1% of duration
            for pos, _ in self.markers:
                if abs(pos - click_time) < threshold:
                    is_near_marker = True
                    break
            
            if not is_near_marker:
                # Add new marker
                is_start = not any(is_start for _, is_start in self.markers)
                self.add_marker(click_time, is_start)
            
            # Update position
            self.set_position(click_time)
            self.position_changed.emit(click_time)
    
    def on_region_changed(self):
        """Handle selection region changes"""
        start, end = self.selection_region.getRegion()
        # Update markers to match region
        self.markers = [(start, True), (end, False)]
    
    def delete_selected_section(self):
        """Delete the currently selected section"""
        if self.markers:
            start = min(pos for pos, is_start in self.markers if is_start)
            end = max(pos for pos, is_start in self.markers if not is_start)
            self.section_deleted.emit((start, end))
            self.markers = []
            self.selection_region.hide()
    
    def get_markers(self):
        """Get list of (start, end) tuples for valid sections"""
        starts = [pos for pos, is_start in self.markers if is_start]
        ends = [pos for pos, is_start in self.markers if not is_start]
        return list(zip(starts, ends))
    
    def has_markers(self):
        """Check if there are valid start and end markers"""
        return len(self.get_markers()) > 0
    
    def setup_shortcuts(self):
        """Set up keyboard shortcuts"""
        # ESC key to remove last marker
        self.esc_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self.esc_shortcut.activated.connect(self.remove_last_marker)
        
        # Delete key to remove selection
        self.del_shortcut = QShortcut(QKeySequence(Qt.Key_Delete), self)
        self.del_shortcut.activated.connect(self.delete_selected_section)
        
        # Space bar for play/pause (emit signal)
        self.space_shortcut = QShortcut(QKeySequence(Qt.Key_Space), self)
        self.space_shortcut.activated.connect(self.toggle_play)
        
        # Left/Right arrow keys for frame stepping
        self.left_shortcut = QShortcut(QKeySequence(Qt.Key_Left), self)
        self.left_shortcut.activated.connect(lambda: self.step_frame(-1))
        
        self.right_shortcut = QShortcut(QKeySequence(Qt.Key_Right), self)
        self.right_shortcut.activated.connect(lambda: self.step_frame(1))
    
    def remove_last_marker(self):
        """Remove the most recently added marker"""
        if self.markers:
            removed_marker = self.markers.pop()
            self.marker_removed.emit(removed_marker[0])
            self._update_selection_region()
            
            # If we removed a start marker but have an end marker, remove the end marker too
            if removed_marker[1] and any(not is_start for _, is_start in self.markers):
                self.markers = [(pos, is_start) for pos, is_start in self.markers if is_start]
            
            # If we removed an end marker but have a start marker, keep the start marker
            if not removed_marker[1] and any(is_start for _, is_start in self.markers):
                pass  # Keep the start marker
    
    def step_frame(self, direction):
        """Step one frame forward or backward"""
        frame_duration = 1/30  # Assume 30fps, this should be set based on actual video
        new_pos = self.position + (direction * frame_duration)
        new_pos = max(0, min(self.duration, new_pos))
        self.set_position(new_pos)
        self.position_changed.emit(new_pos)
    
    def toggle_play(self):
        """Emit signal to toggle play/pause"""
        # This will be connected to the main window to control video playback
        self.play_toggled.emit()        