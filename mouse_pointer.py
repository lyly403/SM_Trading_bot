from pynput.mouse import Listener

# 마우스 위치를 출력하는 함수
def on_move(x, y):
    print(f"Mouse moved to ({x}, {y})")

# 프로그램 종료 시 실행되는 함수
def on_stop():
    print("Listener stopped.")
    
# 마우스 리스너 시작
with Listener(on_move=on_move, on_stop=on_stop) as listener:
    try:
        listener.join()  # 이 부분이 listener를 실행시킴
    except KeyboardInterrupt:  # Ctrl+C를 누르면 종료
        listener.stop()  # 리스너 종료
        print("Program terminated.")