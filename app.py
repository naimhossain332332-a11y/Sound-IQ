import sys
import os
import tempfile
import threading
from pathlib import Path
import soundfile as sf

# Dynamic import of PySide6 or PyQt6
try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QSplitter, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
        QHeaderView, QFileDialog, QLabel, QSlider, QProgressBar,
        QListWidget, QListWidgetItem, QMenu, QAbstractItemView
    )
    from PySide6.QtGui import QShortcut, QKeySequence
    from PySide6.QtGui import QFont, QIcon, QAction, QDrag, QCursor
    from PySide6.QtCore import Qt, QThread, Signal as pyqtSignal, QSize, QUrl, QMimeData
except ImportError:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QSplitter, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
        QHeaderView, QFileDialog, QLabel, QSlider, QProgressBar,
        QListWidget, QListWidgetItem, QMenu, QAbstractItemView
    )
    from PyQt6.QtGui import QShortcut, QKeySequence
    from PyQt6.QtGui import QFont, QIcon, QAction, QDrag, QCursor
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QUrl, QMimeData

from search_engine import SearchEngine
from audio_engine import AudioPlayer
from waveform_widget import WaveformWidget
import create_shortcut

# Worker thread for folder scanning
class ScanWorker(QThread):
    progress = pyqtSignal(int, int, str)  # current_indexed, total_to_index, current_file
    finished = pyqtSignal()

    def __init__(self, search_engine, folder_path):
        super().__init__()
        self.search_engine = search_engine
        self.folder_path = folder_path

    def run(self):
        self.search_engine.scan_folder(self.folder_path, progress_callback=self.on_progress)
        self.finished.emit()

    def on_progress(self, current, total, filename):
        self.progress.emit(current, total, filename)

# Worker thread for lazy loading AI models
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

# Custom widget for the drag handle button
class DragHandle(QLabel):
    def __init__(self, text="  DRAG FILE  ", parent=None):
        super().__init__(text, parent)
        self.parent_app = parent
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setEnabled(False) # Disabled until file is loaded
        
        # Style
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
        if active:
            self.setToolTip("Click and drag to copy file to DAW / Explorer")
        else:
            self.setToolTip("")

    def mousePressEvent(self, event):
        if self.isEnabled() and event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mouseMoveEvent(self, event):
        if self.isEnabled() and event.buttons() & Qt.MouseButton.LeftButton:
            if self.parent_app:
                self.parent_app.initiate_drag()


