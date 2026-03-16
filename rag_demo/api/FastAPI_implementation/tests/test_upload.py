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
