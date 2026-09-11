import sys
import os
import tempfile
import threading
import logging
from pathlib import Path

import soundfile as sf
import numpy as np

from config import AppSettings, APP_NAME, APP_VERSION, LOG_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "soundiq.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("SoundIQ.app")

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QSplitter, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
        QHeaderView, QFileDialog, QLabel, QSlider, QProgressBar,
        QListWidget, QListWidgetItem, QMenu, QAbstractItemView, QSystemTrayIcon,
        QToolButton, QFrame, QStatusBar, QMessageBox, QCheckBox, QSpinBox,
    )
    from PySide6.QtGui import QShortcut, QKeySequence, QFont, QIcon, QAction, QDrag, QCursor
    from PySide6.QtCore import Qt, QThread, Signal as pyqtSignal, QSize, QUrl, QMimeData, QTimer
    HAS_TRAY = True
except ImportError:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QSplitter, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
        QHeaderView, QFileDialog, QLabel, QSlider, QProgressBar,
        QListWidget, QListWidgetItem, QMenu, QAbstractItemView, QSystemTrayIcon,
        QToolButton, QFrame, QStatusBar, QMessageBox, QCheckBox, QSpinBox,
    )
    from PyQt6.QtGui import QShortcut, QKeySequence, QFont, QIcon, QAction, QDrag, QCursor
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QUrl, QMimeData, QTimer
    HAS_TRAY = True

from search_engine import SearchEngine
from audio_engine import AudioPlayer
from waveform_widget import WaveformWidget


class ScanWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal()

    def __init__(self, search_engine, folder_path, reindex=False):
        super().__init__()
        self.search_engine = search_engine
        self.folder_path = folder_path
        self.reindex = reindex

    def run(self):
        if self.reindex:
            self.search_engine.reindex_folder(self.folder_path, progress_callback=self.on_progress)
        else:
            self.search_engine.scan_folder(self.folder_path, progress_callback=self.on_progress)
        self.finished.emit()

    def on_progress(self, current, total, filename):
        self.progress.emit(current, total, filename)


class ModelLoaderWorker(QThread):
    loaded = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, search_engine):
        super().__init__()
        self.search_engine = search_engine

    def run(self):
        try:
            self.search_engine.load_models()
            self.loaded.emit()
        except Exception as e:
            self.error.emit(str(e))


class DragHandle(QLabel):
    def __init__(self, text="  DRAG FILE  ", parent=None):
        super().__init__(text, parent)
        self.parent_app = parent
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setEnabled(False)
        self.setStyleSheet("""
            QLabel {
                background-color: #21262D;
                border: 1px solid #30363D;
                border-radius: 4px;
                color: #8B949E;
                font-weight: bold;
                padding: 6px;
            }
            QLabel:hover {
                background-color: #30363D;
                color: #58A6FF;
                border-color: #58A6FF;
            }
            QLabel:disabled {
                background-color: #0D1117;
                color: #484F58;
                border-color: #21262D;
            }
        """)

    def set_active(self, active=True):
        self.setEnabled(active)
        self.setToolTip("Click and drag to copy file to DAW / Explorer" if active else "")

    def mousePressEvent(self, event):
        if self.isEnabled() and event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mouseMoveEvent(self, event):
        if self.isEnabled() and event.buttons() & Qt.MouseButton.LeftButton:
            if self.parent_app:
                self.parent_app.initiate_drag()


