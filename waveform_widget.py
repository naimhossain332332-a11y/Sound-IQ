import os
import numpy as np

try:
    from PySide6.QtWidgets import QWidget, QApplication
    from PySide6.QtCore import Qt, QRectF, QPoint, QUrl, QMimeData, QTimer, Signal as pyqtSignal
    from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QDrag
except ImportError:
    from PyQt6.QtWidgets import QWidget, QApplication
    from PyQt6.QtCore import Qt, QRectF, QPoint, QUrl, QMimeData, QTimer, pyqtSignal
    from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QDrag


class WaveformWidget(QWidget):
    seek_requested = pyqtSignal(float)
    selection_changed = pyqtSignal(float, float)
    selection_cleared = pyqtSignal()
    drag_started = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.audio_data = None
        self.duration = 0.0
        self.peaks = None
        self.playhead_sec = 0.0

        self.sel_start_sec = None
        self.sel_end_sec = None

        self.is_dragging_selection = False
        self.is_scrubbing = False
        self.is_right_selecting = False
        self.drag_start_x = 0
        self.right_drag_origin_x = 0

        self.color_bg = QColor("#121820")
        self.color_wave_unselected = QColor("#4E5C6E")
        self.color_wave_selected = QColor("#00E5FF")
        self.color_wave_played = QColor("#00B0FF")
        self.color_selection_bg = QColor(0, 229, 255, 30)
        self.color_playhead = QColor("#FF6D00")
        self.color_border = QColor("#222F3E")
        self.color_time_text = QColor("#6E7681")
        self.color_grid = QColor("#1A2030")

        self.setMinimumHeight(120)
        self.setMouseTracking(True)

        self._zoom_level = 1.0
        self._zoom_center = 0.5
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(150)
        self._resize_timer.timeout.connect(self._do_resize_recompute)
        self._last_width = 0

    def set_audio_data(self, data, duration):
        self.audio_data = data
        self.duration = duration
        self.playhead_sec = 0.0
        self.sel_start_sec = None
        self.sel_end_sec = None
        self._zoom_level = 1.0
        self._zoom_center = 0.5
        self._compute_peaks()
        self.update()

    def set_playhead_position(self, seconds):
        self.playhead_sec = max(0.0, min(self.duration, seconds))
        self.update()

    def clear(self):
        self.audio_data = None
        self.duration = 0.0
        self.peaks = None
        self.playhead_sec = 0.0
        self.sel_start_sec = None
        self.sel_end_sec = None
        self._zoom_level = 1.0
        self._zoom_center = 0.5
        self.update()

    def get_selection(self):
        if self.sel_start_sec is not None and self.sel_end_sec is not None:
            start = min(self.sel_start_sec, self.sel_end_sec)
            end = max(self.sel_start_sec, self.sel_end_sec)
            if end - start > 0.01:
                return start, end
        return None

    def clear_selection(self):
        self.sel_start_sec = None
        self.sel_end_sec = None
        self.selection_cleared.emit()
        self.update()

    def zoom_in(self):
        self._zoom_level = min(20.0, self._zoom_level * 1.5)
        self._compute_peaks()
        self.update()

    def zoom_out(self):
        self._zoom_level = max(1.0, self._zoom_level / 1.5)
        self._compute_peaks()
        self.update()

    def zoom_fit(self):
        self._zoom_level = 1.0
        self._zoom_center = 0.5
        self._compute_peaks()
        self.update()

    def zoom_to_selection(self):
        sel = self.get_selection()
        if sel:
            self._zoom_center = (sel[0] + sel[1]) / (2.0 * self.duration) if self.duration > 0 else 0.5
            span = (sel[1] - sel[0]) / self.duration if self.duration > 0 else 1.0
            self._zoom_level = max(1.0, min(20.0, 1.0 / max(span, 0.01)))
            self._compute_peaks()
            self.update()

    def _get_visible_range(self):
        if self.duration == 0.0:
            return 0.0, self.duration
        half_span = self.duration / (2.0 * self._zoom_level)
        center_sec = self._zoom_center * self.duration
        start_sec = max(0.0, center_sec - half_span)
        end_sec = min(self.duration, center_sec + half_span)
        return start_sec, end_sec

    def _compute_peaks(self):
        if self.audio_data is None or len(self.audio_data) == 0:
            self.peaks = None
            return

        if len(self.audio_data.shape) > 1:
            mono_data = np.mean(self.audio_data, axis=1)
        else:
            mono_data = self.audio_data

        start_sec, end_sec = self._get_visible_range()
        start_sample = int(start_sec * self.sr) if hasattr(self, "sr") else int(start_sec * 44100)
        end_sample = int(end_sec * self.sr) if hasattr(self, "sr") else int(end_sec * 44100)
        sr = getattr(self, "sr", 44100)

        if self.duration > 0:
            start_sample = int(start_sec / self.duration * len(mono_data))
            end_sample = int(end_sec / self.duration * len(mono_data))

        start_sample = max(0, start_sample)
        end_sample = min(len(mono_data), end_sample)

        visible_data = mono_data[start_sample:end_sample]
        if len(visible_data) == 0:
            self.peaks = [(0.0, 0.0)] * max(1, self.width())
            return

        width = self.width()
        if width <= 0:
            width = 800

        bin_size = max(1, len(visible_data) // width)
        num_bins = len(visible_data) // bin_size

        if num_bins > 0:
            truncated_len = num_bins * bin_size
            reshaped = visible_data[:truncated_len].reshape(num_bins, bin_size)
            p_mins = np.min(reshaped, axis=1)
            p_maxs = np.max(reshaped, axis=1)

            if num_bins != width:
                xp = np.linspace(0, width - 1, num_bins)
                x = np.arange(width)
                p_mins = np.interp(x, xp, p_mins)
                p_maxs = np.interp(x, xp, p_maxs)

            self.peaks = list(zip(p_mins.tolist(), p_maxs.tolist()))
        else:
            self.peaks = [(0.0, 0.0)] * width

    def resizeEvent(self, event):
        super().resizeEvent(event)
        new_width = self.width()
        if abs(new_width - self._last_width) > 5:
            self._last_width = new_width
            self._resize_timer.start()

    def _do_resize_recompute(self):
        self._compute_peaks()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.fillRect(self.rect(), self.color_bg)
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

        start_sec, end_sec = self._get_visible_range()
        visible_duration = end_sec - start_sec

        if self._zoom_level > 1.0:
            grid_step = self._get_grid_step(visible_duration)
            t = int(start_sec / grid_step) * grid_step
            painter.setFont(painter.font())
            while t <= end_sec:
                x = int(((t - start_sec) / visible_duration) * width)
                if 0 <= x <= width:
                    painter.setPen(QPen(self.color_grid, 1, Qt.PenStyle.DotLine))
                    painter.drawLine(x, 0, x, height)
                    minutes = int(t // 60)
                    seconds = t % 60
                    time_str = f"{minutes}:{seconds:05.2f}"
                    painter.setPen(QPen(self.color_time_text, 1))
                    painter.drawText(x + 3, height - 5, time_str)
                t += grid_step

        sel = self.get_selection()
        if sel:
            start_x = int(((sel[0] - start_sec) / visible_duration) * width)
            end_x = int(((sel[1] - start_sec) / visible_duration) * width)
            start_x = max(0, min(width, start_x))
            end_x = max(0, min(width, end_x))
            painter.fillRect(start_x, 0, end_x - start_x, height, self.color_selection_bg)

        playhead_x = int(((self.playhead_sec - start_sec) / visible_duration) * width)

        for x in range(min(width, len(self.peaks))):
            p_min, p_max = self.peaks[x]
            y_top = mid_y - (p_max * mid_y * 0.85)
            y_bot = mid_y - (p_min * mid_y * 0.85)

            if abs(y_bot - y_top) < 1.0:
                y_top = mid_y - 1
                y_bot = mid_y + 1

            current_time = start_sec + (x / width) * visible_duration

            if sel and sel[0] <= current_time <= sel[1]:
                pen_color = self.color_wave_selected
            elif current_time <= self.playhead_sec:
                pen_color = self.color_wave_played
            else:
                pen_color = self.color_wave_unselected

            painter.setPen(QPen(pen_color, 1))
            painter.drawLine(x, int(y_top), x, int(y_bot))

        if sel:
            painter.setPen(QPen(self.color_wave_selected, 1.5, Qt.PenStyle.SolidLine))
            painter.drawLine(start_x, 0, start_x, height)
            painter.drawLine(end_x, 0, end_x, height)
            painter.fillRect(start_x - 3, 0, 6, 12, QBrush(self.color_wave_selected))
            painter.fillRect(end_x - 3, 0, 6, 12, QBrush(self.color_wave_selected))

        if 0 <= playhead_x <= width:
            painter.setPen(QPen(self.color_playhead, 2))
            painter.drawLine(playhead_x, 0, playhead_x, height)
            triangle = [
                QPoint(playhead_x - 6, 0),
                QPoint(playhead_x + 6, 0),
                QPoint(playhead_x, 8),
            ]
            painter.setBrush(QBrush(self.color_playhead))
            painter.drawPolygon(triangle)

        if self._zoom_level > 1.0:
            zoom_text = f"Zoom: {self._zoom_level:.1f}x"
            painter.setPen(QPen(QColor("#484F58"), 1))
            painter.drawText(width - 80, 15, zoom_text)

        painter.end()

    def _get_grid_step(self, visible_duration):
        if visible_duration > 60:
            return 10.0
        elif visible_duration > 30:
            return 5.0
        elif visible_duration > 10:
            return 2.0
        elif visible_duration > 5:
            return 1.0
        elif visible_duration > 2:
            return 0.5
        elif visible_duration > 1:
            return 0.25
        else:
            return 0.1

    def _x_to_time(self, x):
        if self.duration == 0.0:
            return 0.0
        start_sec, end_sec = self._get_visible_range()
        pct = max(0.0, min(1.0, x / self.width()))
        return start_sec + pct * (end_sec - start_sec)

    def wheelEvent(self, event):
        if self.peaks is None:
            return
        delta = event.angleDelta().y()
        if delta > 0:
            self.zoom_in()
        elif delta < 0:
            self.zoom_out()
        event.accept()

    def mousePressEvent(self, event):
        if self.peaks is None:
            return

        if event.button() == Qt.MouseButton.RightButton:
            x = event.position().x()
            click_time = self._x_to_time(x)
            self.sel_start_sec = click_time
            self.sel_end_sec = click_time
            self.right_drag_origin_x = x
            self.is_right_selecting = True
            self.update()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            x = event.position().x()
            click_time = self._x_to_time(x)

            sel = self.get_selection()
            if sel and sel[0] <= click_time <= sel[1]:
                self.drag_start_x = x
                self.is_dragging_selection = True
                return

            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.sel_start_sec = click_time
                self.sel_end_sec = click_time
                self.selection_changed.emit(click_time, click_time)
                self.is_scrubbing = False
            else:
                self.is_scrubbing = True
                self.seek_requested.emit(click_time)
                self.clear_selection()

            self.update()

    def mouseMoveEvent(self, event):
        if self.peaks is None:
            return

        x = event.position().x()
        curr_time = self._x_to_time(x)

        if self.is_right_selecting and event.buttons() & Qt.MouseButton.RightButton:
            self.sel_end_sec = curr_time
            start = min(self.sel_start_sec, self.sel_end_sec)
            end = max(self.sel_start_sec, self.sel_end_sec)
            if end - start > 0.01:
                self.selection_changed.emit(start, end)
            self.update()
            return

        if self.is_dragging_selection:
            if abs(x - self.drag_start_x) > 10:
                self.is_dragging_selection = False
                self.drag_started.emit()
            return

        if event.buttons() & Qt.MouseButton.LeftButton and event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            if self.sel_start_sec is not None:
                self.sel_end_sec = curr_time
                start = min(self.sel_start_sec, self.sel_end_sec)
                end = max(self.sel_start_sec, self.sel_end_sec)
                self.selection_changed.emit(start, end)
                self.update()
        elif self.is_scrubbing and event.buttons() & Qt.MouseButton.LeftButton:
            self.seek_requested.emit(curr_time)
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.is_right_selecting = False
            sel = self.get_selection()
            if sel:
                self.selection_changed.emit(sel[0], sel[1])
            else:
                self.clear_selection()
            return

        self.is_scrubbing = False
        self.is_dragging_selection = False

    def mouseDoubleClickEvent(self, event):
        if self.peaks is not None:
            self.zoom_fit()
