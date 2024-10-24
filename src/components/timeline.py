from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QStyle, QFrame)
from PySide6.QtCore import Qt, Signal, QPointF, QRectF, QTimer
from PySide6.QtGui import (QPainter, QColor, QPen, QBrush, 
                          QLinearGradient, QKeySequence, QShortcut)
import numpy as np

class TimelineWidget(QFrame):
    # Signals
    position_changed = Signal(float)  # Emits position in seconds
    marker_added = Signal(float)      # Emits marker position
    marker_removed = Signal(float)    # Emits marker position
    section_deleted = Signal(tuple)   # Emits (start, end) tuple

    def __init__(self):
        super().__init__()
        self.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.setMinimumHeight(60)
        self.duration = 0
        self.position = 0
        self.markers = []  # List of (position, is_start_marker) tuples
        self.dragging = False
        self.dragging_marker = None
        self.current_marker = None
        
        # Visual settings
        self.marker_width = 10
        self.marker_height = 20
        self.time_markers_height = 15
        
        # Colors
        self.colors = {
            'background': QColor(240, 240, 240),
            'timeline': QColor(200, 200, 200),
            'position': QColor(255, 100, 100),
            'start_marker': QColor(50, 150, 50),
            'end_marker': QColor(150, 50, 50),
            'selection': QColor(100, 150, 255, 50)
        }
        
        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)
        
        # Timer for smooth updates
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update)
        self.update_timer.start(16)  # ~60 FPS
        
        self.setup_shortcuts()
    
    def setup_shortcuts(self):
        """Set up keyboard shortcuts"""
        self.delete_shortcut = QShortcut(QKeySequence(Qt.Key_Delete), self)
        self.delete_shortcut.activated.connect(self.delete_selected_section)
        return self.delete_shortcut
    
    def set_duration(self, duration):
        """Set the total duration of the timeline in seconds"""
        self.duration = duration
        self.update()
    
    def set_position(self, position):
        """Set the current playback position in seconds"""
        self.position = min(max(0, position), self.duration)
        self.position_changed.emit(self.position)
        self.update()
    
    def add_marker(self, position, is_start=True):
        """Add a marker at the specified position"""
        # Remove existing marker of same type
        self.markers = [(pos, is_start_) for pos, is_start_ in self.markers 
                       if is_start_ != is_start]
        self.markers.append((position, is_start))
        self.markers.sort()  # Sort by position
        self.marker_added.emit(position)
        self.update()
    
    def get_markers(self):
        """Return list of (start, end) tuples for valid sections"""
        starts = [pos for pos, is_start in self.markers if is_start]
        ends = [pos for pos, is_start in self.markers if not is_start]
        return list(zip(starts, ends))
    
    def has_markers(self):
        """Check if there are valid start and end markers"""
        return len(self.get_markers()) > 0
    
    def delete_selected_section(self):
        """Delete the currently selected section"""
        markers = self.get_markers()
        if markers:
            start, end = markers[0]  # For now, just handle one section
            self.section_deleted.emit((start, end))
            self.markers = []
            self.update()
    
    def paintEvent(self, event):
        """Draw the timeline and markers"""
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw background
        painter.fillRect(self.rect(), self.colors['background'])
        
        # Draw time markers
        self._draw_time_markers(painter)
        
        # Draw timeline base
        timeline_rect = self._get_timeline_rect()
        painter.fillRect(timeline_rect, self.colors['timeline'])
        
        # Draw selection regions
        self._draw_selections(painter, timeline_rect)
        
        # Draw position indicator
        self._draw_position(painter, timeline_rect)
        
        # Draw markers
        self._draw_markers(painter, timeline_rect)
    
    def _get_timeline_rect(self):
        """Get the rectangle for the main timeline area"""
        return QRectF(
            0, 
            self.time_markers_height,
            self.width(),
            self.height() - self.time_markers_height
        )
    
    def _draw_time_markers(self, painter):
        """Draw time markers and labels"""
        if self.duration == 0:
            return
        width = self.width()
        # Draw major time markers every 5 seconds
        interval = 5
        num_markers = int(self.duration / interval) + 1
        
        painter.setPen(QPen(Qt.darkGray))
        for i in range(num_markers):
            x = (i * interval / self.duration) * width
            painter.drawLine(int(x), 0, int(x), self.time_markers_height)
            painter.drawText(
                int(x) - 20, 
                0, 
                40, 
                self.time_markers_height,
                Qt.AlignCenter,
                f"{i * interval}s"
            )
    
    def _draw_selections(self, painter, timeline_rect):
        """Draw selected regions"""
        markers = self.get_markers()
        for start, end in markers:
            x1 = (start / self.duration) * timeline_rect.width()
            x2 = (end / self.duration) * timeline_rect.width()
            selection_rect = QRectF(
                x1,
                timeline_rect.top(),
                x2 - x1,
                timeline_rect.height()
            )
            painter.fillRect(selection_rect, self.colors['selection'])
    
    def _draw_position(self, painter, timeline_rect):
        """Draw the current position indicator"""
        if self.duration > 0:
            x = (self.position / self.duration) * timeline_rect.width()
            painter.setPen(QPen(self.colors['position'], 2))
            painter.drawLine(
                int(x),
                int(timeline_rect.top()),
                int(x),
                int(timeline_rect.bottom())
            )
    
    def _draw_markers(self, painter, timeline_rect):
        """Draw start and end markers"""
        for position, is_start in self.markers:
            x = (position / self.duration) * timeline_rect.width()
            color = self.colors['start_marker'] if is_start else self.colors['end_marker']
            
            # Draw triangle marker
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))
            
            if is_start:
                points = [
                    QPointF(x, timeline_rect.top()),
                    QPointF(x + self.marker_width, timeline_rect.top()),
                    QPointF(x, timeline_rect.top() + self.marker_height)
                ]
            else:
                points = [
                    QPointF(x - self.marker_width, timeline_rect.top()),
                    QPointF(x, timeline_rect.top()),
                    QPointF(x, timeline_rect.top() + self.marker_height)
                ]
            
            painter.drawPolygon(points)
    
    def mousePressEvent(self, event):
        """Handle mouse press events for marker manipulation and position setting"""
        if event.button() == Qt.LeftButton:
            timeline_rect = self._get_timeline_rect()
            if timeline_rect.contains(event.position()):
                # Check if clicking near existing marker
                click_pos = self._position_from_x(event.position().x())
                marker_index = self._find_nearby_marker(click_pos)
                
                if marker_index is not None:
                    # Start dragging existing marker
                    self.dragging = True
                    self.dragging_marker = marker_index
                else:
                    # Set new marker
                    is_start = not any(is_start for _, is_start in self.markers)
                    self.add_marker(click_pos, is_start)
            
            self.dragging = True
    
    def mouseMoveEvent(self, event):
        """Handle mouse move events for marker dragging and hover effects"""
        if self.dragging and self.dragging_marker is not None:
            # Update marker position
            new_pos = self._position_from_x(event.position().x())
            self.markers[self.dragging_marker] = (new_pos, self.markers[self.dragging_marker][1])
            self.markers.sort()
            self.update()
        else:
            # Update hover state
            click_pos = self._position_from_x(event.position().x())
            self.current_marker = self._find_nearby_marker(click_pos)
            self.update()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release events"""
        if event.button() == Qt.LeftButton:
            self.dragging = False
            self.dragging_marker = None
            # Emit final position if marker was being dragged
            if self.current_marker is not None:
                self.marker_added.emit(self.markers[self.current_marker][0])
    
    def _position_from_x(self, x):
        """Convert x coordinate to timeline position"""
        return max(0, min(self.duration, (x / self.width()) * self.duration))
    
    def _find_nearby_marker(self, position, threshold=0.5):
        """Find marker near given position within threshold (in seconds)"""
        for i, (pos, _) in enumerate(self.markers):
            if abs(pos - position) < threshold:
                return i
        return None