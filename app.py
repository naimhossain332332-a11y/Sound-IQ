import sys
import os
import tempfile
import threading
import traceback
from pathlib import Path
import soundfile as sf

# Dynamic import of PySide6 or PyQt6
try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QSplitter, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
        QHeaderView, QFileDialog, QLabel, QSlider, QProgressBar,
        QListWidget, QListWidgetItem, QMenu, QAbstractItemView, QStatusBar,
        QMessageBox, QDialog, QSpinBox, QComboBox
    )
    from PySide6.QtGui import QShortcut, QKeySequence
    from PySide6.QtGui import QFont, QIcon, QAction, QDrag, QCursor
    from PySide6.QtCore import Qt, QThread, Signal as pyqtSignal, QSize, QUrl, QMimeData, QTimer, QEvent
except ImportError:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QSplitter, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
        QHeaderView, QFileDialog, QLabel, QSlider, QProgressBar,
        QListWidget, QListWidgetItem, QMenu, QAbstractItemView, QStatusBar,
        QMessageBox, QDialog, QSpinBox, QComboBox
    )
    from PyQt6.QtGui import QShortcut, QKeySequence
    from PyQt6.QtGui import QFont, QIcon, QAction, QDrag, QCursor
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QUrl, QMimeData, QTimer, QEvent

from search_engine import SearchEngine
from audio_engine import AudioPlayer
from waveform_widget import WaveformWidget

# Worker thread for folder scanning with progress
class ScanWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, search_engine, folder_path):
        super().__init__()
        self.search_engine = search_engine
        self.folder_path = folder_path

    def run(self):
        try:
            self.search_engine.scan_folder(self.folder_path, progress_callback=self.on_progress)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

    def on_progress(self, current, total, filename):
        self.progress.emit(current, total, filename)

# Worker thread for lazy loading AI models (non-blocking)
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
            traceback.print_exc()

