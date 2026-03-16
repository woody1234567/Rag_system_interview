import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from app.main import app

def test_upload_success(monkeypatch, tmp_path):
    # Mock RagService.requirements_dir() to return a temp dir
    monkeypatch.setattr("app.api.v1.rag.RagService.requirements_dir", lambda: tmp_path)
    
    c = TestClient(app)
    
    # Create a dummy PDF file
    file_content = b"%PDF-1.4 dummy pdf content"
    files = {"file": ("test_doc.pdf", file_content, "application/pdf")}
    
    r = c.post("/v1/rag/upload", files=files)
    assert r.status_code == 200
    assert r.json()["filename"] == "test_doc.pdf"
    
    # Verify file was written
    uploaded_file = tmp_path / "test_doc.pdf"
    assert uploaded_file.exists()
    assert uploaded_file.read_bytes() == file_content

def test_upload_invalid_type(monkeypatch, tmp_path):
    monkeypatch.setattr("app.api.v1.rag.RagService.requirements_dir", lambda: tmp_path)
    
    c = TestClient(app)
    files = {"file": ("test_doc.txt", b"plain text", "text/plain")}
    
    r = c.post("/v1/rag/upload", files=files)
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "INVALID_FILE_TYPE"

def test_index_empty_requirements(monkeypatch, tmp_path):
    # Mock project_root so that requirements dir points to our empty tmp_path
    monkeypatch.setattr("app.api.v1.rag.RagService.requirements_dir", lambda: tmp_path)
    # Also need to mock project_root within langchain_rag's core since build_index calls it
    monkeypatch.setattr("app.services.rag_service.RagService._import_core", lambda: (
        lambda *args: {}, # mock query
        lambda: _mock_build_index(tmp_path) # mock build index
    ))
    
    def _mock_build_index(path):
        pdf_files = list(path.glob("*.pdf"))
        if not pdf_files:
            raise ValueError("NO_PDF_FOUND")
        return len(pdf_files)
        
    c = TestClient(app)
    r = c.post("/v1/rag/index")
    
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "NO_PDF_FOUND"
