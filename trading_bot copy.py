import customtkinter as ctk
import tkinter as tk
from pynput import mouse
import pyautogui
import threading
import json
import os
import datetime
import time
import screeninfo
import tkinter.simpledialog as simpledialog
from PIL import ImageGrab
from screeninfo import get_monitors

POSITIONS_FILE = 'positions.json'
trade_stop_event = threading.Event()
trade_thread = None
min_x = None
min_y = None

def update_min_screen_coords():
    global min_x, min_y
    monitors = get_monitors()
    min_x = min(monitor.x for monitor in monitors)
    min_y = min(monitor.y for monitor in monitors)

positions = {
    'buy': None,
    'sell': None,
    'close': None,
    'recognition_area': None,
    'signal_colors': {},    # {'buy': (r,g,b), 'sell': (r,g,b), 'close': (r,g,b)}
    'start_time': "09:00",
    'end_time': "15:00",
}

save_position_mode = None  # 위치 저장용 플래그
save_signal_color_mode = None  # 신호 색상 저장용 플래그
trade_state = 'close'  # 초기 상태는 'close'


def time_str_to_minutes(tstr):
    h, m = tstr.split(":")
    return int(h)*60 + int(m)

def is_time_in_range(current_str, start_str, end_str):
    current = time_str_to_minutes(current_str)
    start = time_str_to_minutes(start_str)
    end = time_str_to_minutes(end_str)
    if start < end:
        return start < current < end
    else:
        # 종료시간이 다음날인 경우
        return current > start or current < end

def get_current_time_str():
    now = datetime.datetime.now()
    return now.strftime("%H:%M")

def color_match(c1, c2, tolerance=30):
    """RGB 색상 비교, tolerance내면 True"""
    if c1 is None or c2 is None:
        return False
    return all(abs(a-b) <= tolerance for a,b in zip(c1, c2))

def safe_click(x, y):
    """
    클릭 시 사용자의 마우스 위치를 훼손하지 않고, 
    클릭 대상 위치로 순간 이동 후 클릭, 다시 원래 위치로 복원합니다.
    """
    current_pos = pyautogui.position()  # 현재 위치 저장
    try:
        pyautogui.click(x, y)
    finally:
        pyautogui.moveTo(current_pos.x, current_pos.y)

def monitor_and_trade():
    global trade_stop_event, trade_state

    if not positions.get('recognition_area'):
        print("[경고] 인식 범위가 설정되지 않았습니다.")
        return

    buy_pos = positions.get('buy')
    sell_pos = positions.get('sell')
    close_pos = positions.get('close')
    recognition_area = positions.get('recognition_area')
    signal_colors = positions.get('signal_colors', {})

    if not all([buy_pos, sell_pos, close_pos, recognition_area]) or not signal_colors:
        print("[경고] 좌표 또는 신호 색상이 모두 설정되어 있어야 합니다.")
        return

    print("[매매 시작] 감시 중... 중지하려면 '매매 종료' 버튼 누르세요.")

    rx, ry, rw, rh = recognition_area

    try:
        while not trade_stop_event.is_set():
            now_str = get_current_time_str()
            if not is_time_in_range(now_str, positions['start_time'], positions['end_time']):
                print(f"[시간대 벗어남] 현재시간 {now_str}는 허용 시간 {positions['start_time']}~{positions['end_time']} 밖입니다.")
                safe_click(close_pos[0], close_pos[1])
                break
    

            screenshot = pyautogui.screenshot(region=(rx, ry, rw, rh))

            found_buy = False
            found_sell = False
            found_close = False

            step = 5
            for x in range(0, rw, step):
                for y in range(0, rh, step):
                    px = screenshot.getpixel((x, y))
                    if color_match(px, signal_colors.get('buy')):
                        found_buy = True
                    elif color_match(px, signal_colors.get('sell')):
                        found_sell = True
                    elif color_match(px, signal_colors.get('close')):
                        found_close = True
                    if found_buy and found_close:
                        break
                    if found_sell and found_close:
                        break
                if (found_buy and found_close) or (found_sell and found_close):
                    break

            # 상태와 신호에 따라 클릭 및 상태 변경
            # buy+close 우선, 다음 sell+close, 그 다음 각각 단독 신호 처리
            if found_buy and found_close:
                if trade_state != 'buy':
                    print("[신호 감지] buy+close → close 클릭 후 buy 클릭")
                    safe_click(close_pos[0], close_pos[1])
                    time.sleep(0.1)
                    safe_click(buy_pos[0], buy_pos[1])
                    trade_state = 'buy'
            elif found_sell and found_close:
                if trade_state != 'sell':
                    print("[신호 감지] sell+close → close 클릭 후 sell 클릭")
                    safe_click(close_pos[0], close_pos[1])
                    time.sleep(0.1)
                    safe_click(sell_pos[0], sell_pos[1])
                    trade_state = 'sell'
            elif found_buy:
                if trade_state != 'buy':
                    print("[신호 감지] close → buy 클릭")
                    safe_click(close_pos[0], close_pos[1])
                    time.sleep(0.1)
                    safe_click(buy_pos[0], buy_pos[1])
                    trade_state = 'buy'
            elif found_sell:
                if trade_state != 'sell':
                    print("[신호 감지] sell → sell 클릭")
                    safe_click(close_pos[0], close_pos[1])
                    time.sleep(0.1)
                    safe_click(sell_pos[0], sell_pos[1])
                    trade_state = 'sell'
            elif found_close:
                if trade_state != 'close':
                    print("[신호 감지] close → close 클릭")
                    safe_click(close_pos[0], close_pos[1])
                    trade_state = 'close'
            else:
                # 신호 미감지, 상태 유지
                pass

            trade_stop_event.wait(1)

        print("[매매 종료] 감시 중단됨")

    except Exception as e:
        print("[오류 발생] 감시 중단:", e)


