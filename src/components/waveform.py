import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Qt

class WaveformView(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Set up pyqtgraph plot
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.setMaximumHeight(150)
        self.plot_widget.showGrid(x=True, y=False)
        self.plot_widget.setLabel('bottom', 'Time (s)')
        
        # Remove Y axis - we don't need specific amplitude values
        self.plot_widget.hideAxis('left')
        
        self.layout.addWidget(self.plot_widget)
        
    def set_audio_data(self, audio_data):
        # Clear previous plot
        self.plot_widget.clear()
        
        # Plot the waveform
        pen = pg.mkPen(color='b', width=1)
        self.plot_widget.plot(audio_data['time'], audio_data['samples'], pen=pen)
        
        # Update view limits
        self.plot_widget.setXRange(0, audio_data['duration'])
        self.plot_widget.setYRange(-1, 1)