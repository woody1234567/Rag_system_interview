from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1.rag import router as rag_router

app = FastAPI(title="RAG Demo FastAPI", version="0.1.0")

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
