# ============================================================
# app.py — stock_advisor_pro 실행 진입점
# 실행: streamlit run app.py --server.port 8503
# ============================================================

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

# dashboard.py의 모든 코드를 이 모듈 컨텍스트에서 실행
_dashboard = os.path.join(os.path.dirname(__file__), "ui", "dashboard.py")
with open(_dashboard, encoding="utf-8") as _f:
    exec(compile(_f.read(), _dashboard, "exec"), {"__name__": "__main__", "__file__": _dashboard})
