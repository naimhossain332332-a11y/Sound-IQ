import os
import threading
import numpy as np
import sounddevice as sd
import soundfile as sf

# Dynamic import of PySide6 or PyQt6
try:
    from PySide6.QtCore import QObject, Signal as pyqtSignal
except ImportError:
    from PyQt6.QtCore import QObject, pyqtSignal


class AudioPlayer(QObject):
    """
    Stable, deadlock-free audio player.

    Key design decisions:
    - self.lock protects ONLY shared state variables (data, position, flags).
    - Stream start/stop NEVER happens while self.lock is held.
    - The stream stays open between play() / stop() calls so restart is instant.
    - The stream is only recreated when the file's samplerate or channel count changes.
    """

    # Class-level cache: {file_path: (ndarray, samplerate)}
    _audio_cache = {}

    # Qt signals (safe to emit from audio callback thread via queued connection)
    position_changed = pyqtSignal(float)
    playback_finished = pyqtSignal()

    def __init__(self):
        super().__init__()

        # --- Audio data ---
        self.data = None          # float32 ndarray (frames, 2)
        self.samplerate = 44100
        self.channels = 2

        # --- Playback state (protected by self.lock) ---
        self.position = 0.0       # current frame index (float)
        self.start_frame = 0
        self.end_frame = 0
        self.is_playing = False
        self.is_paused = False
        self.loop = False
        self.volume = 1.0
        self.speed = 1.0
        self.last_emitted_sec = -1.0

        # --- Thread safety ---
        # Lock is ONLY for state variables, never held during stream operations
        self.lock = threading.Lock()

        # --- Stream ---
        self.stream = None
        self.blocksize = 512      # ~11 ms at 44100 Hz — good latency/stability balance

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, file_path):
        """Load audio file into memory and prepare stream for instant playback."""
        if not os.path.exists(file_path):
            print(f"[AudioPlayer] File not found: {file_path}")
            return False

        # Step 1 — Read file (outside lock, may be slow for large files)
        try:
            if file_path in AudioPlayer._audio_cache:
                data, sr = AudioPlayer._audio_cache[file_path]
            else:
                data, sr = sf.read(file_path, dtype='float32')
                AudioPlayer._audio_cache[file_path] = (data, sr)

            # Ensure stereo
            if data.ndim == 1:
                data = np.column_stack((data, data))
            elif data.shape[1] > 2:
                data = data[:, :2]

        except Exception as e:
            print(f"[AudioPlayer] Error reading {file_path}: {e}")
            return False

        # Step 2 — Check if stream needs to be recreated (different sample rate/channels)
        need_new_stream = (
            self.stream is None
            or sr != self.samplerate
            or data.shape[1] != self.channels
        )

        if need_new_stream:
            # Stop old stream BEFORE acquiring lock (prevents deadlock with callback)
            self._close_stream()

        # Step 3 — Update shared state (with lock, safe because stream is stopped)
        with self.lock:
            self.data = data
            self.samplerate = sr
            self.channels = data.shape[1]
            self.position = 0.0
            self.start_frame = 0
            self.end_frame = len(data)
            self.is_playing = False
            self.is_paused = False
            self.last_emitted_sec = -1.0

        # Step 4 — Open/keep stream (outside lock)
        if need_new_stream:
            self._open_stream()

        return True

    def play(self):
        """Start or resume playback instantly (stream already open)."""
        with self.lock:
            if self.data is None:
                return
            if self.is_playing:
                return
            self.is_paused = False
            self.is_playing = True

        # Open stream only if somehow it got closed
        if self.stream is None:
            self._open_stream()

    def pause(self):
        """Pause without closing the stream."""
        with self.lock:
            self.is_paused = True
            self.is_playing = False

    def stop(self):
        """
        Stop playback and reset position.
        Does NOT close the stream so the next play() is instant.
        """
        with self.lock:
            self.is_playing = False
            self.is_paused = False
            self.position = float(self.start_frame)
            curr_time = self.position / self.samplerate

        # Emit outside lock so UI can update cleanly
        self.position_changed.emit(curr_time)

    def cleanup(self):
        """Call this on app close to release audio device resources."""
        with self.lock:
            self.is_playing = False
            self.is_paused = False
        self._close_stream()

    def set_position(self, seconds):
        """Seek to a specific time."""
        with self.lock:
            if self.data is None:
                return
            target = int(seconds * self.samplerate)
            if self.end_frame > self.start_frame:
                target = max(self.start_frame, min(self.end_frame, target))
            else:
                target = max(0, min(len(self.data) - 1, target))
            self.position = float(target)
            curr_time = self.position / self.samplerate

        self.position_changed.emit(curr_time)

    def set_selection(self, start_sec, end_sec):
        """Restrict playback to a time range."""
        with self.lock:
            if self.data is None:
                return
            total = len(self.data)
            self.start_frame = max(0, min(total, int(start_sec * self.samplerate)))
            self.end_frame   = max(self.start_frame, min(total, int(end_sec * self.samplerate)))
            if self.position < self.start_frame or self.position > self.end_frame:
                self.position = float(self.start_frame)
                curr_time = self.position / self.samplerate

        self.position_changed.emit(curr_time if 'curr_time' in dir() else self.get_current_time())

    def clear_selection(self):
        """Restore full-file playback range."""
        with self.lock:
            if self.data is not None:
                self.start_frame = 0
                self.end_frame = len(self.data)

    def set_volume(self, volume):
        with self.lock:
            self.volume = max(0.0, min(1.0, volume))

    def set_speed(self, speed):
        with self.lock:
            self.speed = max(0.1, min(4.0, speed))

    def get_current_time(self):
        if self.data is None:
            return 0.0
        return self.position / self.samplerate

    def get_duration(self):
        if self.data is None:
            return 0.0
        return len(self.data) / self.samplerate

    def crop_selection_to_file(self, dest_path):
        """Export the active selection to a WAV file for drag-and-drop."""
        with self.lock:
            if self.data is None:
                return False
            if self.end_frame <= self.start_frame:
                return False
            if self.start_frame == 0 and self.end_frame == len(self.data):
                return False  # no real selection
            try:
                chunk = self.data[self.start_frame:self.end_frame].copy()
                sr = self.samplerate
            except Exception:
                return False

        try:
            sf.write(dest_path, chunk, sr)
            return True
        except Exception as e:
            print(f"[AudioPlayer] Error exporting selection: {e}")
            return False

    # ------------------------------------------------------------------
    # Internal stream management  (NEVER called while self.lock is held)
    # ------------------------------------------------------------------

    def _open_stream(self):
        """Create and start the sounddevice output stream."""
        if self.stream is not None:
            return
        try:
            self.stream = sd.OutputStream(
                samplerate=self.samplerate,
                channels=self.channels,
                blocksize=self.blocksize,
                callback=self._audio_callback,
                finished_callback=self._on_stream_finished,
            )
            self.stream.start()
        except Exception as e:
            print(f"[AudioPlayer] Failed to open stream: {e}")
            self.stream = None
            with self.lock:
                self.is_playing = False

    def _close_stream(self):
        """Stop and close the stream safely (deadlock-free)."""
        stream = self.stream   # grab reference first
        self.stream = None     # clear before stop so callback sees None stream
        if stream is not None:
            try:
                stream.abort()   # abort is faster than stop (doesn't drain buffer)
                stream.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Audio callback — runs on a high-priority audio thread
    # ------------------------------------------------------------------

    def _audio_callback(self, outdata, frames, time_info, status):
        """Fill output buffer. Called ~every 11 ms. Must be fast."""
        # Acquire lock briefly to read state
        with self.lock:
            if not self.is_playing or self.is_paused or self.data is None:
                outdata.fill(0)
                return

            end_bound   = self.end_frame if self.end_frame > 0 else len(self.data)
            start_bound = self.start_frame
            data        = self.data        # local ref (safe — numpy array is immutable here)
            speed       = self.speed
            volume      = self.volume
            pos         = self.position

        # --- Compute output frame → input frame mapping ---
        out_idx = np.arange(frames, dtype=np.float64)
        inp_idx = pos + out_idx * speed
        valid   = inp_idx < end_bound

        if not np.any(valid):
            if self.loop:
                with self.lock:
                    self.position = float(start_bound)
                outdata.fill(0)
            else:
                with self.lock:
                    self.is_playing = False
                outdata.fill(0)
            return

        # --- Linear interpolation ---
        idx_f  = inp_idx[valid]
        idx_lo = np.floor(idx_f).astype(np.int32)
        idx_hi = np.clip(idx_lo + 1, 0, len(data) - 1)
        w      = (idx_f - idx_lo)[:, np.newaxis]

        chunk = (1.0 - w) * data[idx_lo] + w * data[idx_hi]
        outdata[valid]  = chunk * volume
        outdata[~valid] = 0.0

        # --- Advance position ---
        new_pos = idx_f[-1] + speed if valid.any() else pos + frames * speed

        with self.lock:
            if new_pos >= end_bound:
                if self.loop:
                    self.position = float(start_bound)
                else:
                    self.position = float(end_bound)
                    self.is_playing = False
            else:
                self.position = new_pos

            curr_sec = self.position / self.samplerate
            should_emit = abs(curr_sec - self.last_emitted_sec) > 0.05
            if should_emit:
                self.last_emitted_sec = curr_sec

        if should_emit:
            self.position_changed.emit(curr_sec)

    def _on_stream_finished(self):
        """Called by sounddevice when the stream stops (not on every block)."""
        with self.lock:
            playing = self.is_playing
        if not playing:
            self.playback_finished.emit()


if __name__ == "__main__":
    print("Testing AudioPlayer import...")
    player = AudioPlayer()
    print("AudioPlayer OK")
