import customtkinter as ctk
import tkinter as tk
from pynput import mouse
import pyautogui
import threading
import json
import os

POSITIONS_FILE = 'positions.json'

positions = {
    'buy': None,
    'sell': None,
    'close': None,
    'recognition_area': None,
    'signal_colors': {},    # 여기에 {'buy': (r,g,b), 'sell': (r,g,b), 'close': (r,g,b)} 저장
    'start_time': "09:00",
    'end_time': "15:00",
}

save_position_mode = None  # 위치 저장용
save_signal_color_mode = None  # 신호색 저장용

def save_positions_to_file(filename=POSITIONS_FILE):
    data_to_save = {}
    for k, v in positions.items():
        if v is None:
            data_to_save[k] = None
        elif isinstance(v, tuple):
            data_to_save[k] = list(v)
        elif isinstance(v, dict):
            # dict 안 RGB 튜플 → 리스트로 변환
            data_to_save[k] = {key: list(val) if val else None for key, val in v.items()}
        else:
            data_to_save[k] = v
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=2, ensure_ascii=False)
        print("positions.json에 저장 완료:", data_to_save)
    except Exception as e:
        print("좌표 저장 실패:", e)

def load_positions_from_file(filename=POSITIONS_FILE):
    global positions
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for k in positions.keys():
                v = data.get(k)
                if isinstance(v, list):
                    positions[k] = tuple(v)
                elif isinstance(v, dict):
                    if k == 'signal_colors':
                        positions[k] = {key: tuple(val) if val else None for key, val in v.items()}
                    else:
                        positions[k] = v
                elif v is None and k == 'signal_colors':
                    positions[k] = {}
                else:
                    positions[k] = v
            print("positions.json에서 불러옴:", positions)
        except Exception as e:
            print("좌표 불러오기 실패:", e)
    else:
        print("좌표 파일이 존재하지 않습니다.")


def on_click(x, y, button, pressed):
    global save_position_mode, save_signal_color_mode
    if pressed and button == mouse.Button.right:
        if save_position_mode is not None:
            positions[save_position_mode] = (x, y)
            print(f"{save_position_mode} 좌표 저장됨: {(x, y)}")
            save_position_mode = None
            save_positions_to_file()
            return False
        elif save_signal_color_mode is not None:
            try:
                rgb = pyautogui.screenshot().getpixel((x, y))
                positions.setdefault('signal_colors', {})[save_signal_color_mode] = rgb
                print(f"{save_signal_color_mode} 신호 색상 저장됨: {rgb}")
            except Exception as e:
                print("신호 색상 저장 중 오류:", e)
            save_signal_color_mode = None
            save_positions_to_file()
            return False


def start_mouse_listener():
    with mouse.Listener(on_click=on_click) as listener:
        listener.join()

def save_position(position_type):
    global save_position_mode
    save_position_mode = position_type
    print(f"[INFO] {position_type} 좌표 저장 대기중... HTS 창에서 마우스 오른쪽 클릭하세요.")
    listener_thread = threading.Thread(target=start_mouse_listener, daemon=True)
    listener_thread.start()

def save_signal_color(signal_type):
    global save_signal_color_mode
    save_signal_color_mode = signal_type
    print(f"[INFO] {signal_type} 신호 색상 저장 대기중... HTS 창에서 마우스 왼쪽 클릭하세요.")
    listener_thread = threading.Thread(target=start_mouse_listener, daemon=True)
    listener_thread.start()

def on_start_time_change(event=None):
    h = start_hour_combo.get()
    m = start_minute_combo.get()
    positions['start_time'] = f"{h}:{m}"
    print(f"시작 시간 저장됨: {positions['start_time']}")
    save_positions_to_file()

def on_end_time_change(event=None):
    h = end_hour_combo.get()
    m = end_minute_combo.get()
    positions['end_time'] = f"{h}:{m}"
    print(f"종료 시간 저장됨: {positions['end_time']}")
    save_positions_to_file()


def update_time_ui():
    start_time = positions.get('start_time', "09:00")
    end_time = positions.get('end_time', "15:00")
    if not start_time:
        start_time = "19:00"
    if not end_time:
        end_time = "07:55"
    sh, sm = start_time.split(":")
    eh, em = end_time.split(":")
    start_hour_combo.set(sh)
    start_minute_combo.set(sm)
    end_hour_combo.set(eh)
    end_minute_combo.set(em)

# 인식 범위 드래그 캡처 윈도우는 DragCaptureWindow 클래스 사용

