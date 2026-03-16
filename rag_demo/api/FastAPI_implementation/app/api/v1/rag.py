import shutil

from fastapi import APIRouter, HTTPException, UploadFile

from ...schemas.rag import ClearResponse, IndexResponse, PingResponse, QueryRequest, QueryResponse, UploadResponse
from ...services.rag_service import RagService, RagServiceError

router = APIRouter(prefix="/v1/rag", tags=["rag"])

ALLOWED_EXTENSIONS = {".pdf"}

@router.post("/ping", response_model=PingResponse)
def ping() -> PingResponse:
    RagService.ping()
    return PingResponse(status="ok")

@router.post("/clear", response_model=ClearResponse)
def clear() -> ClearResponse:
    RagService.clear_requirements()
    return ClearResponse(status="ok")


@router.post("/query", response_model=QueryResponse)
def query(payload: QueryRequest) -> QueryResponse:
    try:
        result = RagService.query(payload.question, payload.question_type)
    except RagServiceError as e:
        raise HTTPException(status_code=500, detail={"code": "RAG_QUERY_ERROR", "message": str(e)})

    retrieval_debug = result.get("retrieval_debug") if payload.include_debug else None
    return QueryResponse(
        answer=result.get("answer", ""),
        refusal=bool(result.get("refusal", False)),
        reason=result.get("reason", ""),
        sources=result.get("sources", []),
        gate=result.get("gate"),
        retrieval_debug=retrieval_debug,
    )


@router.post("/index", response_model=IndexResponse)
def index() -> IndexResponse:
    try:
        chunks = RagService.build_index()
    except RagServiceError as e:
        err_msg = str(e)
        if "NO_PDF_FOUND" in err_msg:
            raise HTTPException(
                status_code=400, detail={"code": "NO_PDF_FOUND", "message": "尚未上傳任何檔案，無法建立索引"}
            )
        code = "INDEX_BUILD_IN_PROGRESS" if err_msg == "INDEX_BUILD_IN_PROGRESS" else "RAG_INDEX_ERROR"
        status = 409 if code == "INDEX_BUILD_IN_PROGRESS" else 500
        raise HTTPException(status_code=status, detail={"code": code, "message": err_msg})
    return IndexResponse(chunks=chunks)


@router.post("/upload", response_model=UploadResponse)
def upload(file: UploadFile) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail={"code": "NO_FILENAME", "message": "檔案名稱不得為空"})

    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_FILE_TYPE", "message": f"只允許上傳以下類型的檔案: {', '.join(ALLOWED_EXTENSIONS)}"},
        )

    dest_dir = RagService.requirements_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / file.filename

    try:
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "UPLOAD_FAILED", "message": str(e)})

    return UploadResponse(filename=file.filename)
