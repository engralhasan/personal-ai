"""
File Management & Document Intelligence Tools.
Enables local file search, creation, text extraction from PDF/DOCX/TXT/Code,
directory organization, and high-risk deletion with Confirmation Gate.
"""

from __future__ import annotations
import os
import shutil
from pathlib import Path
import logging
from typing import Optional, List, Dict, Any
from config import RiskLevel
from core.security import RiskLevel

logger = logging.getLogger("JARVIS.Tools.File")


def search_files(directory: str, pattern: str = "*.*", max_results: int = 15) -> str:
    """
    Searches for files matching a pattern (e.g., '*.pdf', '*invoice*', '*.py') in a folder.
    """
    try:
        base = Path(directory).expanduser().resolve()
        if not base.exists():
            return f"Directory does not exist: {directory}"

        matches = []
        for p in base.rglob(pattern):
            if p.is_file():
                matches.append(str(p))
                if len(matches) >= max_results:
                    break

        if not matches:
            return f"No files matching '{pattern}' found in '{directory}'."

        return f"Found {len(matches)} match(es):\n" + "\n".join(f"- {m}" for m in matches)
    except Exception as e:
        return f"File search error: {str(e)}"


def read_file_content(file_path: str, max_chars: int = 4000) -> str:
    """
    Reads the content of text, code, PDF, or Word DOCX files.
    """
    try:
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            return f"File not found: {file_path}"

        suffix = path.suffix.lower()

        # Handle PDF files
        if suffix == ".pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(str(path))
                text = ""
                for page in reader.pages[:10]: # Read up to first 10 pages
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"
                clean_text = text.strip()[:max_chars]
                return f"[PDF Content: {path.name} (pages: {len(reader.pages)})]\n{clean_text}"
            except Exception as e:
                return f"Error reading PDF file: {str(e)}"

        # Handle Word DOCX files
        elif suffix in [".docx", ".doc"]:
            try:
                import docx
                doc = docx.Document(str(path))
                full_text = [para.text for para in doc.paragraphs if para.text.strip()]
                extracted = "\n".join(full_text)[:max_chars]
                return f"[DOCX Content: {path.name}]\n{extracted}"
            except Exception as e:
                return f"Error reading DOCX file: {str(e)}"

        # Standard text, code, json, markdown
        else:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(max_chars)
            return f"[File: {path.name}]\n{content}"

    except Exception as e:
        return f"Error opening file: {str(e)}"


def write_file_content(file_path: str, content: str, mode: str = "w") -> str:
    """
    Creates or overwrites a local file with the provided text content.
    """
    try:
        path = Path(file_path).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, mode, encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote {len(content)} characters to '{path.name}'."
    except Exception as e:
        return f"Failed to write to file: {str(e)}"


def delete_file(file_path: str) -> str:
    """
    Deletes a file or directory permanently.
    HIGH RISK: Strictly protected by the Human-in-the-Loop Confirmation Gate.
    """
    try:
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            return f"Cannot delete: File does not exist at {file_path}"

        if path.is_file():
            path.unlink()
            return f"File '{path.name}' successfully deleted."
        elif path.is_dir():
            shutil.rmtree(path)
            return f"Directory '{path.name}' and all contents successfully deleted."
        return f"Unknown file system entity: {file_path}"
    except Exception as e:
        return f"Failed to delete '{file_path}': {str(e)}"


def organize_directory(directory: str) -> str:
    """
    Cleans and organizes files in a folder into category folders:
    Documents, Images, Audio, Video, Archives, Code, Other.
    """
    try:
        base = Path(directory).expanduser().resolve()
        if not base.exists() or not base.is_dir():
            return f"Invalid directory: {directory}"

        extension_map = {
            "Documents": [".pdf", ".docx", ".doc", ".txt", ".xlsx", ".pptx", ".csv"],
            "Images": [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp"],
            "Audio": [".mp3", ".wav", ".aac", ".flac", ".m4a"],
            "Video": [".mp4", ".mkv", ".mov", ".avi", ".flv"],
            "Archives": [".zip", ".tar", ".gz", ".7z", ".rar"],
            "Code": [".py", ".js", ".ts", ".html", ".css", ".cpp", ".java", ".json"]
        }

        moved_count = 0
        for item in base.iterdir():
            if item.is_file():
                ext = item.suffix.lower()
                target_folder_name = "Other"
                for folder, exts in extension_map.items():
                    if ext in exts:
                        target_folder_name = folder
                        break

                target_dir = base / target_folder_name
                target_dir.mkdir(exist_ok=True)
                dest = target_dir / item.name

                # Avoid collision
                if dest.exists():
                    dest = target_dir / f"{item.stem}_{int(dest.stat().st_mtime)}{item.suffix}"

                shutil.move(str(item), str(dest))
                moved_count += 1

        return f"Organized directory '{base.name}': Sorted {moved_count} file(s) into subfolders."
    except Exception as e:
        return f"Error organizing directory: {str(e)}"


# Register with Tool Registry
from tools import registry

registry.register("search_files", "Searches for files matching wildcard patterns in a folder.", RiskLevel.READ_ONLY)(search_files)
registry.register("read_file_content", "Reads content of text, code, PDF, or Word DOCX documents.", RiskLevel.READ_ONLY)(read_file_content)
registry.register("write_file_content", "Writes or appends text to a specified file.", RiskLevel.SAFE_EXECUTION)(write_file_content)
registry.register(
    "delete_file",
    "Permanently deletes a file or directory. HIGH RISK: Requires user confirmation.",
    RiskLevel.HIGH_RISK_DESTRUCTIVE,
    requires_confirmation=True
)(delete_file)
registry.register("organize_directory", "Sorts and organizes files in a directory by type.", RiskLevel.SAFE_EXECUTION)(organize_directory)
