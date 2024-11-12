from PySide6.QtWidgets import QDialog, QProgressBar, QLabel, QVBoxLayout
from PySide6.QtCore import Qt, Signal


class ProgressDialog(QDialog):
    canceled = Signal()

    def __init__(self, parent=None, title="Processing..."):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModal)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)

        # Create layout
        layout = QVBoxLayout(self)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel()
        layout.addWidget(self.status_label)

        # Fixed size
        self.setFixedSize(300, 100)

    def set_progress(self, value, status=None):
        """Update progress bar and optionally status text"""
        self.progress_bar.setValue(int(value))
        if status:
            self.status_label.setText(status)
