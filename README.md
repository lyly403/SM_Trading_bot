# SM_Trading_bot
SM Trillion Access Key

1. 인식 범위(영역) 지속 감시
- recognition_area 영역의 스크린샷을 계속 분석
2. 색삭 매칭
- 	buy, sell, close 색상을 recognition_area에서 찾음
3. 행위 
- 	색상에 따라 마우스 클릭 (좌표: buy, sell, close)
4. 상태 관리
- buy 상태에서는 또 buy 금지
- sell 상태에서는 또 sell 금지
- buy+close 동시 감지되면 buy
- sell+close 동시 감지되면 sell
5. 시간 제한
	start_time ~ end_time 사이에만 감시 수행