class SoundlyCloneApp(QMainWindow):
    audio_loaded = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sound IQ")
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "soundiq_logo.ico")
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))
        self.audio_loaded.connect(self._on_audio_loaded)
        self.resize(1200, 800)
        
        # Core engines
        self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.db")
        self.search_engine = SearchEngine(self.db_path)
        self.audio_player = AudioPlayer()
        
        # State
        self.current_file_path = None
        self.search_history = []
        self.model_loaded = False
        self.model_loading = False
        
        # Init GUI
        self.init_ui()
        self.apply_theme()
        
        # Connect audio player signals
        self.audio_player.position_changed.connect(self.on_playback_position_changed)
        self.audio_player.playback_finished.connect(self.on_playback_finished)
        
        # Shortcuts for quick actions
        self.shortcut_play_pause = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        self.shortcut_play_pause.activated.connect(self.toggle_play_pause)
        self.shortcut_stop = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.shortcut_stop.activated.connect(self.stop_playback)
        self.shortcut_trim = QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_T), self)
        self.shortcut_trim.activated.connect(self.trim_selection)
        
        # Load indexed folders to UI list
        self.update_folder_list()
        
        # Trigger lazy model loading in background
        self.load_ai_model_async()
        
        # Show default files list
        self.run_search()

    def init_ui(self):
        """Create Layout and Widgets."""
        # Main widget & layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Splitter for Sidebar & Main Content Area
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # ================= Sidebar =================
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(15)
        
        # Local Library section
        lib_label = QLabel("LOCAL LIBRARIES")
        lib_label.setStyleSheet("font-weight: bold; color: #8B949E; font-size: 10px;")
        sidebar_layout.addWidget(lib_label)
        
        self.folder_list_widget = QListWidget()
        self.folder_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.folder_list_widget.customContextMenuRequested.connect(self.show_folder_context_menu)
        self.folder_list_widget.itemClicked.connect(self.on_folder_item_clicked)
        sidebar_layout.addWidget(self.folder_list_widget)
        
        add_folder_btn = QPushButton("+ Add Local Folder")
        add_folder_btn.clicked.connect(self.add_folder_dialog)
        sidebar_layout.addWidget(add_folder_btn)
        
        # Search History section
        hist_label = QLabel("SEARCH HISTORY")
        hist_label.setStyleSheet("font-weight: bold; color: #8B949E; font-size: 10px;")
        sidebar_layout.addWidget(hist_label)
        
        self.history_list_widget = QListWidget()
        self.history_list_widget.itemClicked.connect(self.on_history_item_clicked)
        sidebar_layout.addWidget(self.history_list_widget)
        
        # Set sidebar width constraint
        sidebar.setMinimumWidth(220)
        sidebar.setMaximumWidth(320)
        splitter.addWidget(sidebar)
        
        # ================= Main Area =================
        main_content = QWidget()
        main_content_layout = QVBoxLayout(main_content)
        main_content_layout.setContentsMargins(10, 10, 10, 10)
        main_content_layout.setSpacing(10)
        splitter.addWidget(main_content)
        
        # Search Bar Row
        search_row = QHBoxLayout()
        main_content_layout.addLayout(search_row)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Loading search engine...")
        self.search_input.returnPressed.connect(self.run_search)
        search_row.addWidget(self.search_input)
        
        # AI Search button
        self.btn_search = QPushButton("Search")
        self.btn_search.clicked.connect(self.run_search)
        search_row.addWidget(self.btn_search)
        
        # Indexing Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(15)
        main_content_layout.addWidget(self.progress_bar)
        
        # Results Table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels(["Name", "Duration", "Sample Rate", "Channels", "Size"])
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.setDragEnabled(True)
        self.results_table.itemDoubleClicked.connect(self.on_table_double_clicked)
        self.results_table.itemSelectionChanged.connect(self.on_table_selection_changed)
        
        # Table stretching
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        
        main_content_layout.addWidget(self.results_table)
        
        # ================= Bottom Player Panel =================
        player_panel = QWidget()
        player_panel.setStyleSheet("background-color: #161B22; border-top: 1px solid #21262D;")
        player_panel_layout = QVBoxLayout(player_panel)
        player_panel_layout.setContentsMargins(15, 10, 15, 10)
        player_panel_layout.setSpacing(10)
        main_layout.addWidget(player_panel)
        
        # Waveform Row
        self.waveform_widget = WaveformWidget(self)
        self.waveform_widget.seek_requested.connect(self.on_waveform_seek_requested)
        self.waveform_widget.selection_changed.connect(self.on_waveform_selection_changed)
        self.waveform_widget.selection_cleared.connect(self.on_waveform_selection_cleared)
        self.waveform_widget.drag_started.connect(self.initiate_drag)
        player_panel_layout.addWidget(self.waveform_widget)
        
        # Controls Row
        controls_layout = QHBoxLayout()
        player_panel_layout.addLayout(controls_layout)
        
        # Left play controls
        self.btn_play_pause = QPushButton("▶ Play")
        self.btn_play_pause.setFixedWidth(70)
        self.btn_play_pause.clicked.connect(self.toggle_play_pause)
        controls_layout.addWidget(self.btn_play_pause)
        
        self.btn_stop = QPushButton("⏹ Stop")
        self.btn_stop.setFixedWidth(70)
        self.btn_stop.clicked.connect(self.stop_playback)
        controls_layout.addWidget(self.btn_stop)
        
        self.btn_loop = QPushButton("🔁 Loop")
        self.btn_loop.setCheckable(True)
        self.btn_loop.setFixedWidth(75)
        self.btn_loop.clicked.connect(self.toggle_loop)
        controls_layout.addWidget(self.btn_loop)
        
        # Volume
        controls_layout.addWidget(QLabel("🔊"))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        controls_layout.addWidget(self.volume_slider)
        
        controls_layout.addSpacing(20)
        
        # Speed Control
        controls_layout.addWidget(QLabel("Speed:"))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(50, 200) # 0.5x to 2.0x
        self.speed_slider.setValue(100)
        self.speed_slider.setFixedWidth(120)
        self.speed_slider.valueChanged.connect(self.on_speed_changed)
        controls_layout.addWidget(self.speed_slider)
        
        self.lbl_speed_val = QLabel("1.0x")
        self.lbl_speed_val.setFixedWidth(35)
        controls_layout.addWidget(self.lbl_speed_val)
        
        self.btn_reset_speed = QPushButton("Reset")
        self.btn_reset_speed.setFixedWidth(50)
        self.btn_reset_speed.clicked.connect(self.reset_speed)
        controls_layout.addWidget(self.btn_reset_speed)
        
        # Spacer
        controls_layout.addStretch()
        
        # Current sound selection info
        self.lbl_sound_info = QLabel("No file selected")
        self.lbl_sound_info.setStyleSheet("color: #8B949E; font-size: 11px;")
        controls_layout.addWidget(self.lbl_sound_info)
        
        controls_layout.addSpacing(20)
        
        # Clear Selection Button
        self.btn_clear_sel = QPushButton("Clear Selection")
        self.btn_clear_sel.setVisible(False)
        self.btn_clear_sel.clicked.connect(self.waveform_widget.clear_selection)
        controls_layout.addWidget(self.btn_clear_sel)
        
        # Trim Selection Button (Ctrl+T)
        self.btn_trim = QPushButton("✂ Trim & Save")
        self.btn_trim.setToolTip("Save the selected audio range to a new file (Ctrl+T)")
        self.btn_trim.setVisible(False)
        self.btn_trim.clicked.connect(self.trim_selection)
        controls_layout.addWidget(self.btn_trim)
        
        # Drag handle label (cloning Soundly drag box)
        self.drag_handle = DragHandle("  📄 DRAG FILE  ", self)
        controls_layout.addWidget(self.drag_handle)

    def apply_theme(self):
        """Apply CSS Styling for Premium Soundly Aesthetic."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0D1117;
            }
            QWidget {
                color: #C9D1D9;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
            }
            QSplitter::handle {
                background-color: #21262D;
            }
            QLineEdit {
                background-color: #161B22;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 8px 12px;
                color: #C9D1D9;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #58A6FF;
            }
            QPushButton {
                background-color: #21262D;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 6px 12px;
                color: #C9D1D9;
            }
            QPushButton:hover {
                background-color: #30363D;
                border-color: #8B949E;
            }
            QPushButton:pressed {
                background-color: #0D1117;
            }
            QPushButton:checked {
                background-color: #1F6FEB;
                border-color: #58A6FF;
                color: #FFFFFF;
            }
            QTableWidget {
                background-color: #0D1117;
                border: 1px solid #21262D;
                gridline-color: #161B22;
                border-radius: 6px;
                selection-background-color: #1f2937;
                selection-color: #00E5FF;
            }
            QHeaderView::section {
                background-color: #161B22;
                color: #8B949E;
                padding: 8px;
                border: none;
                border-bottom: 1px solid #30363D;
                font-weight: bold;
            }
            QListWidget {
                background-color: #161B22;
                border: 1px solid #21262D;
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #21262D;
            }
            QListWidget::item:selected {
                background-color: #1F6FEB;
                color: #FFFFFF;
            }
            QSlider::groove:horizontal {
                border: 1px solid #21262D;
                height: 4px;
                background: #30363D;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #58A6FF;
                width: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
            QSlider::handle:horizontal:hover {
                background: #00E5FF;
            }
            QProgressBar {
                border: 1px solid #30363D;
                border-radius: 4px;
                background-color: #161B22;
                text-align: center;
                color: white;
                font-size: 10px;
            }
            QProgressBar::chunk {
                background-color: #1F6FEB;
                border-radius: 3px;
            }
        """)

    def load_ai_model_async(self):
        """Asynchronously load the CLAP model on app startup."""
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
        if hasattr(self, 'model_progress'):
            self.statusBar().removeWidget(self.model_progress)
            self.model_progress.deleteLater()

    def on_model_load_error(self, err_msg):
        self.model_loading = False
        self.search_input.setEnabled(True)
        self.search_input.setPlaceholderText("AI Search unavailable. Check console.")
        self.statusBar().showMessage(f"AI Search error: {err_msg}", 10000)
        if hasattr(self, 'model_progress'):
            self.statusBar().removeWidget(self.model_progress)
            self.model_progress.deleteLater()

    # ================= Search logic =================
    def run_search(self):
        """Triggered on Return pressed or Search button clicked."""
        query = self.search_input.text()
        
        if query.strip() and query not in self.search_history:
            self.search_history.insert(0, query)
            self.search_history = self.search_history[:25]
            self.update_history_ui()
        
        if not self.model_loaded:
            self.statusBar().showMessage("AI Search engine still loading, please wait...", 3000)
            return
        
        self.statusBar().showMessage("Running AI search...")
        results = self.search_engine.search_ai(query)
        self.display_results(results)

    def display_results(self, results):
        """Populate results in table widget."""
        self.results_table.setRowCount(0)
        self.results_data = results # Store actual data list
        
        for row_idx, row_data in enumerate(results):
            # Row contents
            # search_keyword/search_ai output formats: (path, filename, duration, sr, channels, size, [similarity])
            path, filename, duration, sr, channels, size = row_data[:6]
            
            # Format outputs
            dur_str = f"{duration:.2f}s"
            sr_str = f"{sr / 1000:.1f} kHz"
            ch_str = "Stereo" if channels == 2 else ("Mono" if channels == 1 else f"{channels} Ch")
            
            # Size str
            size_mb = size / (1024 * 1024)
            size_str = f"{size_mb:.2f} MB" if size_mb >= 0.1 else f"{size / 1024:.0f} KB"
            
            self.results_table.insertRow(row_idx)
            
            # Set items
            item_name = QTableWidgetItem(filename)
            item_name.setToolTip(path)
            
            self.results_table.setItem(row_idx, 0, item_name)
            self.results_table.setItem(row_idx, 1, QTableWidgetItem(dur_str))
            self.results_table.setItem(row_idx, 2, QTableWidgetItem(sr_str))
            self.results_table.setItem(row_idx, 3, QTableWidgetItem(ch_str))
            self.results_table.setItem(row_idx, 4, QTableWidgetItem(size_str))

    # ================= Folder Library Management =================
    def add_folder_dialog(self):
        """Prompt directory picker to add new local audio folders."""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Folder to Add to Library")
        if dir_path:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.statusBar().showMessage(f"Scanning and indexing folder: {dir_path}...")
            
            self.scan_worker = ScanWorker(self.search_engine, dir_path)
            self.scan_worker.progress.connect(self.on_scan_progress)
            self.scan_worker.finished.connect(self.on_scan_finished)
            self.scan_worker.start()

    def on_scan_progress(self, current, total, filename):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_bar.setFormat(f"Scanning files: {current}/{total} - {filename[:30]}...")

    def on_scan_finished(self):
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("Folder scan and AI indexing complete.", 5000)
        self.update_folder_list()
        self.run_search() # Update library list

    def update_folder_list(self):
        """Sync folders in DB to UI list."""
        self.folder_list_widget.clear()
        folders = self.search_engine.get_all_folders()
        for folder in folders:
            item = QListWidgetItem(os.path.basename(folder))
            item.setToolTip(folder)
            self.folder_list_widget.addItem(item)

    def on_folder_item_clicked(self, item):
        """Show all files inside selected folder when clicked in sidebar."""
        folder_path = item.toolTip()
        results = self.search_engine.get_sounds_in_folder(folder_path)
        self.display_results(results)
        self.statusBar().showMessage(f"Showing {len(results)} files in folder: {folder_path}")

    def show_folder_context_menu(self, pos):
        """Right click context menu on folder list to remove directories."""
        item = self.folder_list_widget.itemAt(pos)
        if item is None:
            return
            
        menu = QMenu()
        remove_action = QAction("Remove Folder from Library", self)
        remove_action.triggered.connect(lambda: self.remove_folder(item.toolTip()))
        menu.addAction(remove_action)
        menu.exec(self.folder_list_widget.mapToGlobal(pos))

    def remove_folder(self, folder_path):
        self.search_engine.remove_folder(folder_path)
        self.statusBar().showMessage(f"Removed folder: {folder_path}", 4000)
        self.update_folder_list()
        self.run_search()

    # ================= History =================
    def update_history_ui(self):
        self.history_list_widget.clear()
        for query in self.search_history:
            self.history_list_widget.addItem(query)

    def on_history_item_clicked(self, item):
        self.search_input.setText(item.text())
        self.run_search()

    # ================= Audio Selection / Playback =================
    def on_table_selection_changed(self):
        """Load selected row metadata to the player, but don't autoplay. Uses async loading for smooth UI."""
        selected_rows = self.results_table.selectedItems()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        sound_data = self.results_data[row]
        file_path = sound_data[0]
        
        # Start loading in a background thread to avoid UI lag
        threading.Thread(target=self.load_audio_file, args=(file_path,), daemon=True).start()

    def on_table_double_clicked(self, item):
        """Double clicking a row loads and plays it immediately."""
        row = item.row()
        sound_data = self.results_data[row]
        file_path = sound_data[0]
        
        if self.load_audio_file(file_path):
            self.audio_player.play()
            self.btn_play_pause.setText("⏸ Pause")

    def load_audio_file(self, file_path):
        """Prepare audio player and waveform visualization with file. Returns success flag."""
        # This method may be called from a background thread; UI updates need to be done via signal.
        if self.current_file_path == file_path:
            return True
        
        self.audio_player.stop()
        success = self.audio_player.load(file_path)
        if success:
            # Emit signal to update UI in main thread
            self.audio_loaded.emit(file_path)
            return True
        else:
            # Emit signal with empty to indicate failure
            self.audio_loaded.emit('')
            return False

    def _on_audio_loaded(self, file_path):
        """Slot executed in GUI thread after async load finishes."""
        if not file_path:
            self.current_file_path = None
            self.lbl_sound_info.setText("Error loading file")
            self.waveform_widget.clear()
            self.drag_handle.set_active(False)
            return
        self.current_file_path = file_path
        filename = os.path.basename(file_path)
        self.lbl_sound_info.setText(f"{filename} | {self.audio_player.get_duration():.2f}s")
        self.waveform_widget.set_audio_data(self.audio_player.data, self.audio_player.get_duration())
        self.drag_handle.set_active(True)
        self.audio_player.play()
        self.btn_play_pause.setText("⏸ Pause")

    def toggle_play_pause(self):
        if self.audio_player.is_playing:
            self.audio_player.pause()
            self.btn_play_pause.setText("▶ Play")
        else:
            self.audio_player.play()
            self.btn_play_pause.setText("⏸ Pause")

    def stop_playback(self):
        self.audio_player.stop()
        self.btn_play_pause.setText("▶ Play")

    def toggle_loop(self):
        self.audio_player.loop = self.btn_loop.isChecked()

    def on_volume_changed(self, val):
        self.audio_player.set_volume(val / 100.0)

    def on_speed_changed(self, val):
        speed = val / 100.0
        self.audio_player.set_speed(speed)
        self.lbl_speed_val.setText(f"{speed:.2f}x")

    def reset_speed(self):
        self.speed_slider.setValue(100)
        self.audio_player.set_speed(1.0)
        self.lbl_speed_val.setText("1.0x")

    # ================= Waveform Widget Connection =================
    def on_playback_position_changed(self, pos):
        """Sync playback position from thread callback to waveform UI."""
        self.waveform_widget.set_playhead_position(pos)

    def on_playback_finished(self):
        """Reset play button when audio reaches the end."""
        self.btn_play_pause.setText("▶ Play")

    def on_waveform_seek_requested(self, seconds):
        """Scrub playhead from waveform click."""
        self.audio_player.set_position(seconds)

    def on_waveform_selection_changed(self, start_sec, end_sec):
        """Selection range active."""
        self.audio_player.set_selection(start_sec, end_sec)
        self.btn_clear_sel.setVisible(True)
        self.btn_trim.setVisible(True)
        
    def on_waveform_selection_cleared(self):
        """Selection range cleared."""
        self.audio_player.clear_selection()
        self.btn_clear_sel.setVisible(False)
        self.btn_trim.setVisible(False)

    # ================= Drag & Drop Integration =================
    def initiate_drag(self):
        """Perform external QDrag copy to DAWs or File Explorers."""
        if not self.current_file_path:
            return
            
        drag = QDrag(self)
        mime_data = QMimeData()
        
        # Check if there is an active selection cropped clip
        sel = self.waveform_widget.get_selection()
        
        if sel:
            # Generate temporary file for the cropped segment
            temp_dir = tempfile.gettempdir()
            filename_orig = os.path.basename(self.current_file_path)
            name_part, ext = os.path.splitext(filename_orig)
            
            # Standard extension as WAV to preserve high quality
            temp_file_name = f"{name_part}_selection.wav"
            temp_path = os.path.join(temp_dir, temp_file_name)
            
            # Export crop range
            success = self.audio_player.crop_selection_to_file(temp_path)
            
            if success:
                drag_file_path = temp_path
            else:
                drag_file_path = self.current_file_path
        else:
            drag_file_path = self.current_file_path
            
        # Put local file url in mime data
        mime_data.setUrls([QUrl.fromLocalFile(drag_file_path)])
        drag.setMimeData(mime_data)
        
        # Execute drag operation
        self.statusBar().showMessage(f"Dragging: {os.path.basename(drag_file_path)}")
        drag.exec(Qt.DropAction.CopyAction)
        self.statusBar().showMessage("Drag completed", 3000)

    def trim_selection(self):
        """Save the active audio selection to a new WAV file."""
        if not self.current_file_path:
            return
            
        sel = self.waveform_widget.get_selection()
        if not sel:
            self.statusBar().showMessage("No selection range active to trim.", 3000)
            return
            
        # Propose a default save path in original directory
        dir_orig = os.path.dirname(self.current_file_path)
        filename_orig = os.path.basename(self.current_file_path)
        name_part, ext = os.path.splitext(filename_orig)
        default_save_path = os.path.join(dir_orig, f"{name_part}_trimmed.wav")
        
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Trimmed Selection", default_save_path, "WAV Files (*.wav)"
        )
        
        if save_path:
            success = self.audio_player.crop_selection_to_file(save_path)
            if success:
                self.statusBar().showMessage(f"Trimmed clip saved successfully: {os.path.basename(save_path)}", 5000)
            else:
                self.statusBar().showMessage("Failed to save trimmed selection.", 5000)

        # Legacy hotkey methods removed; shortcuts are defined earlier using QShortcut.

    def closeEvent(self, event):
        """Cleanup audio threads on close."""
        self.audio_player.cleanup()
        super().closeEvent(event)


if __name__ == "__main__":
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SoundIQ.1")
    
    import torch
    torch.set_num_threads(os.cpu_count())
    if torch.cuda.is_available():
        torch.backends.cudnn.benchmark = True
        torch.backends.cuda.matmul.allow_tf32 = True
    
    app = QApplication(sys.argv)
    ico_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "soundiq_logo.ico")
    if os.path.exists(ico_path):
        app_icon = QIcon(ico_path)
        app.setWindowIcon(app_icon)
    
    window = SoundlyCloneApp()
    window.show()
    # Ensure desktop shortcut exists for easy launch
    try:
        created = create_shortcut.create_desktop_shortcut()
        if created:
            print("Desktop shortcut is ready.")
    except Exception as e:
        print(f"Failed to create desktop shortcut: {e}")
    sys.exit(app.exec())