def start_trading_thread():
    global trade_stop_event, trade_thread, trade_state
    if trade_thread and trade_thread.is_alive():
        print("[알림] 이미 매매 감시가 동작 중입니다.")
        return
    trade_stop_event.clear()
    trade_state = 'close'  # 시작할 때 상태 초기화
    trade_thread = threading.Thread(target=monitor_and_trade, daemon=True)
    trade_thread.start()

def stop_trading():
    global trade_stop_event
    if trade_thread and trade_thread.is_alive():
        trade_stop_event.set()
        print("[알림] 매매 감시 종료 요청됨.")
    else:
        print("[알림] 실행 중인 매매 감시가 없습니다.")


def save_positions_to_file(filename=POSITIONS_FILE):
    data_to_save = {}
    for k, v in positions.items():
        if v is None:
            data_to_save[k] = None
        elif isinstance(v, tuple):
            data_to_save[k] = list(v)
        elif isinstance(v, dict):
            # dict 내 RGB 튜플 값을 리스트로 변환
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
    global save_position_mode, save_signal_color_mode, min_x, min_y
    if pressed and button == mouse.Button.right:
        if save_position_mode is not None:
            positions[save_position_mode] = (x, y)
            print(f"{save_position_mode} 좌표 저장됨: {(x, y)}")
            save_position_mode = None
            save_positions_to_file()
            return False
        elif save_signal_color_mode is not None:
            try:
                img = ImageGrab.grab(all_screens=True)
                # 좌표 보정
                img_x, img_y = x - min_x, y - min_y
                rgb = img.getpixel((img_x, img_y))
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
    print(f"[INFO] {signal_type} 신호 색상 저장 대기중... HTS 창에서 마우스 오른쪽 클릭하세요.")
    update_min_screen_coords()  # 보정값 갱신
    listener_thread = threading.Thread(target=start_mouse_listener, daemon=True)
    listener_thread.start()


def update_time_ui():
    start_time = positions.get('start_time', "09:00")
    end_time = positions.get('end_time', "15:00")
    if not start_time:
        start_time = "09:00"
    if not end_time:
        end_time = "15:00"
    sh, sm = start_time.split(":")
    eh, em = end_time.split(":")
    start_hour_combo.set(sh)
    start_minute_combo.set(sm)
    end_hour_combo.set(eh)
    end_minute_combo.set(em)


def apply_time_settings():
    h_start = start_hour_combo.get()
    m_start = start_minute_combo.get()
    h_end = end_hour_combo.get()
    m_end = end_minute_combo.get()

    positions['start_time'] = f"{h_start}:{m_start}"
    positions['end_time'] = f"{h_end}:{m_end}"
    save_positions_to_file()

    print(f"[적용 완료] 시작 시간: {positions['start_time']}, 종료 시간: {positions['end_time']}")


# 인식 범위 드래그 캡처 윈도우

class DragCaptureWindow(tk.Toplevel):
    def __init__(self, parent, callback, monitor):
        super().__init__(parent)
        self.callback = callback
        self.monitor = monitor
        self.start_x = self.start_y = 0
        self.rect = None

        # 모니터 위치/크기에 맞게 창 크기 및 위치 설정
        self.geometry(f"{monitor.width}x{monitor.height}+{monitor.x}+{monitor.y}")

        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.3)
        self.config(bg='black')

        self.canvas = tk.Canvas(self, cursor="cross", bg="gray")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

        self.bind("<Escape>", lambda e: self.destroy())

    def on_button_press(self, event):
        # 캔버스 좌표(0 ~ 모니터 크기)
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline="red", width=2)

    def on_drag(self, event):
        cur_x, cur_y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)

        x1, y1 = min(self.start_x, end_x), min(self.start_y, end_y)
        x2, y2 = max(self.start_x, end_x), max(self.start_y, end_y)

        # 모니터 좌표를 기준으로 절대 스크린 좌표로 변환
        abs_x1 = int(x1) + self.monitor.x
        abs_y1 = int(y1) + self.monitor.y
        width = int(x2 - x1)
        height = int(y2 - y1)
        rect = (abs_x1, abs_y1, width, height)

        self.callback(rect)
        self.destroy()


def on_recognition_area_selected(rect):
    positions['recognition_area'] = rect
    print(f"인식 범위 저장됨: {rect}")
    save_positions_to_file()