# Custom drag handle widget
class DragHandle(QLabel):
    def __init__(self, text="📄 DRAG FILE", parent=None):
        super().__init__(text, parent)
        self.parent_app = parent
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setEnabled(False)
        self.setStyleSheet("""
            QLabel {
                background-color: #1e293b;
                border: 2px solid #3b82f6;
                border-radius: 6px;
                color: #e2e8f0;
                font-weight: bold;
                padding: 8px;
            }
            QLabel:hover {
                background-color: #334155;
                border-color: #60a5fa;
            }
            QLabel:disabled {
                background-color: #0f172a;
                color: #64748b;
                border-color: #1e293b;
            }
        """)

    def set_active(self, active=True):
        self.setEnabled(active)
        self.setToolTip("Drag file to DAW/Explorer" if active else "")

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
        self.setWindowTitle("Sound IQ v2.0 🎵")
        self.setGeometry(100, 100, 1400, 900)
        
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "soundiq_logo.ico")
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))
        
        self.audio_loaded.connect(self._on_audio_loaded)
        
        # Initialize database path
        self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.db")
        self.search_engine = SearchEngine(self.db_path)
        self.audio_player = AudioPlayer()
        
        # State
        self.current_file_path = None
        self.search_history = []
        self.model_loaded = False
        self.model_loading = False
        self.results_data = []
        
        # Init GUI immediately (fast)
        self.init_ui()
        self.apply_theme()
        
        # Connect audio signals
        self.audio_player.position_changed.connect(self.on_playback_position_changed)
        self.audio_player.playback_finished.connect(self.on_playback_finished)
        
        # Setup keyboard shortcuts
        self.setup_shortcuts()
        
        # Load folder list
        self.update_folder_list()
        
        # Start model loading in background (non-blocking)
        self.load_ai_model_async()
        
        # Show initial empty results
        self.statusBar().showMessage("Ready! Add folders and search...")

    def init_ui(self):
        """Create the main UI layout"""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Splitter: Sidebar + Main Content
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # ===== SIDEBAR =====
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 12, 12, 12)
        sidebar_layout.setSpacing(12)
        
        # Library section
        lib_label = QLabel("📁 LOCAL LIBRARIES")
        lib_label.setStyleSheet("font-weight: bold; color: #64748b; font-size: 11px; letter-spacing: 1px;")
        sidebar_layout.addWidget(lib_label)
        
        self.folder_list_widget = QListWidget()
        self.folder_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.folder_list_widget.customContextMenuRequested.connect(self.show_folder_context_menu)
        self.folder_list_widget.itemClicked.connect(self.on_folder_item_clicked)
        sidebar_layout.addWidget(self.folder_list_widget)
        
        add_folder_btn = QPushButton("+ Add Folder")
        add_folder_btn.clicked.connect(self.add_folder_dialog)
        sidebar_layout.addWidget(add_folder_btn)
        
        # Search History section
        hist_label = QLabel("🕐 SEARCH HISTORY")
        hist_label.setStyleSheet("font-weight: bold; color: #64748b; font-size: 11px; letter-spacing: 1px; margin-top: 12px;")
        sidebar_layout.addWidget(hist_label)
        
        self.history_list_widget = QListWidget()
        self.history_list_widget.itemClicked.connect(self.on_history_item_clicked)
        sidebar_layout.addWidget(self.history_list_widget)
        
        sidebar.setMinimumWidth(240)
        sidebar.setMaximumWidth(380)
        splitter.addWidget(sidebar)
        
        # ===== MAIN CONTENT =====
        main_content = QWidget()
        main_content_layout = QVBoxLayout(main_content)
        main_content_layout.setContentsMargins(12, 12, 12, 12)
        main_content_layout.setSpacing(10)
        splitter.addWidget(main_content)
        
        # Search bar
        search_row = QHBoxLayout()
        main_content_layout.addLayout(search_row)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Describe audio to search...")
        self.search_input.returnPressed.connect(self.run_search)
        search_row.addWidget(self.search_input)
        
        self.btn_search = QPushButton("🔎 Search")
        self.btn_search.setFixedWidth(100)
        self.btn_search.clicked.connect(self.run_search)
        search_row.addWidget(self.btn_search)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(18)
        main_content_layout.addWidget(self.progress_bar)
        
        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels(["📄 Name", "⏱️ Duration", "📊 Sample Rate", "🔊 Channels", "💾 Size"])
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.itemDoubleClicked.connect(self.on_table_double_clicked)
        self.results_table.itemSelectionChanged.connect(self.on_table_selection_changed)
        
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 5):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        
        main_content_layout.addWidget(self.results_table)
        
        # ===== PLAYER PANEL =====
        player_panel = QWidget()
        player_panel.setStyleSheet("background-color: #0f172a; border-top: 1px solid #1e293b;")
        player_panel_layout = QVBoxLayout(player_panel)
        player_panel_layout.setContentsMargins(15, 10, 15, 10)
        player_panel_layout.setSpacing(10)
        main_layout.addWidget(player_panel)
        
        # Waveform
        self.waveform_widget = WaveformWidget(self)
        self.waveform_widget.seek_requested.connect(self.on_waveform_seek_requested)
        self.waveform_widget.selection_changed.connect(self.on_waveform_selection_changed)
        self.waveform_widget.selection_cleared.connect(self.on_waveform_selection_cleared)
        self.waveform_widget.drag_started.connect(self.initiate_drag)
        player_panel_layout.addWidget(self.waveform_widget)
        
        # Controls
        controls_layout = QHBoxLayout()
        player_panel_layout.addLayout(controls_layout)
        
        # Play controls
        self.btn_play_pause = QPushButton("▶ Play")
        self.btn_play_pause.setFixedWidth(80)
        self.btn_play_pause.clicked.connect(self.toggle_play_pause)
        controls_layout.addWidget(self.btn_play_pause)
        
        self.btn_stop = QPushButton("⏹ Stop")
        self.btn_stop.setFixedWidth(80)
        self.btn_stop.clicked.connect(self.stop_playback)
        controls_layout.addWidget(self.btn_stop)
        
        self.btn_loop = QPushButton("🔁 Loop")
        self.btn_loop.setCheckable(True)
        self.btn_loop.setFixedWidth(80)
        self.btn_loop.clicked.connect(self.toggle_loop)
        controls_layout.addWidget(self.btn_loop)
        
        # Volume
        controls_layout.addWidget(QLabel("🔊"))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedWidth(120)
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        controls_layout.addWidget(self.volume_slider)
        
        controls_layout.addSpacing(20)
        
        # Speed control
        controls_layout.addWidget(QLabel("⚡ Speed:"))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(50, 200)
        self.speed_slider.setValue(100)
        self.speed_slider.setFixedWidth(120)
        self.speed_slider.valueChanged.connect(self.on_speed_changed)
        controls_layout.addWidget(self.speed_slider)
        
        self.lbl_speed_val = QLabel("1.0x")
        self.lbl_speed_val.setFixedWidth(40)
        controls_layout.addWidget(self.lbl_speed_val)
        
        self.btn_reset_speed = QPushButton("Reset")
        self.btn_reset_speed.setFixedWidth(60)
        self.btn_reset_speed.clicked.connect(self.reset_speed)
        controls_layout.addWidget(self.btn_reset_speed)
        
        controls_layout.addStretch()
        
        # Info label
        self.lbl_sound_info = QLabel("No file selected")
        self.lbl_sound_info.setStyleSheet("color: #94a3b8; font-size: 11px;")
        controls_layout.addWidget(self.lbl_sound_info)
        
        controls_layout.addSpacing(20)
        
        # Selection buttons
        self.btn_clear_sel = QPushButton("Clear")
        self.btn_clear_sel.setFixedWidth(70)
        self.btn_clear_sel.setVisible(False)
        self.btn_clear_sel.clicked.connect(self.waveform_widget.clear_selection)
        controls_layout.addWidget(self.btn_clear_sel)
        
        self.btn_trim = QPushButton("✂️ Trim")
        self.btn_trim.setFixedWidth(70)
        self.btn_trim.setVisible(False)
        self.btn_trim.clicked.connect(self.trim_selection)
        controls_layout.addWidget(self.btn_trim)
        
        self.drag_handle = DragHandle("📄 DRAG", self)
        controls_layout.addWidget(self.drag_handle)

    def apply_theme(self):
        """Apply modern dark theme"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0f172a;
            }
            QWidget {
                color: #e2e8f0;
                font-family: 'Segoe UI', 'SF Pro Display', sans-serif;
                font-size: 11px;
            }
            QSplitter::handle {
                background-color: #1e293b;
                width: 2px;
            }
            QLineEdit {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px 12px;
                color: #e2e8f0;
                selection-background-color: #3b82f6;
            }
            QLineEdit:focus {
                border: 2px solid #3b82f6;
                padding: 7px 11px;
            }
            QPushButton {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 7px 14px;
                color: #e2e8f0;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #334155;
                border-color: #64748b;
            }
            QPushButton:pressed {
                background-color: #0f172a;
            }
            QPushButton:checked {
                background-color: #3b82f6;
                border-color: #60a5fa;
                color: #ffffff;
            }
            QTableWidget {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                gridline-color: #1e293b;
                border-radius: 4px;
            }
            QTableWidget::item:selected {
                background-color: #3b82f6;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #1e293b;
                color: #94a3b8;
                padding: 8px;
                border: none;
                border-right: 1px solid #334155;
                font-weight: bold;
            }
            QListWidget {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #334155;
            }
            QListWidget::item:selected {
                background-color: #3b82f6;
                color: #ffffff;
            }
            QSlider::groove:horizontal {
                border: 1px solid #334155;
                height: 5px;
                background: #1e293b;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #3b82f6;
                width: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #60a5fa;
            }
            QProgressBar {
                border: 1px solid #334155;
                border-radius: 4px;
                background-color: #1e293b;
                text-align: center;
                color: #e2e8f0;
                font-size: 10px;
            }
            QProgressBar::chunk {
                background-color: #3b82f6;
                border-radius: 3px;
            }
            QStatusBar {
                background-color: #1e293b;
                color: #94a3b8;
                border-top: 1px solid #334155;
            }
            QLabel {
                color: #e2e8f0;
            }
        """)

    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        QShortcut(QKeySequence(Qt.Key.Key_Space), self).activated.connect(self.toggle_play_pause)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self).activated.connect(self.stop_playback)
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_T), self).activated.connect(self.trim_selection)
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_L), self).activated.connect(self.add_folder_dialog)

    def load_ai_model_async(self):
        """Load CLAP model in background thread"""
        self.search_input.setEnabled(False)
        self.search_input.setPlaceholderText("🔄 Loading AI model...")
        
        self.model_progress = QProgressBar()
        self.model_progress.setMaximum(0)
        self.model_progress.setFixedWidth(200)
        self.model_progress.setFormat(" Loading CLAP model...")
        self.statusBar().addPermanentWidget(self.model_progress)
        
        self.model_loader = ModelLoaderWorker(self.search_engine)
        self.model_loader.loaded.connect(self.on_model_loaded)
        self.model_loader.error.connect(self.on_model_load_error)
        self.model_loader.start()
        self.model_loading = True

    def on_model_loaded(self):
        """Model loaded successfully"""
        self.model_loaded = True
        self.model_loading = False
        self.search_input.setEnabled(True)
        self.search_input.setPlaceholderText("🔍 Describe audio to search...")
        self.statusBar().showMessage("✅ AI Search ready!", 3000)
        if hasattr(self, 'model_progress'):
            self.statusBar().removeWidget(self.model_progress)
            self.model_progress.deleteLater()

    def on_model_load_error(self, err_msg):
        """Model loading failed"""
        self.model_loading = False
        self.search_input.setEnabled(True)
        self.search_input.setPlaceholderText("❌ Keyword search only")
        self.statusBar().showMessage(f"⚠️ AI Search unavailable: {err_msg}", 5000)
        if hasattr(self, 'model_progress'):
            self.statusBar().removeWidget(self.model_progress)
            self.model_progress.deleteLater()

    def run_search(self):
        """Execute search query"""
        query = self.search_input.text().strip()
        
        if query and query not in self.search_history:
            self.search_history.insert(0, query)
            self.search_history = self.search_history[:20]
            self.update_history_ui()
        
        if not query:
            self.results_table.setRowCount(0)
            return
        
        if self.model_loading:
            self.statusBar().showMessage("⏳ AI model still loading...")
            return
        
        self.statusBar().showMessage("🔍 Searching...")
        
        # Use AI search if model is loaded, else keyword search
        if self.model_loaded:
            results = self.search_engine.search_ai(query)
        else:
            results = self.search_engine.search_keyword(query)
        
        self.display_results(results)
        self.statusBar().showMessage(f"✅ Found {len(results)} results", 3000)

    def display_results(self, results):
        """Display search results in table"""
        self.results_table.setRowCount(0)
        self.results_data = results
        
        for row_idx, row_data in enumerate(results):
            path, filename, duration, sr, channels, size = row_data[:6]
            
            dur_str = f"{duration:.2f}s"
            sr_str = f"{sr / 1000:.1f}kHz"
            ch_str = "Stereo" if channels == 2 else ("Mono" if channels == 1 else f"{channels}Ch")
            size_mb = size / (1024 * 1024)
            size_str = f"{size_mb:.1f}MB" if size_mb >= 0.1 else f"{size / 1024:.0f}KB"
            
            self.results_table.insertRow(row_idx)
            
            item_name = QTableWidgetItem(filename)
            item_name.setToolTip(path)
            
            self.results_table.setItem(row_idx, 0, item_name)
            self.results_table.setItem(row_idx, 1, QTableWidgetItem(dur_str))
            self.results_table.setItem(row_idx, 2, QTableWidgetItem(sr_str))
            self.results_table.setItem(row_idx, 3, QTableWidgetItem(ch_str))
            self.results_table.setItem(row_idx, 4, QTableWidgetItem(size_str))

    def add_folder_dialog(self):
        """Add folder to library"""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Folder to Index")
        if dir_path:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.statusBar().showMessage(f"📁 Indexing: {os.path.basename(dir_path)}...")
            
            self.scan_worker = ScanWorker(self.search_engine, dir_path)
            self.scan_worker.progress.connect(self.on_scan_progress)
            self.scan_worker.finished.connect(self.on_scan_finished)
            self.scan_worker.error.connect(self.on_scan_error)
            self.scan_worker.start()

    def on_scan_progress(self, current, total, filename):
        """Update scanning progress"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_bar.setFormat(f"Scanning: {current}/{total} - {filename[:25]}...")

    def on_scan_finished(self):
        """Scanning complete"""
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("✅ Indexing complete!", 3000)
        self.update_folder_list()

    def on_scan_error(self, err_msg):
        """Scanning error"""
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage(f"❌ Indexing error: {err_msg}", 5000)

    def update_folder_list(self):
        """Refresh folder list"""
        self.folder_list_widget.clear()
        folders = self.search_engine.get_all_folders()
        for folder in folders:
            item = QListWidgetItem(os.path.basename(folder))
            item.setToolTip(folder)
            self.folder_list_widget.addItem(item)

    def on_folder_item_clicked(self, item):
        """Show files in selected folder"""
        folder_path = item.toolTip()
        results = self.search_engine.get_sounds_in_folder(folder_path)
        self.display_results(results)
        self.statusBar().showMessage(f"📁 {len(results)} files in {os.path.basename(folder_path)}")

    def show_folder_context_menu(self, pos):
        """Context menu for folder actions"""
        item = self.folder_list_widget.itemAt(pos)
        if item is None:
            return
        
        menu = QMenu()
        remove_action = QAction("🗑️ Remove from Library", self)
        remove_action.triggered.connect(lambda: self.remove_folder(item.toolTip()))
        menu.addAction(remove_action)
        menu.exec(self.folder_list_widget.mapToGlobal(pos))

    def remove_folder(self, folder_path):
        """Remove folder from library"""
        reply = QMessageBox.question(self, "Remove Folder", f"Remove '{os.path.basename(folder_path)}' from library?")
        if reply == QMessageBox.StandardButton.Yes:
            self.search_engine.remove_folder(folder_path)
            self.statusBar().showMessage(f"✅ Removed folder", 3000)
            self.update_folder_list()

    def update_history_ui(self):
        """Refresh search history"""
        self.history_list_widget.clear()
        for query in self.search_history:
            self.history_list_widget.addItem(query)

    def on_history_item_clicked(self, item):
        """Search from history"""
        self.search_input.setText(item.text())
        self.run_search()

    def on_table_selection_changed(self):
        """Load selected file"""
        selected_rows = self.results_table.selectedItems()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        sound_data = self.results_data[row]
        file_path = sound_data[0]
        
        threading.Thread(target=self.load_audio_file, args=(file_path,), daemon=True).start()

    def on_table_double_clicked(self, item):
        """Double-click to load and play"""
        row = item.row()
        sound_data = self.results_data[row]
        file_path = sound_data[0]
        
        if self.load_audio_file(file_path):
            self.audio_player.play()
            self.btn_play_pause.setText("⏸ Pause")

    def load_audio_file(self, file_path):
        """Load audio file"""
        if self.current_file_path == file_path:
            return True
        
        self.audio_player.stop()
        success = self.audio_player.load(file_path)
        if success:
            self.audio_loaded.emit(file_path)
            return True
        else:
            self.audio_loaded.emit('')
            return False

    def _on_audio_loaded(self, file_path):
        """Audio file loaded callback"""
        if not file_path:
            self.current_file_path = None
            self.lbl_sound_info.setText("❌ Error loading file")
            self.waveform_widget.clear()
            self.drag_handle.set_active(False)
            return
        
        self.current_file_path = file_path
        filename = os.path.basename(file_path)
        duration = self.audio_player.get_duration()
        self.lbl_sound_info.setText(f"▶️ {filename} | {duration:.2f}s")
        self.waveform_widget.set_audio_data(self.audio_player.data, duration)
        self.drag_handle.set_active(True)

    def toggle_play_pause(self):
        """Play/pause toggle"""
        if not self.current_file_path:
            self.statusBar().showMessage("⚠️ No file selected")
            return
        
        if self.audio_player.is_playing:
            self.audio_player.pause()
            self.btn_play_pause.setText("▶ Play")
        else:
            self.audio_player.play()
            self.btn_play_pause.setText("⏸ Pause")

    def stop_playback(self):
        """Stop playback and reset"""
        self.audio_player.stop()
        self.btn_play_pause.setText("▶ Play")
        self.statusBar().showMessage("⏹️ Stopped", 2000)

    def toggle_loop(self):
        """Toggle loop mode"""
        self.audio_player.loop = self.btn_loop.isChecked()
        self.statusBar().showMessage("🔁 Loop: ON" if self.btn_loop.isChecked() else "🔁 Loop: OFF", 2000)

    def on_volume_changed(self, val):
        """Volume slider changed"""
        self.audio_player.set_volume(val / 100.0)

    def on_speed_changed(self, val):
        """Speed slider changed"""
        speed = val / 100.0
        self.audio_player.set_speed(speed)
        self.lbl_speed_val.setText(f"{speed:.2f}x")

    def reset_speed(self):
        """Reset speed to 1.0x"""
        self.speed_slider.setValue(100)

    def on_playback_position_changed(self, pos):
        """Update waveform playhead"""
        self.waveform_widget.set_playhead_position(pos)

    def on_playback_finished(self):
        """Playback finished - reset button and playhead"""
        self.btn_play_pause.setText("▶ Play")
        self.waveform_widget.set_playhead_position(0.0)
        self.statusBar().showMessage("✅ Playback finished", 2000)

    def on_waveform_seek_requested(self, seconds):
        """Seek to time in waveform"""
        self.audio_player.set_position(seconds)

    def on_waveform_selection_changed(self, start_sec, end_sec):
        """Selection made in waveform"""
        self.audio_player.set_selection(start_sec, end_sec)
        self.btn_clear_sel.setVisible(True)
        self.btn_trim.setVisible(True)

    def on_waveform_selection_cleared(self):
        """Selection cleared"""
        self.audio_player.clear_selection()
        self.btn_clear_sel.setVisible(False)
        self.btn_trim.setVisible(False)

    def initiate_drag(self):
        """Drag file to external application"""
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
        self.statusBar().showMessage(f"📤 Dragging: {os.path.basename(drag_file_path)}")
        drag.exec(Qt.DropAction.CopyAction)
        self.statusBar().showMessage("✅ Drag completed", 2000)

    def trim_selection(self):
        """Trim and save selection"""
        if not self.current_file_path:
            return
        
        sel = self.waveform_widget.get_selection()
        if not sel:
            self.statusBar().showMessage("⚠️ No selection to trim", 2000)
            return
        
        dir_orig = os.path.dirname(self.current_file_path)
        filename_orig = os.path.basename(self.current_file_path)
        name_part, ext = os.path.splitext(filename_orig)
        default_save_path = os.path.join(dir_orig, f"{name_part}_trimmed.wav")
        
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Trimmed Audio", default_save_path, "WAV Files (*.wav)"
        )
        
        if save_path:
            success = self.audio_player.crop_selection_to_file(save_path)
            if success:
                self.statusBar().showMessage(f"✅ Saved: {os.path.basename(save_path)}", 3000)
            else:
                self.statusBar().showMessage("❌ Failed to save", 3000)

    def closeEvent(self, event):
        """Clean up on close"""
        try:
            self.audio_player.cleanup()
        except:
            pass
        super().closeEvent(event)

if __name__ == "__main__":
    import ctypes
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SoundIQ.v2")
    except:
        pass
    
    try:
        import torch
        torch.set_num_threads(os.cpu_count())
        if torch.cuda.is_available():
            torch.backends.cudnn.benchmark = True
    except:
        pass
    
    app = QApplication(sys.argv)
    window = SoundIQApp()
    window.show()
    sys.exit(app.exec())