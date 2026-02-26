from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from core.database import Base, engine
from api import users, market, strategies, trading, broker, dashboard, ai

# DB 테이블 생성
Base.metadata.create_all(bind=engine)

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
