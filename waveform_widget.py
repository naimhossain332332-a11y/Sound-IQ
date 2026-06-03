import os
import tempfile
import numpy as np

# Dynamic import of PySide6 or PyQt6
try:
    from PySide6.QtWidgets import QWidget, QApplication
    from PySide6.QtCore import Qt, QRectF, QPoint, QUrl, QMimeData, Signal as pyqtSignal
    from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QDrag
except ImportError:
    from PyQt6.QtWidgets import QWidget, QApplication
    from PyQt6.QtCore import Qt, QRectF, QPoint, QUrl, QMimeData, pyqtSignal
    from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QDrag

class WaveformWidget(QWidget):
    # Signals
    seek_requested = pyqtSignal(float)          # Emit target time in seconds
    selection_changed = pyqtSignal(float, float) # Emit (start_sec, end_sec)
    selection_cleared = pyqtSignal()
    drag_started = pyqtSignal()                 # Notify when drag starts

    def __init__(self, parent=None):
        super().__init__(parent)
        self.audio_data = None
        self.duration = 0.0
        self.peaks = None
        self.playhead_sec = 0.0
        
        # Selection bounds in seconds
        self.sel_start_sec = None
        self.sel_end_sec = None
        
        self.is_dragging_selection = False
        self.is_scrubbing = False
        self.is_right_selecting = False   # right-click drag selection mode
        self.drag_start_x = 0
        self.right_drag_origin_x = 0      # where right-click started
        
        # UI Colors (Soundly inspired dark-mode palette)
        self.color_bg = QColor("#121820")
        self.color_wave_unselected = QColor("#4E5C6E")
        self.color_wave_selected = QColor("#00E5FF")
        self.color_wave_played = QColor("#00B0FF")
        self.color_selection_bg = QColor(0, 229, 255, 30) # Semi-transparent neon blue
        self.color_playhead = QColor("#FF6D00")          # Orange playhead
        self.color_border = QColor("#222F3E")
        
        self.setMinimumHeight(120)
        self.setMouseTracking(True)

    def set_audio_data(self, data, duration):
        """Load audio array and compute peaks for drawing."""
        self.audio_data = data
        self.duration = duration
        self.playhead_sec = 0.0
        self.sel_start_sec = None
        self.sel_end_sec = None
        
        self._compute_peaks()
        self.update()

    def set_playhead_position(self, seconds):
        """Update playhead position and redraw."""
        self.playhead_sec = max(0.0, min(self.duration, seconds))
        self.update()

    def clear(self):
        """Clear loaded waveform."""
        self.audio_data = None
        self.duration = 0.0
        self.peaks = None
        self.playhead_sec = 0.0
        self.sel_start_sec = None
        self.sel_end_sec = None
        self.update()

    def get_selection(self):
        """Return active selection in seconds (start, end) or None."""
        if self.sel_start_sec is not None and self.sel_end_sec is not None:
            # Sort bounds
            start = min(self.sel_start_sec, self.sel_end_sec)
            end = max(self.sel_start_sec, self.sel_end_sec)
            if end - start > 0.01:
                return start, end
        return None

    def clear_selection(self):
        """Clear selection bounds and notify."""
        self.sel_start_sec = None
        self.sel_end_sec = None
        self.selection_cleared.emit()
        self.update()

    def _compute_peaks(self):
        """Compute peaks for drawing using fast vectorized numpy operations."""
        if self.audio_data is None or len(self.audio_data) == 0:
            self.peaks = None
            return
            
        # Convert stereo to mono for visual simplicity
        if len(self.audio_data.shape) > 1:
            mono_data = np.mean(self.audio_data, axis=1)
        else:
            mono_data = self.audio_data
            
        length = len(mono_data)
        width = self.width()
        if width <= 0:
            width = 800
            
        # Vectorized calculation of min/max peaks
        bin_size = max(1, length // width)
        num_bins = length // bin_size
        
        if num_bins > 0:
            truncated_len = num_bins * bin_size
            reshaped = mono_data[:truncated_len].reshape(num_bins, bin_size)
            p_mins = np.min(reshaped, axis=1)
            p_maxs = np.max(reshaped, axis=1)
            
            # Map/interpolate to exactly 'width' points if num_bins != width
            if num_bins != width:
                xp = np.linspace(0, width - 1, num_bins)
                x = np.arange(width)
                p_mins = np.interp(x, xp, p_mins)
                p_maxs = np.interp(x, xp, p_maxs)
                
            self.peaks = list(zip(p_mins.tolist(), p_maxs.tolist()))
        else:
            self.peaks = [(0.0, 0.0)] * width

    def resizeEvent(self, event):
        """Recompute peaks when widget is resized."""
        super().resizeEvent(event)
        self._compute_peaks()

    def paintEvent(self, event):
        """Render background, waveform, selection, playhead."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 1. Background
        painter.fillRect(self.rect(), self.color_bg)
        
        # Draw border
        painter.setPen(QPen(self.color_border, 1))
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
        
        if self.peaks is None or self.duration == 0.0:
            painter.setPen(QPen(QColor("#7F8C8D"), 1))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No Audio Loaded")
            painter.end()
            return
            
        width = self.width()
        height = self.height()
        mid_y = height / 2.0
        
        # 2. Draw selection background overlay
        sel = self.get_selection()
        if sel:
            start_x = int((sel[0] / self.duration) * width)
            end_x = int((sel[1] / self.duration) * width)
            painter.fillRect(start_x, 0, end_x - start_x, height, self.color_selection_bg)
            
        # 3. Draw Waveform
        playhead_x = int((self.playhead_sec / self.duration) * width)
        
        for x in range(min(width, len(self.peaks))):
            p_min, p_max = self.peaks[x]
            
            # Map peak values to pixels (scale to 85% of widget height)
            y_top = mid_y - (p_max * mid_y * 0.85)
            y_bot = mid_y - (p_min * mid_y * 0.85)
            
            # Ensure at least 1px height is drawn for silence
            if abs(y_bot - y_top) < 1.0:
                y_top = mid_y - 1
                y_bot = mid_y + 1
                
            # Determine color
            current_time = (x / width) * self.duration
            
            # Color hierarchy:
            # - If inside selection range: Neon Cyan/Blue
            # - If played (left of playhead): Light Slate Blue
            # - Otherwise: Dim slate
            if sel and sel[0] <= current_time <= sel[1]:
                pen_color = self.color_wave_selected
            elif current_time <= self.playhead_sec:
                pen_color = self.color_wave_played
            else:
                pen_color = self.color_wave_unselected
                
            painter.setPen(QPen(pen_color, 1))
            painter.drawLine(x, int(y_top), x, int(y_bot))
            
        # 4. Draw selection boundary markers
        if sel:
            painter.setPen(QPen(self.color_wave_selected, 1.5, Qt.PenStyle.SolidLine))
            painter.drawLine(start_x, 0, start_x, height)
            painter.drawLine(end_x, 0, end_x, height)
            
            # Draw handles
            painter.fillRect(start_x - 3, 0, 6, 12, QBrush(self.color_wave_selected))
            painter.fillRect(end_x - 3, 0, 6, 12, QBrush(self.color_wave_selected))
            
        # 5. Draw Playhead
        painter.setPen(QPen(self.color_playhead, 1.5))
        painter.drawLine(playhead_x, 0, playhead_x, height)
        
        # Playhead triangle top marker
        triangle = [
            QPoint(playhead_x - 6, 0),
            QPoint(playhead_x + 6, 0),
            QPoint(playhead_x, 8)
        ]
        painter.setBrush(QBrush(self.color_playhead))
        painter.drawPolygon(triangle)
        
        painter.end()

    def _x_to_time(self, x):
        """Map x coordinate to time in seconds."""
        if self.duration == 0.0:
            return 0.0
        pct = max(0.0, min(1.0, x / self.width()))
        return pct * self.duration

    def mousePressEvent(self, event):
        """Handle mouse clicks: left=scrub/select, right=start selection."""
        if self.peaks is None:
            return

        # ---- Right button: start a new selection ----
        if event.button() == Qt.MouseButton.RightButton:
            x = event.position().x()
            click_time = self._x_to_time(x)
            self.sel_start_sec = click_time
            self.sel_end_sec = click_time
            self.right_drag_origin_x = x
            self.is_right_selecting = True
            self.update()
            return

        # ---- Left button ----
        if event.button() == Qt.MouseButton.LeftButton:
            x = event.position().x()
            click_time = self._x_to_time(x)

            # Click inside existing selection starts a drag operation
            sel = self.get_selection()
            if sel and sel[0] <= click_time <= sel[1]:
                self.drag_start_x = x
                self.is_dragging_selection = True
                return

            # Shift+drag extends/creates selection
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.sel_start_sec = click_time
                self.sel_end_sec = click_time
                self.selection_changed.emit(click_time, click_time)
                self.is_scrubbing = False
            else:
                # Plain left click = scrub playhead + clear selection
                self.is_scrubbing = True
                self.seek_requested.emit(click_time)
                self.clear_selection()

            self.update()

    def mouseMoveEvent(self, event):
        """Handle mouse movements: scrub, select (shift or right-drag), or initiate drag."""
        if self.peaks is None:
            return

        x = event.position().x()
        curr_time = self._x_to_time(x)

        # Right-click drag → grow selection
        if self.is_right_selecting and event.buttons() & Qt.MouseButton.RightButton:
            self.sel_end_sec = curr_time
            start = min(self.sel_start_sec, self.sel_end_sec)
            end = max(self.sel_start_sec, self.sel_end_sec)
            if end - start > 0.01:
                self.selection_changed.emit(start, end)
            self.update()
            return

        # Left-click inside selection → initiate drag-and-drop after threshold
        if self.is_dragging_selection:
            if abs(x - self.drag_start_x) > 10:
                self.is_dragging_selection = False
                self.drag_started.emit()
            return

        # Shift+left drag → grow selection
        if event.buttons() & Qt.MouseButton.LeftButton and event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            if self.sel_start_sec is not None:
                self.sel_end_sec = curr_time
                start = min(self.sel_start_sec, self.sel_end_sec)
                end = max(self.sel_start_sec, self.sel_end_sec)
                self.selection_changed.emit(start, end)
                self.update()

        # Plain left drag → scrub playhead
        elif self.is_scrubbing and event.buttons() & Qt.MouseButton.LeftButton:
            self.seek_requested.emit(curr_time)
            self.update()

    def mouseReleaseEvent(self, event):
        """Finish mouse operations."""
        if event.button() == Qt.MouseButton.RightButton:
            # Finalise right-click selection
            self.is_right_selecting = False
            # If selection is large enough, emit it; otherwise clear
            sel = self.get_selection()
            if sel:
                self.selection_changed.emit(sel[0], sel[1])
            else:
                self.clear_selection()
            return

        self.is_scrubbing = False
        self.is_dragging_selection = False

    def mouseDoubleClickEvent(self, event):
        """Double click clears selection."""
        if self.peaks is not None:
            self.clear_selection()
