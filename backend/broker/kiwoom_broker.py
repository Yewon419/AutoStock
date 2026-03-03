# DEPRECATED: 키움 브릿지는 Docker 불호환(32-bit PyQt5)으로 제거되었습니다.
# Phase 5에서 KIS(한국투자증권) REST+WebSocket으로 전면 교체.
# 사용처: broker/factory.py → KisBroker
raise ImportError("kiwoom_broker is deprecated. Use kis_broker instead.")
