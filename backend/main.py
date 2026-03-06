from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from core.config import settings
from core.database import Base, engine
from api import users, market, strategies, trading, broker, dashboard, ai

# DB 테이블 생성
Base.metadata.create_all(bind=engine)

# 신규 컬럼 마이그레이션 (ADD COLUMN IF NOT EXISTS — 멱등)
_MIGRATIONS = [
    "ALTER TABLE executions ADD COLUMN IF NOT EXISTS profit_loss_pct DECIMAL(7,4)",
    "ALTER TABLE bot_reports ADD COLUMN IF NOT EXISTS max_drawdown DECIMAL(8,4)",
    "ALTER TABLE bot_reports ADD COLUMN IF NOT EXISTS sharpe_ratio DECIMAL(8,4)",
    "ALTER TABLE bot_reports ADD COLUMN IF NOT EXISTS profit_factor DECIMAL(8,4)",
    "ALTER TABLE strategies ADD COLUMN IF NOT EXISTS strategy_type VARCHAR(20) DEFAULT 'swing'",
]
with engine.connect() as conn:
    for stmt in _MIGRATIONS:
        conn.execute(text(stmt))
    conn.commit()

app = FastAPI(title="AutoStock API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(users.router, prefix="/api/v1")
app.include_router(market.router, prefix="/api/v1")
app.include_router(strategies.router, prefix="/api/v1")
app.include_router(trading.router, prefix="/api/v1")
app.include_router(broker.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(ai.router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
