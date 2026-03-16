from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any


class RagServiceError(Exception):
    pass


class RagService:
    _index_lock = Lock()

    @staticmethod
    def requirements_dir() -> Path:
        here = Path(__file__).resolve()
        api_root = here.parents[2]  # .../FastAPI_implementation
        return api_root / "requirements"

    @staticmethod
    def _import_core():
        import sys

        here = Path(__file__).resolve()
        api_root = here.parents[2].parent  # .../rag_demo/api
        src_path = api_root / "langchain_rag" / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from langchain_rag_app.core import answer_question, build_index  # type: ignore

        return answer_question, build_index

    @classmethod
    def query(cls, question: str, question_type: str | None = None) -> dict[str, Any]:
        try:
            answer_question, _ = cls._import_core()
            return answer_question(question, question_type or "")
        except Exception as e:  # pragma: no cover
            raise RagServiceError(str(e)) from e

    @classmethod
    def build_index(cls) -> int:
        if not cls._index_lock.acquire(blocking=False):
            raise RagServiceError("INDEX_BUILD_IN_PROGRESS")
        try:
            _, build_index = cls._import_core()
            return int(build_index())
        except Exception as e:  # pragma: no cover
            raise RagServiceError(str(e)) from e
        finally:
            cls._index_lock.release()
