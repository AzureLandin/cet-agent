from __future__ import annotations

import io
import json
import os
import re
import zipfile
from typing import Any

import httpx
from services.http_client import create_httpx_client

VALID_MODULES = {"writing", "reading", "translation"}
VALID_SUB_TYPES = {
    "writing": {"essay", "chart_essay", "letter"},
    "reading": {"banked_cloze", "matching", "careful_reading"},
    "translation": {"paragraph_translation"},
}
DEFAULT_SUB_TYPE = {
    "writing": "essay",
    "reading": "careful_reading",
    "translation": "paragraph_translation",
}


class MinerUError(RuntimeError):
    """Raised when MinerU Cloud API returns an error or malformed response."""


class MinerUClient:
    def __init__(self, config: dict | None = None):
        cfg = config or {}
        self.api_key = (cfg.get("api_key") or "").strip()
        self.base_url = (cfg.get("base_url") or "https://mineru.net/api/v4").rstrip("/")
        self.timeout = float(cfg.get("timeout", 60.0))

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def upload_and_create_task(self, file_path: str, filename: str | None = None) -> dict[str, Any]:
        """Upload a local PDF to MinerU Cloud via presigned URL or read MD/TXT directly."""
        fname = filename or os.path.basename(file_path)
        ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""

        if ext in {"md", "markdown", "txt"}:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                raw_md = f.read()
            return {
                "task_id": None,
                "status": "draft",
                "raw_markdown": raw_md,
            }

        if not self.is_configured():
            return {
                "task_id": None,
                "status": "draft",
                "raw_markdown": "",
                "message": "CET_MINERU_API_KEY is not configured; paste raw_markdown manually to parse.",
            }

        presign_url = f"{self.base_url}/file-urls/batch"
        payload = {
            "enable_formula": False,
            "language": "en",
            "files": [{"name": fname, "is_ocr": True}],
        }
        with create_httpx_client(timeout=self.timeout) as client:
            res = client.post(presign_url, headers=self._headers(), json=payload)
            res.raise_for_status()
            body = res.json()
            if body.get("code") not in (0, None):
                raise MinerUError(body.get("msg") or f"MinerU presign error: {body}")

            data = body.get("data") or {}
            batch_id = data.get("batch_id")
            file_urls = data.get("file_urls") or []
            if not batch_id or not file_urls:
                raise MinerUError("MinerU presign response missing batch_id or file_urls.")

            with open(file_path, "rb") as f:
                file_bytes = f.read()

            put_res = client.put(file_urls[0], content=file_bytes)
            put_res.raise_for_status()

        return {
            "task_id": f"batch:{batch_id}",
            "batch_id": batch_id,
            "status": "parsing",
        }

    def create_extract_task(self, file_url: str, is_ocr: bool = True) -> dict[str, Any]:
        """Create an extraction task from a public PDF URL via POST /extract/task."""
        if not self.is_configured():
            raise MinerUError("CET_MINERU_API_KEY is required for remote URL extraction.")

        url = f"{self.base_url}/extract/task"
        payload = {"url": file_url, "is_ocr": is_ocr, "language": "en"}
        with create_httpx_client(timeout=self.timeout) as client:
            res = client.post(url, headers=self._headers(), json=payload)
            res.raise_for_status()
            body = res.json()
            if body.get("code") not in (0, None):
                raise MinerUError(body.get("msg") or f"MinerU task creation error: {body}")
            data = body.get("data") or {}
            task_id = data.get("task_id")
            if not task_id:
                raise MinerUError("MinerU response missing task_id.")
            return {"task_id": task_id, "status": "parsing"}

    def get_task_result(self, task_id: str) -> dict[str, Any]:
        """Poll MinerU task/batch status and download extracted markdown when done."""
        if not self.is_configured():
            raise MinerUError("CET_MINERU_API_KEY is not configured.")

        if task_id.startswith("batch:"):
            batch_id = task_id.split(":", 1)[1]
            url = f"{self.base_url}/extract-results/batch/{batch_id}"
        else:
            url = f"{self.base_url}/extract/task/{task_id}"

        with create_httpx_client(timeout=self.timeout) as client:
            res = client.get(url, headers=self._headers())
            res.raise_for_status()
            body = res.json()
            if body.get("code") not in (0, None):
                raise MinerUError(body.get("msg") or f"MinerU status error: {body}")

            data = body.get("data") or {}
            # Batch endpoint returns {"extract_result": [{...}]}
            if "extract_result" in data and isinstance(data["extract_result"], list):
                item = data["extract_result"][0] if data["extract_result"] else {}
            else:
                item = data

            state = (item.get("state") or item.get("status") or "").lower()
            if state in {"pending", "running", "converting", "waiting-file", "processing"}:
                return {"status": "parsing", "state": state}
            if state in {"failed", "error"}:
                return {
                    "status": "failed",
                    "error_message": item.get("err_msg") or item.get("error_message") or "MinerU parsing failed.",
                }
            if state in {"done", "success", "completed"} or item.get("full_zip_url") or item.get("markdown"):
                if item.get("markdown"):
                    return {"status": "done", "raw_markdown": item["markdown"]}
                if item.get("md_url"):
                    md_res = client.get(item["md_url"])
                    md_res.raise_for_status()
                    return {"status": "done", "raw_markdown": md_res.text}
                if item.get("full_zip_url"):
                    md_text = self._download_markdown_from_zip(client, item["full_zip_url"])
                    return {"status": "done", "raw_markdown": md_text}
                raise MinerUError("MinerU task finished but no markdown or zip URL was returned.")

            return {"status": "parsing", "state": state or "unknown"}

    def _download_markdown_from_zip(self, client: httpx.Client, zip_url: str) -> str:
        res = client.get(zip_url)
        res.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
            names = zf.namelist()
            md_names = [n for n in names if n.lower().endswith(".md")]
            if not md_names:
                raise MinerUError("MinerU result archive contains no markdown files.")
            preferred = next((n for n in md_names if os.path.basename(n).lower() == "full.md"), md_names[0])
            return zf.read(preferred).decode("utf-8", errors="replace")