class DragCaptureWindow(tk.Toplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback = callback
        self.start_x = self.start_y = 0
        self.rect = None

        self.attributes("-fullscreen", True)
        self.attributes("-alpha", 0.3)
        self.config(bg='black')

        self.canvas = tk.Canvas(self, cursor="cross", bg="gray")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

        self.bind("<Escape>", lambda e: self.destroy())

    def on_button_press(self, event):
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y,
                                                 outline="red", width=2)

    def on_drag(self, event):
        cur_x, cur_y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)
        x1, y1 = min(self.start_x, end_x), min(self.start_y, end_y)
        x2, y2 = max(self.start_x, end_x), max(self.start_y, end_y)
        rect = (int(x1), int(y1), int(x2 - x1), int(y2 - y1))
        self.callback(rect)
        self.destroy()

def on_recognition_area_selected(rect):
    positions['recognition_area'] = rect
    print(f"인식 범위 저장됨: {rect}")
    save_positions_to_file()

def open_drag_capture():
    DragCaptureWindow(app, on_recognition_area_selected)

def apply_time_settings():
    h_start = start_hour_combo.get()
    m_start = start_minute_combo.get()
    h_end = end_hour_combo.get()
    m_end = end_minute_combo.get()

    positions['start_time'] = f"{h_start}:{m_start}"
    positions['end_time'] = f"{h_end}:{m_end}"
    save_positions_to_file()

    print(f"[적용 완료] 시작 시간: {positions['start_time']}, 종료 시간: {positions['end_time']}")

# UI 및 기존 코드에 신호 인식 버튼 추가

app = ctk.CTk()
app.geometry("420x460")
app.title("자동 매매 신호 인식")

def toggle_settings():
    if setting_frame.winfo_ismapped():
        setting_frame.pack_forget()
    else:
        setting_frame.pack(pady=10)

trade_frame = ctk.CTkFrame(app)
trade_frame.pack(pady=20)

start_button = ctk.CTkButton(trade_frame, text="매매 시작", width=120, height=40)
start_button.pack(side="left", padx=10)
stop_button = ctk.CTkButton(trade_frame, text="매매 종료", width=120, height=40)
stop_button.pack(side="left", padx=10)

setting_button = ctk.CTkButton(app, text="Setting", command=toggle_settings, width=120, height=40)
setting_button.pack(pady=10)

setting_frame = ctk.CTkFrame(app)
setting_frame.pack_forget()

coordinate_frame = ctk.CTkFrame(setting_frame)
coordinate_frame.pack(pady=5)

btn_info = [("매수 버튼", "buy"), ("매도 버튼", "sell"), ("청산 버튼", "close")]

for text, key in btn_info:
    btn = ctk.CTkButton(coordinate_frame, text=text, width=100, height=40,
                        command=lambda k=key: save_position(k))
    btn.pack(side="left", padx=5)

signal_frame = ctk.CTkFrame(setting_frame)
signal_frame.pack(pady=5)

signal_btn_info = [("매수 신호", "buy"), ("매도 신호", "sell"), ("청산 신호", "close")]

for text, key in signal_btn_info:
    btn = ctk.CTkButton(signal_frame, text=text, width=100, height=40,
                        command=lambda k=key: save_signal_color(k))
    btn.pack(side="left", padx=5)

ctk.CTkButton(setting_frame, text="인식 범위 설정", width=320, height=40, command=open_drag_capture).pack(pady=5)

time_start_frame = ctk.CTkFrame(setting_frame)
time_start_frame.pack(pady=(10,5))

ctk.CTkLabel(time_start_frame, text="시작 시간", width=100).pack(side="left", padx=5)

hours = [f"{h:02d}" for h in range(24)]
minutes = [f"{m:02d}" for m in range(60)]

start_hour_combo = ctk.CTkComboBox(time_start_frame, values=hours, width=60)
start_hour_combo.set("09")
start_hour_combo.pack(side="left", padx=(0,5))

ctk.CTkLabel(time_start_frame, text=":").pack(side="left")

start_minute_combo = ctk.CTkComboBox(time_start_frame, values=minutes, width=60)
start_minute_combo.set("00")
start_minute_combo.pack(side="left", padx=(5,0))

time_end_frame = ctk.CTkFrame(setting_frame)
time_end_frame.pack(pady=5)

ctk.CTkLabel(time_end_frame, text="종료 시간", width=100).pack(side="left", padx=5)

end_hour_combo = ctk.CTkComboBox(time_end_frame, values=hours, width=60)
end_hour_combo.set("15")
end_hour_combo.pack(side="left", padx=(0,5))

ctk.CTkLabel(time_end_frame, text=":").pack(side="left")

end_minute_combo = ctk.CTkComboBox(time_end_frame, values=minutes, width=60)
end_minute_combo.set("00")
end_minute_combo.pack(side="left", padx=(5,0))

apply_time_button = ctk.CTkButton(setting_frame, text="시간 적용", width=320, height=40, command=apply_time_settings)
apply_time_button.pack(pady=10)

load_positions_from_file()
update_time_ui()

app.mainloop()
