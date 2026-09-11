import sys
import os

try:
    from PySide6.QtWidgets import QSplashScreen, QLabel, QWidget, QVBoxLayout, QProgressBar
    from PySide6.QtGui import QPixmap, QFont, QColor, QPainter, QLinearGradient
    from PySide6.QtCore import Qt, QTimer, Signal as pyqtSignal
except ImportError:
    from PyQt6.QtWidgets import QSplashScreen, QLabel, QWidget, QVBoxLayout, QProgressBar
    from PyQt6.QtGui import QPixmap, QFont, QColor, QPainter, QLinearGradient
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal


class SplashWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(480, 320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(12)

        self.title_label = QLabel("Sound IQ")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("""
            font-size: 36px;
            font-weight: bold;
            color: #58A6FF;
            background: transparent;
            font-family: 'Segoe UI', Arial;
        """)
        layout.addWidget(self.title_label)

        self.subtitle_label = QLabel("Local AI Sound Searcher")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setStyleSheet("""
            font-size: 14px;
            color: #8B949E;
            background: transparent;
            font-family: 'Segoe UI', Arial;
        """)
        layout.addWidget(self.subtitle_label)

        layout.addSpacing(20)

        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("""
            font-size: 11px;
            color: #6E7681;
            background: transparent;
            font-family: 'Segoe UI', Arial;
        """)
        layout.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setMaximum(0)
        self.progress.setFixedHeight(4)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #21262D;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #58A6FF;
                border-radius: 2px;
            }
        """)
        layout.addWidget(self.progress)

        self.version_label = QLabel("v2.0.0")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.version_label.setStyleSheet("""
            font-size: 10px;
            color: #484F58;
            background: transparent;
            font-family: 'Segoe UI', Arial;
        """)
        layout.addStretch()
        layout.addWidget(self.version_label)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor("#0D1117"))
        gradient.setColorAt(1, QColor("#161B22"))
        painter.fillRect(self.rect(), gradient)
        painter.setPen(QColor("#21262D"))
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
        painter.end()


def show_splash(on_ready_callback):
    widget = SplashWidget()
    splash = QSplashScreen(widget.grab())
    splash.setWindowFlags(Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
    splash.move(
        int((splash.screen().availableGeometry().width() - widget.width()) / 2),
        int((splash.screen().availableGeometry().height() - widget.height()) / 2),
    )
    splash.show()

    def advance(status_text, delay_ms, callback=None):
        splash.showMessage(
            f"  {status_text}",
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
            QColor("#8B949E"),
        )
        if callback:
            QTimer.singleShot(delay_ms, callback)

    def step1():
        advance("Loading configuration...", 400, step2)

    def step2():
        advance("Preparing audio engine...", 300, step3)

    def step3():
        advance("Loading AI search model...", 400, step4)

    def step4():
        splash.finish(None)
        on_ready_callback()

    QTimer.singleShot(100, step1)
    return splash