class SoundIQApp(QMainWindow):
    audio_loaded = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.settings = AppSettings()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.audio_loaded.connect(self._on_audio_loaded)

        w = self.settings.get("window", "width", default=1280)
        h = self.settings.get("window", "height", default=860)
        self.resize(w, h)

        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "soundiq_logo.ico")
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))

        self.db_path = self.settings.db_path
        self.search_engine = SearchEngine(self.db_path)
        self.audio_player = AudioPlayer()

        self.current_file_path = None
        self.model_loaded = False
        self.model_loading = False
        self.results_data = []

        self.init_ui()
        self.apply_theme()
        self._setup_shortcuts()
        self._setup_tray()

        self.audio_player.position_changed.connect(self.on_playback_position_changed)
        self.audio_player.playback_finished.connect(self.on_playback_finished)

        saved_vol = self.settings.get("audio", "volume", default=80)
        saved_speed = self.settings.get("audio", "speed", default=100)
        saved_loop = self.settings.get("audio", "loop", default=False)
        self.volume_slider.setValue(saved_vol)
        self.speed_slider.setValue(saved_speed)
        self.btn_loop.setChecked(saved_loop)
        self.audio_player.set_volume(saved_vol / 100.0)
        self.audio_player.set_speed(saved_speed / 100.0)
        self.audio_player.loop = saved_loop

        self.update_folder_list()
        self.load_ai_model_async()
        self.run_search()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(10)

        lib_label = QLabel("LOCAL LIBRARIES")
        lib_label.setStyleSheet("font-weight: bold; color: #8B949E; font-size: 10px; letter-spacing: 1px;")
        sidebar_layout.addWidget(lib_label)

        self.folder_list_widget = QListWidget()
        self.folder_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.folder_list_widget.customContextMenuRequested.connect(self.show_folder_context_menu)
        self.folder_list_widget.itemClicked.connect(self.on_folder_item_clicked)
        sidebar_layout.addWidget(self.folder_list_widget)

        folder_btns = QHBoxLayout()
        self.btn_add_folder = QPushButton("+ Add Folder")
        self.btn_add_folder.clicked.connect(self.add_folder_dialog)
        folder_btns.addWidget(self.btn_add_folder)
        self.btn_reindex = QPushButton("Reindex")
        self.btn_reindex.setToolTip("Reindex selected folder")
        self.btn_reindex.clicked.connect(self.reindex_selected_folder)
        self.btn_reindex.setEnabled(False)
        folder_btns.addWidget(self.btn_reindex)
        sidebar_layout.addLayout(folder_btns)

        hist_label = QLabel("SEARCH HISTORY")
        hist_label.setStyleSheet("font-weight: bold; color: #8B949E; font-size: 10px; letter-spacing: 1px;")
        sidebar_layout.addWidget(hist_label)

        self.history_list_widget = QListWidget()
        self.history_list_widget.itemClicked.connect(self.on_history_item_clicked)
        sidebar_layout.addWidget(self.history_list_widget)

        sidebar.setMinimumWidth(220)
        sidebar.setMaximumWidth(350)
        splitter.addWidget(sidebar)

        main_content = QWidget()
        main_content_layout = QVBoxLayout(main_content)
        main_content_layout.setContentsMargins(10, 10, 10, 10)
        main_content_layout.setSpacing(10)
        splitter.addWidget(main_content)

        search_row = QHBoxLayout()
        main_content_layout.addLayout(search_row)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Loading search engine...")
        self.search_input.returnPressed.connect(self.run_search)
        search_row.addWidget(self.search_input)

        self.btn_search = QPushButton("Search")
        self.btn_search.clicked.connect(self.run_search)
        search_row.addWidget(self.btn_search)

        self.lbl_results_count = QLabel("")
        self.lbl_results_count.setStyleSheet("color: #8B949E; font-size: 11px;")
        search_row.addWidget(self.lbl_results_count)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(15)
        main_content_layout.addWidget(self.progress_bar)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(6)
        self.results_table.setHorizontalHeaderLabels(["Name", "Duration", "Sample Rate", "Channels", "Size", "Score"])
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.setDragEnabled(True)
        self.results_table.itemDoubleClicked.connect(self.on_table_double_clicked)
        self.results_table.itemSelectionChanged.connect(self.on_table_selection_changed)

        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        main_content_layout.addWidget(self.results_table)

        player_panel = QWidget()
        player_panel.setStyleSheet("background-color: #161B22; border-top: 1px solid #21262D;")
        player_panel_layout = QVBoxLayout(player_panel)
        player_panel_layout.setContentsMargins(15, 10, 15, 10)
        player_panel_layout.setSpacing(8)
        main_layout.addWidget(player_panel)

        self.waveform_widget = WaveformWidget(self)
        self.waveform_widget.seek_requested.connect(self.on_waveform_seek_requested)
        self.waveform_widget.selection_changed.connect(self.on_waveform_selection_changed)
        self.waveform_widget.selection_cleared.connect(self.on_waveform_selection_cleared)
        self.waveform_widget.drag_started.connect(self.initiate_drag)
        player_panel_layout.addWidget(self.waveform_widget)

        zoom_row = QHBoxLayout()
        zoom_row.setContentsMargins(0, 0, 0, 0)
        self.btn_zoom_in = QToolButton()
        self.btn_zoom_in.setText("+")
        self.btn_zoom_in.setFixedSize(24, 24)
        self.btn_zoom_in.clicked.connect(self.waveform_widget.zoom_in)
        zoom_row.addWidget(self.btn_zoom_in)
        self.btn_zoom_out = QToolButton()
        self.btn_zoom_out.setText("-")
        self.btn_zoom_out.setFixedSize(24, 24)
        self.btn_zoom_out.clicked.connect(self.waveform_widget.zoom_out)
        zoom_row.addWidget(self.btn_zoom_out)
        self.btn_zoom_fit = QToolButton()
        self.btn_zoom_fit.setText("Fit")
        self.btn_zoom_fit.setFixedSize(36, 24)
        self.btn_zoom_fit.clicked.connect(self.waveform_widget.zoom_fit)
        zoom_row.addWidget(self.btn_zoom_fit)
        self.btn_zoom_sel = QToolButton()
        self.btn_zoom_sel.setText("Zoom Sel")
        self.btn_zoom_sel.setFixedSize(60, 24)
        self.btn_zoom_sel.clicked.connect(self.waveform_widget.zoom_to_selection)
        zoom_row.addWidget(self.btn_zoom_sel)
        zoom_row.addStretch()
        player_panel_layout.addLayout(zoom_row)

        controls_layout = QHBoxLayout()
        player_panel_layout.addLayout(controls_layout)

        self.btn_play_pause = QPushButton("Play")
        self.btn_play_pause.setFixedWidth(75)
        self.btn_play_pause.clicked.connect(self.toggle_play_pause)
        controls_layout.addWidget(self.btn_play_pause)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setFixedWidth(65)
        self.btn_stop.clicked.connect(self.stop_playback)
        controls_layout.addWidget(self.btn_stop)

        self.btn_loop = QPushButton("Loop")
        self.btn_loop.setCheckable(True)
        self.btn_loop.setFixedWidth(65)
        self.btn_loop.clicked.connect(self.toggle_loop)
        controls_layout.addWidget(self.btn_loop)

        controls_layout.addWidget(QLabel("Vol:"))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        controls_layout.addWidget(self.volume_slider)

        controls_layout.addSpacing(15)

        controls_layout.addWidget(QLabel("Speed:"))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(50, 200)
        self.speed_slider.setValue(100)
        self.speed_slider.setFixedWidth(100)
        self.speed_slider.valueChanged.connect(self.on_speed_changed)
        controls_layout.addWidget(self.speed_slider)

        self.lbl_speed_val = QLabel("1.00x")
        self.lbl_speed_val.setFixedWidth(40)
        controls_layout.addWidget(self.lbl_speed_val)

        self.btn_reset_speed = QPushButton("Reset")
        self.btn_reset_speed.setFixedWidth(50)
        self.btn_reset_speed.clicked.connect(self.reset_speed)
        controls_layout.addWidget(self.btn_reset_speed)

        controls_layout.addStretch()

        self.lbl_sound_info = QLabel("No file selected")
        self.lbl_sound_info.setStyleSheet("color: #8B949E; font-size: 11px;")
        controls_layout.addWidget(self.lbl_sound_info)

        controls_layout.addSpacing(15)

        self.btn_clear_sel = QPushButton("Clear Sel")
        self.btn_clear_sel.setVisible(False)
        self.btn_clear_sel.clicked.connect(self.waveform_widget.clear_selection)
        controls_layout.addWidget(self.btn_clear_sel)

        self.btn_trim = QPushButton("Trim & Save")
        self.btn_trim.setToolTip("Save selection to file (Ctrl+T)")
        self.btn_trim.setVisible(False)
        self.btn_trim.clicked.connect(self.trim_selection)
        controls_layout.addWidget(self.btn_trim)

        self.drag_handle = DragHandle("DRAG", self)
        controls_layout.addWidget(self.drag_handle)

    def apply_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #0D1117; }
            QWidget { color: #C9D1D9; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; }
            QSplitter::handle { background-color: #21262D; }
            QLineEdit {
                background-color: #161B22; border: 1px solid #30363D; border-radius: 6px;
                padding: 8px 12px; color: #C9D1D9; font-size: 13px;
            }
            QLineEdit:focus { border-color: #58A6FF; }
            QPushButton {
                background-color: #21262D; border: 1px solid #30363D; border-radius: 6px;
                padding: 6px 12px; color: #C9D1D9;
            }
            QPushButton:hover { background-color: #30363D; border-color: #8B949E; }
            QPushButton:pressed { background-color: #0D1117; }
            QPushButton:checked { background-color: #1F6FEB; border-color: #58A6FF; color: #FFFFFF; }
            QPushButton:disabled { color: #484F58; }
            QToolButton {
                background-color: #21262D; border: 1px solid #30363D; border-radius: 4px;
                color: #8B949E; font-size: 11px;
            }
            QToolButton:hover { background-color: #30363D; color: #C9D1D9; }
            QTableWidget {
                background-color: #0D1117; border: 1px solid #21262D; gridline-color: #161B22;
                border-radius: 6px; selection-background-color: #1f2937; selection-color: #00E5FF;
            }
            QHeaderView::section {
                background-color: #161B22; color: #8B949E; padding: 8px;
                border: none; border-bottom: 1px solid #30363D; font-weight: bold;
            }
            QListWidget {
                background-color: #161B22; border: 1px solid #21262D; border-radius: 6px; padding: 4px;
            }
            QListWidget::item { padding: 6px 8px; border-radius: 4px; }
            QListWidget::item:hover { background-color: #21262D; }
            QListWidget::item:selected { background-color: #1F6FEB; color: #FFFFFF; }
            QSlider::groove:horizontal {
                border: 1px solid #21262D; height: 4px; background: #30363D; border-radius: 2px;
            }
            QSlider::handle:horizontal { background: #58A6FF; width: 12px; margin: -4px 0; border-radius: 6px; }
            QSlider::handle:horizontal:hover { background: #00E5FF; }
            QProgressBar {
                border: 1px solid #30363D; border-radius: 4px; background-color: #161B22;
                text-align: center; color: white; font-size: 10px;
            }
            QProgressBar::chunk { background-color: #1F6FEB; border-radius: 3px; }
            QMenu {
                background-color: #161B22; border: 1px solid #30363D; color: #C9D1D9; padding: 4px;
            }
            QMenu::item { padding: 6px 20px; border-radius: 4px; }
            QMenu::item:selected { background-color: #1F6FEB; color: #FFFFFF; }
            QStatusBar { color: #8B949E; font-size: 11px; }
            QSpinBox {
                background-color: #161B22; border: 1px solid #30363D; border-radius: 4px;
                color: #C9D1D9; padding: 2px 6px;
            }
        """)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence(Qt.Key.Key_Space), self).activated.connect(self.toggle_play_pause)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self).activated.connect(self.stop_playback)
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_T), self).activated.connect(self.trim_selection)
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_F), self).activated.connect(self._focus_search)
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_O), self).activated.connect(self.add_folder_dialog)
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self).activated.connect(self._delete_selected)
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_1), self).activated.connect(self.waveform_widget.zoom_fit)
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_Equal), self).activated.connect(self.waveform_widget.zoom_in)
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_Minus), self).activated.connect(self.waveform_widget.zoom_out)
        QShortcut(QKeySequence(Qt.Key.Key_Up), self).activated.connect(lambda: self._navigate_table(-1))
        QShortcut(QKeySequence(Qt.Key.Key_Down), self).activated.connect(lambda: self._navigate_table(1))

    def _setup_tray(self):
        if not HAS_TRAY or not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        tray_menu = QMenu()
        show_action = tray_menu.addAction("Show")
        show_action.triggered.connect(self._show_from_tray)
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(self._quit_app)
        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.setToolTip(APP_NAME)
        self.tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_from_tray()

    def _show_from_tray(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _quit_app(self):
        self.audio_player.cleanup()
        if hasattr(self, "tray"):
            self.tray.hide()
        QApplication.quit()

    def _focus_search(self):
        self.search_input.setFocus()
        self.search_input.selectAll()

    def _navigate_table(self, direction):
        rows = self.results_table.rowCount()
        if rows == 0:
            return
        current = self.results_table.currentRow()
        new_row = max(0, min(rows - 1, current + direction))
        self.results_table.selectRow(new_row)

    def _delete_selected(self):
        selected = self.results_table.selectedItems()
        if not selected:
            return
        rows = set(item.row() for item in selected)
        self.statusBar().showMessage(f"Selected {len(rows)} file(s) for deletion (use right-click to remove from library)")

    def load_ai_model_async(self):
        self.search_input.setEnabled(False)
        self.search_input.setPlaceholderText("Loading AI Search engine...")

        self.model_progress = QProgressBar()
        self.model_progress.setMaximum(0)
        self.model_progress.setFixedWidth(200)
        self.model_progress.setFixedHeight(16)
        self.model_progress.setFormat(" Loading model...")
        self.statusBar().addPermanentWidget(self.model_progress)

        self.model_loader = ModelLoaderWorker(self.search_engine)
        self.model_loader.loaded.connect(self.on_model_loaded)
        self.model_loader.error.connect(self.on_model_load_error)
        self.model_loader.start()
        self.model_loading = True

    def on_model_loaded(self):
        self.model_loaded = True
        self.model_loading = False
        self.search_input.setEnabled(True)
        self.search_input.setPlaceholderText("Describe the audio type to search...")
        self.statusBar().showMessage("AI Search engine ready.", 5000)
        if hasattr(self, "model_progress"):
            self.statusBar().removeWidget(self.model_progress)
            self.model_progress.deleteLater()
        self._update_stats()

    def on_model_load_error(self, err_msg):
        self.model_loading = False
        self.search_input.setEnabled(True)
        self.search_input.setPlaceholderText("AI Search unavailable. Check console.")
        self.statusBar().showMessage(f"AI Search error: {err_msg}", 10000)
        if hasattr(self, "model_progress"):
            self.statusBar().removeWidget(self.model_progress)
            self.model_progress.deleteLater()

    def _update_stats(self):
        try:
            total = self.search_engine.get_total_sounds()
            folders = self.search_engine.get_total_folders()
            self.lbl_results_count.setText(f"{total} sounds in {folders} folders")
        except Exception:
            pass

    def run_search(self):
        query = self.search_input.text()

        if query.strip():
            self.settings.add_search_history(query.strip())
            self._refresh_history_ui()

        if not self.model_loaded:
            self.statusBar().showMessage("AI Search engine still loading...", 3000)
            return

        self.statusBar().showMessage("Searching...")
        QApplication.processEvents()

        try:
            if query.strip():
                results = self.search_engine.search_ai(query)
            else:
                results = self.search_engine.search_keyword("")
        except Exception as e:
            logger.error(f"Search error: {e}")
            results = []

        self.display_results(results)
        self.statusBar().showMessage(f"Found {len(results)} results", 3000)

    def display_results(self, results):
        self.results_table.setRowCount(0)
        self.results_data = results

        has_score = len(results) > 0 and len(results[0]) > 6
        if has_score:
            self.results_table.setColumnCount(6)
            self.results_table.setHorizontalHeaderLabels(["Name", "Duration", "Sample Rate", "Channels", "Size", "Score"])
        else:
            self.results_table.setColumnCount(5)
            self.results_table.setHorizontalHeaderLabels(["Name", "Duration", "Sample Rate", "Channels", "Size"])

        for row_idx, row_data in enumerate(results):
            path, filename, duration, sr, channels, size = row_data[:6]
            dur_str = f"{duration:.2f}s"
            sr_str = f"{sr / 1000:.1f} kHz"
            ch_str = "Stereo" if channels == 2 else ("Mono" if channels == 1 else f"{channels} Ch")
            size_mb = size / (1024 * 1024)
            size_str = f"{size_mb:.2f} MB" if size_mb >= 0.1 else f"{size / 1024:.0f} KB"

            self.results_table.insertRow(row_idx)
            item_name = QTableWidgetItem(filename)
            item_name.setToolTip(path)
            self.results_table.setItem(row_idx, 0, item_name)
            self.results_table.setItem(row_idx, 1, QTableWidgetItem(dur_str))
            self.results_table.setItem(row_idx, 2, QTableWidgetItem(sr_str))
            self.results_table.setItem(row_idx, 3, QTableWidgetItem(ch_str))
            self.results_table.setItem(row_idx, 4, QTableWidgetItem(size_str))

            if has_score and len(row_data) > 6:
                score = row_data[6]
                score_str = f"{score:.3f}"
                item_score = QTableWidgetItem(score_str)
                item_score.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.results_table.setItem(row_idx, 5, item_score)

        self.lbl_results_count.setText(f"{len(results)} result(s)")

    def add_folder_dialog(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Folder to Add to Library")
        if dir_path:
            self._start_scan(dir_path, reindex=False)

    def reindex_selected_folder(self):
        items = self.folder_list_widget.selectedItems()
        if not items:
            self.statusBar().showMessage("Select a folder in the sidebar first.", 3000)
            return
        folder_path = items[0].toolTip()
        self._start_scan(folder_path, reindex=True)

    def _start_scan(self, folder_path, reindex=False):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        action = "Reindexing" if reindex else "Scanning"
        self.statusBar().showMessage(f"{action}: {folder_path}...")

        self.scan_worker = ScanWorker(self.search_engine, folder_path, reindex=reindex)
        self.scan_worker.progress.connect(self.on_scan_progress)
        self.scan_worker.finished.connect(self.on_scan_finished)
        self.scan_worker.start()

    def on_scan_progress(self, current, total, filename):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_bar.setFormat(f"Files: {current}/{total} - {filename[:40]}...")

    def on_scan_finished(self):
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("Scan complete.", 5000)
        self.update_folder_list()
        self.run_search()
        self._update_stats()

    def update_folder_list(self):
        self.folder_list_widget.clear()
        folders = self.search_engine.get_all_folders()
        for folder in folders:
            item = QListWidgetItem(os.path.basename(folder))
            item.setToolTip(folder)
            item.setData(Qt.ItemDataRole.UserRole, folder)
            self.folder_list_widget.addItem(item)

    def on_folder_item_clicked(self, item):
        folder_path = item.toolTip()
        results = self.search_engine.get_sounds_in_folder(folder_path)
        self.display_results(results)
        self.btn_reindex.setEnabled(True)
        self.statusBar().showMessage(f"Showing {len(results)} files in: {folder_path}")

    def show_folder_context_menu(self, pos):
        item = self.folder_list_widget.itemAt(pos)
        if item is None:
            return
        menu = QMenu()
        reindex_action = menu.addAction("Reindex Folder")
        reindex_action.triggered.connect(lambda: self._start_scan(item.toolTip(), reindex=True))
        remove_action = menu.addAction("Remove from Library")
        remove_action.triggered.connect(lambda: self.remove_folder(item.toolTip()))
        menu.exec(self.folder_list_widget.mapToGlobal(pos))

    def remove_folder(self, folder_path):
        self.search_engine.remove_folder(folder_path)
        self.statusBar().showMessage(f"Removed: {folder_path}", 4000)
        self.update_folder_list()
        self.run_search()
        self._update_stats()

    def _refresh_history_ui(self):
        self.history_list_widget.clear()
        for query in self.settings.get_search_history():
            self.history_list_widget.addItem(query)

    def on_history_item_clicked(self, item):
        self.search_input.setText(item.text())
        self.run_search()

    def on_table_selection_changed(self):
        selected_rows = self.results_table.selectedItems()
        if not selected_rows:
            return

        row = selected_rows[0].row()
        if row >= len(self.results_data):
            return
        sound_data = self.results_data[row]
        file_path = sound_data[0]

        threading.Thread(target=self.load_audio_file, args=(file_path,), daemon=True).start()

    def on_table_double_clicked(self, item):
        row = item.row()
        if row >= len(self.results_data):
            return
        sound_data = self.results_data[row]
        file_path = sound_data[0]

        if self.load_audio_file(file_path):
            self.audio_player.play()
            self.btn_play_pause.setText("Pause")

    def load_audio_file(self, file_path):
        if self.current_file_path == file_path:
            return True
        self.audio_player.stop()
        success = self.audio_player.load(file_path)
        if success:
            self.audio_loaded.emit(file_path)
            return True
        else:
            self.audio_loaded.emit("")
            return False

    def _on_audio_loaded(self, file_path):
        if not file_path:
            self.current_file_path = None
            self.lbl_sound_info.setText("Error loading file")
            self.waveform_widget.clear()
            self.drag_handle.set_active(False)
            return
        self.current_file_path = file_path
        filename = os.path.basename(file_path)
        dur = self.audio_player.get_duration()
        self.lbl_sound_info.setText(f"{filename} | {dur:.2f}s | {self.audio_player.samplerate}Hz")
        self.waveform_widget.sr = self.audio_player.samplerate
        self.waveform_widget.set_audio_data(self.audio_player.data, dur)
        self.drag_handle.set_active(True)
        self.audio_player.play()
        self.btn_play_pause.setText("Pause")

    def toggle_play_pause(self):
        if self.audio_player.is_playing:
            self.audio_player.pause()
            self.btn_play_pause.setText("Play")
        else:
            self.audio_player.play()
            self.btn_play_pause.setText("Pause")

    def stop_playback(self):
        self.audio_player.stop()
        self.btn_play_pause.setText("Play")

    def toggle_loop(self):
        self.audio_player.loop = self.btn_loop.isChecked()
        self.settings.set("audio", "loop", self.btn_loop.isChecked())

    def on_volume_changed(self, val):
        self.audio_player.set_volume(val / 100.0)
        self.settings.set("audio", "volume", val)

    def on_speed_changed(self, val):
        speed = val / 100.0
        self.audio_player.set_speed(speed)
        self.lbl_speed_val.setText(f"{speed:.2f}x")
        self.settings.set("audio", "speed", val)

    def reset_speed(self):
        self.speed_slider.setValue(100)
        self.audio_player.set_speed(1.0)
        self.lbl_speed_val.setText("1.00x")

    def on_playback_position_changed(self, pos):
        self.waveform_widget.set_playhead_position(pos)

    def on_playback_finished(self):
        self.btn_play_pause.setText("Play")

    def on_waveform_seek_requested(self, seconds):
        self.audio_player.set_position(seconds)

    def on_waveform_selection_changed(self, start_sec, end_sec):
        self.audio_player.set_selection(start_sec, end_sec)
        self.btn_clear_sel.setVisible(True)
        self.btn_trim.setVisible(True)

    def on_waveform_selection_cleared(self):
        self.audio_player.clear_selection()
        self.btn_clear_sel.setVisible(False)
        self.btn_trim.setVisible(False)

    def initiate_drag(self):
        if not self.current_file_path:
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        sel = self.waveform_widget.get_selection()

        if sel:
            temp_dir = tempfile.gettempdir()
            filename_orig = os.path.basename(self.current_file_path)
            name_part, ext = os.path.splitext(filename_orig)
            temp_file_name = f"{name_part}_selection.wav"
            temp_path = os.path.join(temp_dir, temp_file_name)

            success = self.audio_player.crop_selection_to_file(temp_path)
            drag_file_path = temp_path if success else self.current_file_path
        else:
            drag_file_path = self.current_file_path

        mime_data.setUrls([QUrl.fromLocalFile(drag_file_path)])
        drag.setMimeData(mime_data)

        self.statusBar().showMessage(f"Dragging: {os.path.basename(drag_file_path)}")
        drag.exec(Qt.DropAction.CopyAction)
        self.statusBar().showMessage("Drag completed", 3000)

    def trim_selection(self):
        if not self.current_file_path:
            return

        sel = self.waveform_widget.get_selection()
        if not sel:
            self.statusBar().showMessage("No selection to trim.", 3000)
            return

        dir_orig = os.path.dirname(self.current_file_path)
        filename_orig = os.path.basename(self.current_file_path)
        name_part, ext = os.path.splitext(filename_orig)
        default_save_path = os.path.join(dir_orig, f"{name_part}_trimmed.wav")

        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Trimmed Selection", default_save_path,
            "WAV Files (*.wav);;FLAC Files (*.flac);;All Files (*)"
        )

        if save_path:
            success = self.audio_player.crop_selection_to_file(save_path)
            if success:
                self.statusBar().showMessage(f"Saved: {os.path.basename(save_path)}", 5000)
            else:
                self.statusBar().showMessage("Failed to save trimmed selection.", 5000)

    def closeEvent(self, event):
        self.settings.set("window", "width", self.width())
        self.settings.set("window", "height", self.height())
        self.audio_player.cleanup()
        if hasattr(self, "tray"):
            self.tray.hide()
        super().closeEvent(event)

    def changeEvent(self, event):
        if event.type() == event.Type.WindowStateChange:
            if self.isMinimized() and HAS_TRAY and hasattr(self, "tray"):
                self.hide()
                self.tray.showMessage(
                    APP_NAME,
                    "Running in system tray. Double-click to restore.",
                    QSystemTrayIcon.MessageIcon.Information,
                    2000,
                )
        super().changeEvent(event)


def main():
    import ctypes
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SoundIQ.2")
    except Exception:
        pass

    try:
        import torch
        torch.set_num_threads(os.cpu_count())
        if torch.cuda.is_available():
            torch.backends.cudnn.benchmark = True
            torch.backends.cuda.matmul.allow_tf32 = True
    except ImportError:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    ico_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "soundiq_logo.ico")
    if os.path.exists(ico_path):
        app_icon = QIcon(ico_path)
        app.setWindowIcon(app_icon)

    settings = AppSettings()
    show_splash = settings.get("ui", "show_splash", default=True)

    def launch_main():
        window = SoundIQApp()
        window.show()
        settings.set("ui", "show_splash", False)

    if show_splash:
        try:
            from splash import show_splash as _show_splash
            _show_splash(launch_main)
        except Exception:
            launch_main()
    else:
        launch_main()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
