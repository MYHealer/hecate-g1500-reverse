"""
music_reactive.py - HECATE G1500 BAR 声光律动
实时捕获系统音频，分析频率/节拍，映射到 LED 颜色和灯效。

依赖: pip install pyaudiowpatch numpy
用法: python music_reactive.py
"""
import ctypes
import time
import sys
import struct
import math
import threading

import numpy as np
import pyaudiowpatch as pyaudio

# ======== LED 控制 ========
hidapi = ctypes.CDLL(r'C:\Program Files\HECATE\hidapi.dll')

class hid_device_info(ctypes.Structure): pass
hid_device_info._fields_ = [
    ('path', ctypes.c_char_p), ('vendor_id', ctypes.c_ushort),
    ('product_id', ctypes.c_ushort), ('serial_number', ctypes.c_wchar_p),
    ('release_number', ctypes.c_ushort), ('manufacturer_string', ctypes.c_wchar_p),
    ('product_string', ctypes.c_wchar_p), ('usage_page', ctypes.c_ushort),
    ('usage', ctypes.c_ushort), ('interface_number', ctypes.c_int),
    ('next', ctypes.POINTER(hid_device_info)),
]

hidapi.hid_enumerate.argtypes = [ctypes.c_ushort, ctypes.c_ushort]
hidapi.hid_enumerate.restype = ctypes.POINTER(hid_device_info)
hidapi.hid_open_path.argtypes = [ctypes.c_char_p]
hidapi.hid_open_path.restype = ctypes.c_void_p
hidapi.hid_write.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int]
hidapi.hid_write.restype = ctypes.c_int
hidapi.hid_send_feature_report.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int]
hidapi.hid_send_feature_report.restype = ctypes.c_int
hidapi.hid_close.argtypes = [ctypes.c_void_p]


def find_col02():
    devs = hidapi.hid_enumerate(0x35BB, 0xB001)
    d = devs
    result = None
    while d and d[0].path:
        if b'Col02' in d[0].path:
            result = d[0].path
            break
        d = d[0].next
    hidapi.hid_free_enumeration(devs)
    return result


# 5个预设颜色
PRESETS = [
    ('red',      (0xFF, 0x00, 0x00)),
    ('green',    (0x00, 0xFF, 0x00)),
    ('blue',     (0x00, 0x50, 0xFF)),
    ('ice_blue', (0x00, 0xFF, 0xFF)),
    ('pink',     (0xFF, 0x00, 0xFF)),
]

MODE_CONSTANT = 0
MODE_BREATHE = 1
MODE_BLINK_SLOW = 2
MODE_BLINK_FAST = 3
MODE_HEARTBEAT = 4


def nearest_preset(r, g, b):
    """找到最近的预设颜色"""
    best = None
    best_dist = float('inf')
    for name, (pr, pg, pb) in PRESETS:
        dist = (r - pr)**2 + (g - pg)**2 + (b - pb)**2
        if dist < best_dist:
            best_dist = dist
            best = (name, (pr, pg, pb))
    return best


def send_led(path, mode, r, g, b):
    """发送 LED 命令"""
    h = hidapi.hid_open_path(path)
    if not h:
        return False
    # init
    init = (ctypes.c_ubyte * 16)(0xED, 0x10, *([0]*14))
    hidapi.hid_write(h, init, 16)
    time.sleep(0.02)
    # set color
    report = (ctypes.c_ubyte * 16)(0xED, 0x06, 0x10, 0x01, mode, r, g, b, *([0]*8))
    ret = hidapi.hid_send_feature_report(h, report, 16)
    hidapi.hid_close(h)
    return ret > 0


# ======== 音频分析 ========
CHUNK = 1024          # 每帧采样数
RATE = 48000          # 采样率
BASS_MAX = 250        # bass 上限 Hz
MID_MAX = 2000        # mid 上限 Hz
BEAT_THRESHOLD = 1.5  # 节拍检测: 能量突变倍数
BEAT_COOLDOWN = 0.3   # 节拍冷却时间 (秒)
LED_INTERVAL = 0.1    # LED 更新间隔 (秒)