EXTRACTION_SYSTEM_PROMPT = """你是一位四六级（CET-4/CET-6）真题结构化解析专家。
请从提供的真题 Markdown 文本中提取所有可识别的题目，并输出严格合法的 JSON 对象：{"questions": [...]}。

每个题目对象必须包含以下字段：
- exam_level: "CET4" 或 "CET6"
- module: "writing" | "reading" | "translation"
- sub_type:
  - writing 模块: "essay" | "chart_essay" | "letter"
  - reading 模块: "banked_cloze" (选词填空) | "matching" (长篇阅读信息匹配) | "careful_reading" (仔细阅读)
  - translation 模块: "paragraph_translation"
- title: 简明中文标题，如 "2024年6月 CET-6 仔细阅读 Passage 1"
- topic: 英文蛇形主题标签，如 "technology_and_society"
- content: 仅含题面（不含答案与解析）的结构化 JSON：
  - writing: {"directions": "...", "prompt": "...", "word_limit": "120-180", "image_url": null}
  - translation: {"directions": "...", "source_text": "...", "hints": []}
  - careful_reading: {"directions": "...", "passage": "...", "questions": [{"number": 46, "stem": "...", "options": {"A": "...", "B": "...", "C": "...", "D": "..."}}]}
  - banked_cloze: {"directions": "...", "passage": "...", "blank_numbers": [26, ...], "word_bank": {"A": "...", ...}}
  - matching: {"directions": "...", "paragraphs": [{"label": "A", "text": "..."}], "statements": [{"number": 36, "text": "..."}]}
- answer: 答案与解析 JSON（若原文未包含答案，保留空字典或基于原文给出标注）：
  - reading: {"correct_answers": {"46": "B", ...}, "explanations": {"46": "..."}}
  - writing: {"reference_essay": "...", "key_points": [...], "scoring_criteria": "..."}
  - translation: {"reference_translation": "...", "key_vocabulary": [{"zh": "...", "en": "..."}], "grammar_notes": "..."}

只输出 JSON，不要附加任何解释或 Markdown 之外的废话。"""


def _strip_json_fences(text: str) -> str:
    cleaned = text.strip()
    fence_match = re.match(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()
    return cleaned


def _call_model_text(model_client, messages: list[dict]) -> str:
    if hasattr(model_client, "chat_completion"):
        return model_client.chat_completion(messages)
    chunks = list(model_client.chat_completion_stream(messages))
    return "".join(chunks)


def extract_questions_from_markdown(
    model_client,
    raw_markdown: str,
    exam_level: str = "CET4",
    year: int | None = None,
    month: int | None = None,
    set_no: int = 1,
) -> list[dict[str, Any]]:
    """Use the configured LLM to parse raw exam markdown into structured question dicts."""
    if not raw_markdown or not raw_markdown.strip():
        raise ValueError("raw_markdown cannot be empty.")

    user_prompt = (
        f"试卷元信息：exam_level={exam_level or 'CET4'}, year={year}, month={month}, set_no={set_no}。\n"
        "请从以下 Markdown 内容中提取题目并按约定 JSON Schema 返回：\n\n"
        f"{raw_markdown}"
    )
    messages = [
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    raw_output = _call_model_text(model_client, messages)
    cleaned = _strip_json_fences(raw_output)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model returned invalid JSON while extracting questions: {exc}") from exc

    if isinstance(parsed, dict):
        items = parsed.get("questions") or parsed.get("items") or []
    elif isinstance(parsed, list):
        items = parsed
    else:
        raise ValueError("Unexpected JSON structure returned by question extractor.")

    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        module = str(item.get("module") or "").strip().lower()
        if module not in VALID_MODULES:
            continue
        sub_type = str(item.get("sub_type") or "").strip().lower()
        if sub_type not in VALID_SUB_TYPES[module]:
            sub_type = DEFAULT_SUB_TYPE[module]

        level = str(item.get("exam_level") or exam_level or "CET4").upper()
        if level not in {"CET4", "CET6"}:
            level = exam_level if exam_level in {"CET4", "CET6"} else "CET4"

        content = item.get("content")
        if not isinstance(content, dict):
            content = {}
        answer = item.get("answer")
        if not isinstance(answer, dict):
            answer = {}

        title = (item.get("title") or "").strip() or f"{level} {module} #{idx}"
        topic = (item.get("topic") or "").strip() or None

        normalized.append(
            {
                "exam_level": level,
                "module": module,
                "sub_type": sub_type,
                "year": item.get("year") if item.get("year") is not None else year,
                "month": item.get("month") if item.get("month") is not None else month,
                "set_no": item.get("set_no") if item.get("set_no") is not None else set_no,
                "title": title,
                "topic": topic,
                "content": content,
                "answer": answer,
            }
        )

    return normalized
