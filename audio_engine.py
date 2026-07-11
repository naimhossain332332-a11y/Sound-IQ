import os
import threading
import numpy as np
import sounddevice as sd
import soundfile as sf

try:
    from PySide6.QtCore import QObject, Signal as pyqtSignal
except ImportError:
    from PyQt6.QtCore import QObject, pyqtSignal

class AudioPlayer(QObject):
    """Production-grade audio player with deadlock-free design.
    
    - Lazy stream initialization
    - Proper state management
    - Playhead reset on completion
    - Thread-safe operations
    """
    
    _audio_cache = {}  # Shared audio cache across instances
    
    position_changed = pyqtSignal(float)
    playback_finished = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        
        # Audio data
        self.data = None
        self.samplerate = 44100
        self.channels = 2
        
        # Playback state (protected by lock)
        self.position = 0.0
        self.start_frame = 0
        self.end_frame = 0
        self.is_playing = False
        self.is_paused = False
        self.loop = False
        self.volume = 1.0
        self.speed = 1.0
        self.last_emitted_sec = -1.0
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Stream (created lazily)
        self.stream = None
        self.blocksize = 512
        
    def load(self, file_path):
        """Load audio file with caching."""
        if not os.path.exists(file_path):
            print(f"[AudioPlayer] File not found: {file_path}")
            return False
        
        try:
            # Use cache if available
            if file_path in AudioPlayer._audio_cache:
                data, sr = AudioPlayer._audio_cache[file_path]
            else:
                data, sr = sf.read(file_path, dtype='float32')
                # Limit cache size
                if len(AudioPlayer._audio_cache) > 10:
                    AudioPlayer._audio_cache.clear()
                AudioPlayer._audio_cache[file_path] = (data, sr)
            
            # Ensure stereo
            if data.ndim == 1:
                data = np.column_stack((data, data))
            elif data.shape[1] > 2:
                data = data[:, :2]
            
        except Exception as e:
            print(f"[AudioPlayer] Error reading {file_path}: {e}")
            return False
        
        # Check if we need a new stream
        need_new_stream = (
            self.stream is None
            or sr != self.samplerate
            or data.shape[1] != self.channels
        )
        
        if need_new_stream:
            self._close_stream()
        
        # Update state
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
        
        if need_new_stream:
            self._open_stream()
        
        return True
    
    def play(self):
        """Start or resume playback."""
        with self.lock:
            if self.data is None or self.is_playing:
                return
            self.is_paused = False
            self.is_playing = True
        
        if self.stream is None:
            self._open_stream()
    
    def pause(self):
        """Pause playback."""
        with self.lock:
            self.is_paused = True
            self.is_playing = False
    
    def stop(self):
        """Stop and reset playhead to beginning."""
        with self.lock:
            self.is_playing = False
            self.is_paused = False
            self.position = float(self.start_frame)
            curr_time = self.position / self.samplerate
        
        self.position_changed.emit(curr_time)
    
    def cleanup(self):
        """Release resources."""
        with self.lock:
            self.is_playing = False
            self.is_paused = False
        self._close_stream()
    
    def set_position(self, seconds):
        """Seek to specific time."""
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
        """Set playback range."""
        with self.lock:
            if self.data is None:
                return
            total = len(self.data)
            self.start_frame = max(0, min(total, int(start_sec * self.samplerate)))
            self.end_frame = max(self.start_frame, min(total, int(end_sec * self.samplerate)))
            if self.position < self.start_frame or self.position > self.end_frame:
                self.position = float(self.start_frame)
                curr_time = self.position / self.samplerate
            else:
                return
        
        self.position_changed.emit(curr_time)
    
    def clear_selection(self):
        """Reset to full playback range."""
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
        """Export selection to file."""
        with self.lock:
            if self.data is None or self.end_frame <= self.start_frame:
                return False
            if self.start_frame == 0 and self.end_frame == len(self.data):
                return False
            try:
                chunk = self.data[self.start_frame:self.end_frame].copy()
                sr = self.samplerate
            except Exception:
                return False
        
        try:
            sf.write(dest_path, chunk, sr)
            return True
        except Exception as e:
            print(f"[AudioPlayer] Export error: {e}")
            return False
    
    def _open_stream(self):
        """Create audio output stream."""
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
            print(f"[AudioPlayer] Stream open failed: {e}")
            self.stream = None
            with self.lock:
                self.is_playing = False
    
    def _close_stream(self):
        """Close audio stream safely."""
        stream = self.stream
        self.stream = None
        if stream is not None:
            try:
                stream.abort()
                stream.close()
            except Exception:
                pass
    
    def _audio_callback(self, outdata, frames, time_info, status):
        """Audio callback - fills output buffer."""
        with self.lock:
            if not self.is_playing or self.is_paused or self.data is None:
                outdata.fill(0)
                return
            
            end_bound = self.end_frame if self.end_frame > 0 else len(self.data)
            start_bound = self.start_frame
            data = self.data
            speed = self.speed
            volume = self.volume
            pos = self.position
        
        # Compute frame indices
        out_idx = np.arange(frames, dtype=np.float64)
        inp_idx = pos + out_idx * speed
        valid = inp_idx < end_bound
        
        if not np.any(valid):
            # Reached end
            if self.loop:
                with self.lock:
                    self.position = float(start_bound)
            else:
                with self.lock:
                    self.is_playing = False
                    self.position = float(start_bound)  # ✅ Reset playhead
            outdata.fill(0)
            return
        
        # Linear interpolation
        idx_f = inp_idx[valid]
        idx_lo = np.floor(idx_f).astype(np.int32)
        idx_hi = np.clip(idx_lo + 1, 0, len(data) - 1)
        w = (idx_f - idx_lo)[:, np.newaxis]
        
        chunk = (1.0 - w) * data[idx_lo] + w * data[idx_hi]
        outdata[valid] = chunk * volume
        outdata[~valid] = 0.0
        
        # Update position
        new_pos = idx_f[-1] + speed if valid.any() else pos + frames * speed
        
        with self.lock:
            if new_pos >= end_bound:
                if self.loop:
                    self.position = float(start_bound)
                else:
                    self.position = float(start_bound)  # ✅ Reset on completion
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
        """Called when stream finishes."""
        with self.lock:
            playing = self.is_playing
        if not playing:
            self.playback_finished.emit()
