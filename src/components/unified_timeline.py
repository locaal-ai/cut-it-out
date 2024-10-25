from PySide6.QtWidgets import QVBoxLayout, QFrame
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QBrush, QColor
import pyqtgraph as pg


class UnifiedTimeline(QFrame):
    position_changed = Signal(float)  # Emits position in seconds
    marker_added = Signal(float)  # Emits marker position
    section_deleted = Signal(tuple)  # Emits (start, end) tuple
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
        self.plot_widget.setBackground("black")
        self.plot_widget.showGrid(x=True, y=False)
        self.plot_widget.setMouseEnabled(x=True, y=False)
        self.plot_widget.setMenuEnabled(False)

        # Get the ViewBox for setting zoom limits
        self.view_box = self.plot_widget.getViewBox()

        # Set up zoom limits
        # Maximum zoom out will show 2x the duration
        # Maximum zoom in will show 1 second of audio
        self.min_zoom_range = 1.0  # 1 second minimum view
        self.max_zoom_range = None  # Will be set when duration is known

        # Set up ViewBox scaling limits
        self.view_box.setLimits(
            xMin=0,  # Cannot scroll before start
            yMin=-1.1,  # Slight padding for waveform
            yMax=1.1,
            minXRange=self.min_zoom_range,  # Minimum view range (maximum zoom in)
            maxYRange=2.2,  # Fixed vertical range
            maxXRange=None,  # Will be set when duration is known
        )

        # Disable vertical scrolling completely
        self.view_box.setMouseEnabled(x=True, y=False)

        # Connect range change signal
        self.view_box.sigRangeChangedManually.connect(self._on_range_changed)

        # Remove Y axis - we don't need amplitude values
        self.plot_widget.hideAxis("left")

        # Customize X axis
        self.plot_widget.getAxis("bottom").setLabel("Time (s)")

        # Add plot widget to layout
        self.layout.addWidget(self.plot_widget)

        # Initialize state
        self.duration = 0
        self.position = 0
        self.markers = []  # List of (position, is_start_marker) tuples
        self.audio_data = None
        self.waveform_item = None
        self.position_line = self.plot_widget.addLine(x=0, pen=pg.mkPen("r", width=2))

        # Setup marker items
        self.marker_items = []
        self.selection_region = pg.LinearRegionItem(
            [0, 0], brush=pg.mkBrush(100, 100, 255, 50)
        )
        self.selection_region.hide()
        self.plot_widget.addItem(self.selection_region)

        # Connect signals
        self.plot_widget.scene().sigMouseClicked.connect(self.on_mouse_clicked)
        self.selection_region.sigRegionChanged.connect(self.on_region_changed)

        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)
        self.setup_shortcuts()

        # Add tracking for deleted segments
        self.deleted_segments = []  # List of (start, end) tuples

        # Create pattern for deleted segments
        self.deletion_pattern = self._create_deletion_pattern()

        # Create separate LinearRegionItems for regular selection and deleted segments
        self.selection_region = pg.LinearRegionItem(
            [0, 0], brush=pg.mkBrush(100, 100, 255, 50), movable=True
        )
        self.selection_region.hide()
        self.plot_widget.addItem(self.selection_region)

        # Create initial deleted region item
        self.deleted_regions = []

    def set_audio_data(self, audio_data):
        """Set audio data and display waveform"""
        self.audio_data = audio_data
        self.duration = audio_data["duration"]

        # Update maximum zoom range (2x duration)
        self.max_zoom_range = self.duration * 2

        # Update ViewBox limits
        self.view_box.setLimits(
            xMax=self.duration,  # Cannot scroll past end
            maxXRange=self.max_zoom_range,  # Maximum view range (maximum zoom out)
        )

        # Clear existing waveform
        if self.waveform_item is not None:
            self.plot_widget.removeItem(self.waveform_item)

        # Plot new waveform
        pen = pg.mkPen("w", width=1)
        self.waveform_item = self.plot_widget.plot(
            audio_data["time"], audio_data["samples"], pen=pen
        )

        # Set initial view to show full duration
        self.view_box.setXRange(0, self.duration, padding=0)

    def set_position(self, position):
        """Update current position marker"""
        self.position = position
        self.position_line.setValue(position)

    def add_marker(self, position, is_start=True):
        """Add a marker and update selection region"""
        self.markers = [
            (pos, is_start_) for pos, is_start_ in self.markers if is_start_ != is_start
        ]
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
                self.markers = [
                    (pos, is_start) for pos, is_start in self.markers if is_start
                ]

            # If we removed an end marker but have a start marker, keep the start marker
            if not removed_marker[1] and any(is_start for _, is_start in self.markers):
                pass  # Keep the start marker

    def step_frame(self, direction):
        """Step one frame forward or backward"""
        frame_duration = (
            1 / 30
        )  # Assume 30fps, this should be set based on actual video
        new_pos = self.position + (direction * frame_duration)
        new_pos = max(0, min(self.duration, new_pos))
        self.set_position(new_pos)
        self.position_changed.emit(new_pos)

    def toggle_play(self):
        """Emit signal to toggle play/pause"""
        # This will be connected to the main window to control video playback
        self.play_toggled.emit()

    def _create_deletion_pattern(self):
        """Create a striped pattern for deleted segments"""
        # Create a brush with diagonal lines
        brush = QBrush(QColor(255, 0, 0, 80))
        brush.setStyle(Qt.BDiagPattern)  # Diagonal line pattern
        return pg.mkBrush(brush)

    def delete_selected_section(self):
        """Mark the current section for deletion"""
        if self.markers and len(self.markers) >= 2:
            # Get start and end markers
            start = min(pos for pos, is_start in self.markers if is_start)
            end = max(pos for pos, is_start in self.markers if not is_start)

            # Add to deleted segments
            self.deleted_segments.append((start, end))

            # Create new deleted region visualization
            deleted_region = pg.LinearRegionItem(
                values=[start, end],
                brush=self.deletion_pattern,
                movable=False,  # Can't move deleted regions
                span=(0, 1),  # Full height
            )
            # Make the border red and dashed
            deleted_region.lines[0].setPen(pg.mkPen("r", style=Qt.DashLine))
            deleted_region.lines[1].setPen(pg.mkPen("r", style=Qt.DashLine))

            self.plot_widget.addItem(deleted_region)
            self.deleted_regions.append(deleted_region)

            # Clear current selection
            self.markers = []
            self.selection_region.hide()

            # Emit signal with all deleted segments
            self.section_deleted.emit((start, end))

    def get_deleted_segments(self):
        """Return list of segments marked for deletion"""
        return self.deleted_segments

    def clear_deleted_segments(self):
        """Clear all deleted segments"""
        self.deleted_segments = []
        for region in self.deleted_regions:
            self.plot_widget.removeItem(region)
        self.deleted_regions = []

    def remove_last_deleted_segment(self):
        """Remove the most recently deleted segment"""
        if self.deleted_segments:
            self.deleted_segments.pop()
            if self.deleted_regions:
                region = self.deleted_regions.pop()
                self.plot_widget.removeItem(region)

    def keyPressEvent(self, event):
        """Handle keyboard events"""
        if event.key() == Qt.Key_Delete:
            self.delete_selected_section()
        elif event.key() == Qt.Key_Escape:
            if self.markers:
                self.remove_last_marker()
            elif self.deleted_segments:
                # If no markers but there are deleted segments, undo last deletion
                self.remove_last_deleted_segment()
        else:
            super().keyPressEvent(event)

    def _on_range_changed(self):
        """Handle manual range changes (zoom/pan)"""
        # Get current view range
        view_range = self.view_box.viewRange()
        x_range = view_range[0]

        # Ensure minimum zoom level (maximum range)
        if x_range[1] - x_range[0] > self.max_zoom_range:
            center = sum(x_range) / 2
            half_range = self.max_zoom_range / 2
            self.view_box.setXRange(center - half_range, center + half_range, padding=0)

        # Ensure maximum zoom level (minimum range)
        elif x_range[1] - x_range[0] < self.min_zoom_range:
            center = sum(x_range) / 2
            half_range = self.min_zoom_range / 2
            self.view_box.setXRange(center - half_range, center + half_range, padding=0)

        # Ensure we don't scroll past the valid range
        if x_range[0] < 0:
            shift = -x_range[0]
            self.view_box.setXRange(x_range[0] + shift, x_range[1] + shift, padding=0)
        elif x_range[1] > self.duration:
            shift = self.duration - x_range[1]
            self.view_box.setXRange(x_range[0] + shift, x_range[1] + shift, padding=0)

    def wheelEvent(self, event):
        """Custom wheel event to control zoom behavior"""
        if self.duration is None:
            return

        # Get current range
        view_range = self.view_box.viewRange()
        current_range = view_range[0][1] - view_range[0][0]

        # Calculate zoom factor based on wheel delta
        zoom_factor = 0.9 if event.angleDelta().y() > 0 else 1.1
        new_range = current_range * zoom_factor

        # Check zoom limits
        if self.min_zoom_range <= new_range <= self.max_zoom_range:
            # Calculate zoom center point based on mouse position
            mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(event.position())
            center_x = mouse_point.x()

            # Calculate new bounds
            half_range = new_range / 2
            left = center_x - half_range
            right = center_x + half_range

            # Adjust bounds if they exceed limits
            if left < 0:
                left = 0
                right = new_range
            elif right > self.duration:
                right = self.duration
                left = right - new_range

            # Apply new range
            self.view_box.setXRange(left, right, padding=0)

        # Consume the event
        event.accept()
