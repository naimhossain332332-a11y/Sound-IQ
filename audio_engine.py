import os
import threading
import logging
from collections import OrderedDict
import numpy as np
import sounddevice as sd
import soundfile as sf

try:
    from PySide6.QtCore import QObject, Signal as pyqtSignal
except ImportError:
    from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger("SoundIQ.audio")


class LRUCache:
    def __init__(self, max_size=20):
        self._cache = OrderedDict()
        self._max_size = max_size

    def get(self, key):
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, key, value):
        if key in self._cache:
            self._cache.move_to_end(key)
            self._cache[key] = value
        else:
            if len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            self._cache[key] = value

    def remove(self, key):
        self._cache.pop(key, None)

    def clear(self):
        self._cache.clear()

    def __contains__(self, key):
        return key in self._cache


class AudioPlayer(QObject):
    position_changed = pyqtSignal(float)
    playback_finished = pyqtSignal()

    _audio_cache = LRUCache(max_size=30)

    def __init__(self):
        super().__init__()
        self.data = None
        self.samplerate = 44100
        self.channels = 2
        self.position = 0.0
        self.start_frame = 0
        self.end_frame = 0
        self.is_playing = False
        self.is_paused = False
        self.loop = False
        self.volume = 1.0
        self.speed = 1.0
        self.last_emitted_sec = -1.0
        self.lock = threading.Lock()
        self.stream = None
        self.blocksize = 512
        self._current_file = None

    def load(self, file_path):
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return False

        try:
            cached = AudioPlayer._audio_cache.get(file_path)
            if cached is not None:
                data, sr = cached
            else:
                data, sr = sf.read(file_path, dtype="float32")
                AudioPlayer._audio_cache.put(file_path, (data, sr))

            if data.ndim == 1:
                data = np.column_stack((data, data))
            elif data.shape[1] > 2:
                data = data[:, :2]
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            AudioPlayer._audio_cache.remove(file_path)
            return False

        need_new_stream = (
            self.stream is None
            or sr != self.samplerate
            or data.shape[1] != self.channels
        )

        if need_new_stream:
            self._close_stream()

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
            self._current_file = file_path

        if need_new_stream:
            self._open_stream()

        return True

    def play(self):
        with self.lock:
            if self.data is None:
                return
            if self.is_playing:
                return
            self.is_paused = False
            self.is_playing = True
        if self.stream is None:
            self._open_stream()

    def pause(self):
        with self.lock:
            self.is_paused = True
            self.is_playing = False

    def stop(self):
        with self.lock:
            self.is_playing = False
            self.is_paused = False
            self.position = float(self.start_frame)
            curr_time = self.position / self.samplerate
        self.position_changed.emit(curr_time)

    def cleanup(self):
        with self.lock:
            self.is_playing = False
            self.is_paused = False
        self._close_stream()

    def set_position(self, seconds):
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
        curr_time = 0.0
        with self.lock:
            if self.data is None:
                return
            total = len(self.data)
            self.start_frame = max(0, min(total, int(start_sec * self.samplerate)))
            self.end_frame = max(self.start_frame, min(total, int(end_sec * self.samplerate)))
            if self.position < self.start_frame or self.position > self.end_frame:
                self.position = float(self.start_frame)
            curr_time = self.position / self.samplerate
        self.position_changed.emit(curr_time)

    def clear_selection(self):
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
        with self.lock:
            if self.data is None:
                return False
            if self.end_frame <= self.start_frame:
                return False
            if self.start_frame == 0 and self.end_frame == len(self.data):
                return False
            try:
                chunk = self.data[self.start_frame : self.end_frame].copy()
                sr = self.samplerate
            except Exception:
                return False
        try:
            sf.write(dest_path, chunk, sr)
            return True
        except Exception as e:
            logger.error(f"Error exporting selection: {e}")
            return False

    def _open_stream(self):
        if self.stream is not None:
            return
        for attempt in range(3):
            try:
                self.stream = sd.OutputStream(
                    samplerate=self.samplerate,
                    channels=self.channels,
                    blocksize=self.blocksize,
                    callback=self._audio_callback,
                    finished_callback=self._on_stream_finished,
                )
                self.stream.start()
                return
            except Exception as e:
                logger.warning(f"Stream open attempt {attempt + 1} failed: {e}")
                self.stream = None
                if attempt < 2:
                    import time
                    time.sleep(0.1)
        logger.error("Failed to open audio stream after 3 attempts")
        with self.lock:
            self.is_playing = False

    def _close_stream(self):
        stream = self.stream
        self.stream = None
        if stream is not None:
            try:
                stream.abort()
                stream.close()
            except Exception:
                pass

    def _audio_callback(self, outdata, frames, time_info, status):
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

        out_idx = np.arange(frames, dtype=np.float64)
        inp_idx = pos + out_idx * speed
        valid = inp_idx < end_bound

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

        idx_f = inp_idx[valid]
        idx_lo = np.floor(idx_f).astype(np.int32)
        idx_hi = np.clip(idx_lo + 1, 0, len(data) - 1)
        w = (idx_f - idx_lo)[:, np.newaxis]

        chunk = (1.0 - w) * data[idx_lo] + w * data[idx_hi]
        outdata[valid] = chunk * volume
        outdata[~valid] = 0.0

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
        with self.lock:
            playing = self.is_playing
        if not playing:
            self.playback_finished.emit()


if __name__ == "__main__":
    print("Testing AudioPlayer import...")
    player = AudioPlayer()
    print("AudioPlayer OK")
