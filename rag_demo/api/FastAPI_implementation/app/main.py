import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1.rag import router as rag_router
from .services.rag_service import RagService


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start cleanup background task
    task = asyncio.create_task(cleanup_task())
    yield
    # Shutdown: cancel task
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def cleanup_task():
    while True:
        await asyncio.sleep(60)  # Check every minute
        now = time.time()
        # 10 minutes timeout (600 seconds)
        if now - RagService.last_active_time > 600:
            RagService.clear_requirements()


app = FastAPI(title="RAG Demo FastAPI", version="0.1.0", lifespan=lifespan)

# 設定 CORS 允許前端跨域請求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允許所有來源，部署上線建議改為前端的實際網址
    allow_credentials=True,
    allow_methods=["*"],  # 允許所有 HTTP 方法 (GET, POST, OPTIONS, 等)
    allow_headers=["*"],  # 允許所有 Header
)

app.include_router(rag_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    return {"status": "ready"}