def open_drag_capture():
    monitors = screeninfo.get_monitors()
    monitor_list_str = "\n".join(
        f"{i}: {m.name} ({m.width}x{m.height} at {m.x},{m.y})"
        for i, m in enumerate(monitors)
    )
    selected = simpledialog.askinteger("모니터 선택", f"인식 범위 설정할 모니터 번호를 입력하세요:\n{monitor_list_str}", parent=app)

    if selected is None or selected < 0 or selected >= len(monitors):
        print("모니터 선택이 취소되었거나 잘못된 번호입니다.")
        return

    monitor = monitors[selected]
    DragCaptureWindow(app, on_recognition_area_selected, monitor)

def show_positions_on_screen():
    # 전체 모니터 정보 가져오기
    monitors = get_monitors()
    min_x = min(monitor.x for monitor in monitors)
    min_y = min(monitor.y for monitor in monitors)
    max_x = max(monitor.x + monitor.width for monitor in monitors)
    max_y = max(monitor.y + monitor.height for monitor in monitors)

    total_width = max_x - min_x
    total_height = max_y - min_y

    # 투명 윈도우 생성
    top = tk.Toplevel(app)
    top.geometry(f"{total_width}x{total_height}+0+0")
    top.attributes("-topmost", True)
    top.overrideredirect(True)
    top.attributes("-alpha", 0.25)  # 반투명 정도 조정
    top.config(bg="black")

    canvas = tk.Canvas(top, width=total_width, height=total_height, bg="black")
    canvas.pack()

    colors = {
        "buy": "lime",
        "sell": "red",
        "close": "yellow",
    }
    radius = 10

    # 좌표 원 그리기
    for key in ("buy", "sell", "close"):
        pos = positions.get(key)
        if pos:
            x, y = pos
            # 전체 스크린 좌표 -> 캔버스 좌표로 변환
            cx, cy = x - min_x, y - min_y
            canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                               outline=colors[key], width=3)
            canvas.create_text(cx, cy - 15, text=key, fill=colors[key], font=("Arial", 14, "bold"))

    # 인식 영역 사각형 그리기
    rec = positions.get("recognition_area")
    if rec:
        x, y, w, h = rec
        cx, cy = x - min_x, y - min_y
        canvas.create_rectangle(cx, cy, cx + w, cy + h, outline="cyan", width=3)
        canvas.create_text(cx + w//2, cy - 15, text="인식범위", fill="cyan", font=("Arial", 14, "bold"))

    # ESC 또는 클릭시 닫기
    top.bind("<Escape>", lambda e: top.destroy())
    top.bind("<Button-1>", lambda e: top.destroy())


# UI 및 설정
app = ctk.CTk()
app.geometry("420x460")
app.title("민규와 상우의 100조부자 열쇠")

def toggle_settings():
    if setting_frame.winfo_ismapped():
        setting_frame.pack_forget()
    else:
        setting_frame.pack(pady=10)

trade_frame = ctk.CTkFrame(app)
trade_frame.pack(pady=20)

start_button = ctk.CTkButton(trade_frame, text="매매 시작", width=120, height=40, command=start_trading_thread)
start_button.pack(side="left", padx=10)
stop_button = ctk.CTkButton(trade_frame, text="매매 종료", width=120, height=40, command=stop_trading)
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
ctk.CTkButton(setting_frame, text="좌표 확인", width=320, height=40, command=show_positions_on_screen).pack(pady=5)

time_start_frame = ctk.CTkFrame(setting_frame)
time_start_frame.pack(pady=(10, 5))

ctk.CTkLabel(time_start_frame, text="시작 시간", width=100).pack(side="left", padx=5)

hours = [f"{h:02d}" for h in range(24)]
minutes = [f"{m:02d}" for m in range(60)]

start_hour_combo = ctk.CTkComboBox(time_start_frame, values=hours, width=60, state='readonly')
start_hour_combo.set("09")
start_hour_combo.pack(side="left", padx=(0, 5))

ctk.CTkLabel(time_start_frame, text=":").pack(side="left")

start_minute_combo = ctk.CTkComboBox(time_start_frame, values=minutes, width=60, state='readonly')
start_minute_combo.set("00")
start_minute_combo.pack(side="left", padx=(5, 0))

time_end_frame = ctk.CTkFrame(setting_frame)
time_end_frame.pack(pady=5)

ctk.CTkLabel(time_end_frame, text="종료 시간", width=100).pack(side="left", padx=5)

end_hour_combo = ctk.CTkComboBox(time_end_frame, values=hours, width=60, state='readonly')
end_hour_combo.set("15")
end_hour_combo.pack(side="left", padx=(0, 5))

ctk.CTkLabel(time_end_frame, text=":").pack(side="left")

end_minute_combo = ctk.CTkComboBox(time_end_frame, values=minutes, width=60, state='readonly')
end_minute_combo.set("00")
end_minute_combo.pack(side="left", padx=(5, 0))

apply_time_button = ctk.CTkButton(setting_frame, text="시간 적용", width=320, height=40, command=apply_time_settings)
apply_time_button.pack(pady=10)


# 저장된 값으로 UI 업데이트
load_positions_from_file()
update_time_ui()

app.mainloop()