class AudioAnalyzer:
    def __init__(self):
        self.energy_history = []
        self.max_history = 43  # ~1秒 (43帧 * 21ms)
        self.last_beat_time = 0
        self.current_mode = MODE_CONSTANT
        self.mode_until = 0

    def analyze(self, audio_data, channels):
        """分析一帧音频，返回 (bass, mid, treble) 能量 (0-1)"""
        # 转为 float
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32) / 32768.0

        # 混合为单声道
        if channels > 1:
            audio_data = audio_data.reshape(-1, channels).mean(axis=1)

        # FFT
        fft = np.fft.rfft(audio_data)
        magnitude = np.abs(fft) / len(audio_data)
        freqs = np.fft.rfftfreq(len(audio_data), 1.0 / RATE)

        # 分段能量 (用峰值而非均值，避免零值稀释)
        bass_mask = freqs <= BASS_MAX
        mid_mask = (freqs > BASS_MAX) & (freqs <= MID_MAX)
        treble_mask = freqs > MID_MAX

        bass = np.max(magnitude[bass_mask]) if np.any(bass_mask) else 0
        mid = np.max(magnitude[mid_mask]) if np.any(mid_mask) else 0
        treble = np.max(magnitude[treble_mask]) if np.any(treble_mask) else 0

        return bass, mid, treble

    def detect_beat(self, bass):
        """基于 bass 能量检测节拍"""
        now = time.time()
        self.energy_history.append(bass)
        if len(self.energy_history) > self.max_history:
            self.energy_history.pop(0)

        if len(self.energy_history) < 5:
            return False

        avg = np.mean(self.energy_history)
        is_beat = bass > avg * BEAT_THRESHOLD and bass > 0.002

        if is_beat and (now - self.last_beat_time) > BEAT_COOLDOWN:
            self.last_beat_time = now
            return True
        return False

    def get_mode(self, is_beat, bass):
        """根据节拍强度选择灯效模式"""
        now = time.time()

        if is_beat:
            if bass > 0.3:
                self.current_mode = MODE_HEARTBEAT
                self.mode_until = now + 0.8
            elif bass > 0.15:
                self.current_mode = MODE_BLINK_FAST
                self.mode_until = now + 0.5
            else:
                self.current_mode = MODE_BREATHE
                self.mode_until = now + 0.6

        if now > self.mode_until:
            self.current_mode = MODE_CONSTANT

        return self.current_mode


# ======== 主循环 ========
def energy_to_rgb(val):
    """对数缩放能量到 0-255"""
    if val <= 0:
        return 0
    # 典型范围 0.001-0.05，映射到 0-255
    db = 20 * math.log10(max(val, 1e-6))
    # db 范围约 -60 到 -26，归一化到 0-255
    normalized = (db + 70) / 40  # -70→0, -30→1
    return max(0, min(255, int(normalized * 255)))


def main():
    print("=== HECATE G1500 BAR 声光律动 ===\n")

    # 找 LED
    path = find_col02()
    if not path:
        print("ERROR: Col02 not found!")
        return
    print(f"LED: Col02 found")

    # 找 WASAPI loopback 设备
    p = pyaudio.PyAudio()

    try:
        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    except Exception:
        print("ERROR: WASAPI not available")
        p.terminate()
        return

    default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
    print(f"Output: {default_speakers['name']}")

    # 找对应的 loopback 设备 (名称含 "[Loopback]")
    loopback_device = None
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        if "[Loopback]" in dev["name"]:
            # 检查是否对应默认输出设备
            out_name = dev["name"].replace("[Loopback]", "").strip()
            if out_name in default_speakers["name"] or default_speakers["name"] in out_name:
                loopback_device = dev
                break

    if not loopback_device:
        print("ERROR: Loopback device not found!")
        print("Make sure audio is playing through HECATE G1500 BAR")
        p.terminate()
        return

    print(f"Loopback: {loopback_device['name']}")
    channels = int(loopback_device["maxInputChannels"])
    print(f"Channels: {channels}, Rate: {RATE}")

    # 打开音频流
    stream = p.open(
        format=pyaudio.paInt16,
        channels=channels,
        rate=RATE,
        input=True,
        input_device_index=loopback_device["index"],
        frames_per_buffer=CHUNK,
    )

    analyzer = AudioAnalyzer()
    last_led_time = 0
    frame_count = 0
    idle_count = 0

    print("\n律动运行中... 播放音乐，Ctrl+C 退出\n")

    try:
        while True:
            # 检查是否有数据可读
            available = stream.get_read_available()
            if available < CHUNK:
                time.sleep(0.01)
                idle_count += 1
                if idle_count > 100 and idle_count % 100 == 0:
                    print(f"\r等待音频... (播放音乐)", end="", flush=True)
                continue

            idle_count = 0

            # 读音频帧
            data = stream.read(CHUNK, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16)

            # 8声道→取前2声道(立体声)→混合单声道
            if channels >= 2:
                audio_data = audio_data.reshape(-1, channels)
                audio_data = audio_data[:, :2].mean(axis=1)

            # 分析
            bass, mid, treble = analyzer.analyze(audio_data, 1)
            is_beat = analyzer.detect_beat(bass)
            mode = analyzer.get_mode(is_beat, bass)

            # 频率→RGB
            r = energy_to_rgb(bass)
            g = energy_to_rgb(mid)
            b_val = energy_to_rgb(treble)

            # 找最近预设
            preset_name, (pr, pg, pb) = nearest_preset(r, g, b_val)

            # 控制 LED (限帧)
            now = time.time()
            if now - last_led_time >= LED_INTERVAL:
                send_led(path, mode, pr, pg, pb)
                last_led_time = now

            # 状态输出
            frame_count += 1
            if frame_count % 10 == 0:
                beat_str = "BEAT!" if is_beat else ""
                mode_names = ["常亮", "呼吸", "慢闪", "快闪", "心跳"]
                bar_r = "#" * (r // 25)
                bar_g = "#" * (g // 25)
                bar_b = "#" * (b_val // 25)
                print(f"\r bass[{bar_r:<10}] mid[{bar_g:<10}] treb[{bar_b:<10}] "
                      f"→ {preset_name:8s} {mode_names[mode]:4s} {beat_str:5s}", end="", flush=True)

    except KeyboardInterrupt:
        print("\n\n停止律动")
        # 关灯
        send_led(path, MODE_CONSTANT, 0, 0, 0)
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()


if __name__ == "__main__":
    main()
