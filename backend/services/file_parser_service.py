"""
File Parser Service - handles file parsing using MinerU service and image captioning
"""
import os
import re
import time
import logging
import zipfile
import io
import requests
import tempfile
import uuid
from typing import Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from PIL import Image
from markitdown import MarkItDown
from services.ai_providers.text import strip_think_tags
from services.prompt_registry import prompt_registry

logger = logging.getLogger(__name__)


def _get_ai_provider_format(provider_format: str = None) -> str:
    """Get the configured AI provider format
    
    Priority:
        1. Provided provider_format parameter
        2. Flask app.config['AI_PROVIDER_FORMAT'] (from database settings)
        3. Environment variable AI_PROVIDER_FORMAT
        4. Default: 'gemini'
    
    Args:
        provider_format: Optional provider format string. If not provided, reads from Flask config or environment variable.
    """
    if provider_format:
        return provider_format.lower()
    
    # Try to get from Flask app config first (database settings)
    try:
        from flask import current_app
        if current_app and hasattr(current_app, 'config'):
            config_value = current_app.config.get('AI_PROVIDER_FORMAT')
            if config_value:
                return str(config_value).lower()
    except RuntimeError:
        # Not in Flask application context
        pass
    
    # Fallback to environment variable
    return os.getenv('AI_PROVIDER_FORMAT', 'gemini').lower()


class FileParserService:
    """Service for parsing files using MinerU and enhancing with image captions"""

    _MINERU_ENDPOINT_SUFFIXES = (
        "/api/v4/extract/task",
        "/api/v4/file-urls/batch",
        "/api/v4/extract-results/batch",
    )
    
    def __init__(self, mineru_token: str = "", mineru_api_base: str = "",
                 google_api_key: str = "", google_api_base: str = "",
                 openai_api_key: str = "", openai_api_base: str = "",
                 image_caption_model: str = "gemini-3-flash-preview",
                 lazyllm_image_caption_source: str = "", 
                 provider_format: str = None,
                 mineru_model_version: str = "vlm",
                 mineru_provider: str = None,
                 local_api_base: str = None,
                 local_backend: str = None,
                 local_parse_method: str = None,
                 local_return_images: bool = None,
                 local_response_format_zip: bool = None,
                 local_return_original_file: bool = None,
                 caption_provider = None,
                 **_ignored_kwargs,
                 ):
        """
        Initialize the file parser service
        
        Args:
            mineru_token: MinerU API token
            mineru_api_base: MinerU API base URL
            google_api_key: Google Gemini API key for image captioning (used when AI_PROVIDER_FORMAT=gemini)
            google_api_base: Google Gemini API base URL
            openai_api_key: OpenAI API key for image captioning (used when AI_PROVIDER_FORMAT=openai)
            openai_api_base: OpenAI API base URL
            image_caption_model: Model to use for image captioning
            lazyllm_image_caption_source: image caption model provider for lazyllm
            provider_format: AI provider format ('gemini' or 'openai'). If not provided, reads from environment variable.
            mineru_model_version: MinerU model version ('vlm' or 'pipeline'). Default is 'vlm'.
        """
        self.mineru_token = mineru_token
        explicit_mineru_api_base = bool((mineru_api_base or "").strip())
        self.mineru_api_base = self.normalize_mineru_api_base(mineru_api_base or "https://mineru.net")
        self.mineru_model_version = mineru_model_version
        self.mineru_provider = (mineru_provider or os.getenv("MINERU_PROVIDER", "cloud")).lower()
        local_base = local_api_base or os.getenv("MINERU_LOCAL_API_BASE", "http://127.0.0.1:7860")
        if self.mineru_provider == "local" and explicit_mineru_api_base:
            local_base = self.mineru_api_base
        self.local_api_base = self.normalize_mineru_api_base(local_base)
        self.local_backend = local_backend or os.getenv("MINERU_LOCAL_BACKEND", "pipeline")
        self.local_parse_method = local_parse_method or os.getenv("MINERU_LOCAL_PARSE_METHOD", "auto")
        self.local_return_images = self._coerce_bool(local_return_images, "MINERU_LOCAL_RETURN_IMAGES", True)
        self.local_response_format_zip = self._coerce_bool(local_response_format_zip, "MINERU_LOCAL_RESPONSE_FORMAT_ZIP", True)
        self.local_return_original_file = self._coerce_bool(local_return_original_file, "MINERU_LOCAL_RETURN_ORIGINAL_FILE", False)
        self.get_upload_url_api = f"{self.mineru_api_base}/api/v4/file-urls/batch"
        self.get_result_api_template = f"{self.mineru_api_base}/api/v4/extract-results/batch/{{}}"
        
        self._image_caption_model = image_caption_model
        self._provider_format = _get_ai_provider_format(provider_format)
        # Long-running exports can pin the request's provider here. This keeps
        # MinerU image captions on the same model/key as text-style extraction.
        self._caption_provider = caption_provider

    @staticmethod
    def normalize_mineru_api_base(value: str | None) -> str:
        base = (value or "").strip().rstrip("/")
        for suffix in FileParserService._MINERU_ENDPOINT_SUFFIXES:
            if base.endswith(suffix):
                return base[: -len(suffix)] or base
        return base

    @staticmethod
    def _coerce_bool(value, env_name: str, default: bool) -> bool:
        if value is None:
            value = os.getenv(env_name)
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    
    def _get_caption_provider(self):
        """Lazily initialize caption provider via the provider factory"""
        if self._caption_provider is None:
            from services.ai_providers import get_caption_provider
            self._caption_provider = get_caption_provider(model=self._image_caption_model)
        return self._caption_provider
    
    def _can_generate_captions(self) -> bool:
        """Check if image caption generation is available"""
        try:
            return self._get_caption_provider() is not None
        except (ValueError, ImportError):
            return False
    
    def parse_file(self, file_path: str, filename: str) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str], int]:
        """
        Parse a file using MinerU service and enhance with image captions
        
        Args:
            file_path: Path to the file to parse
            filename: Original filename
            
        Returns:
            Tuple of (batch_id, markdown_content, extract_id, error_message, failed_image_count)
            - batch_id: MinerU batch ID (for tracking, None for text files)
            - markdown_content: Parsed markdown with enhanced image descriptions
            - extract_id: Unique ID for the extracted files directory (None for text files)
            - error_message: Error message if parsing failed
            - failed_image_count: Number of images that failed to generate captions
        """
        try:
            # Check if it's a plain text file that doesn't need MinerU parsing
            file_ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
            
            if file_ext in ['txt', 'md', 'markdown']:
                logger.info(f"File {filename} is a plain text file, reading directly...")
                return self._parse_text_file(file_path, filename)
            
            # Keep legacy/non-local formats on markitdown instead of forcing them through local MinerU.
            if file_ext in ['xls', 'csv'] or (self.mineru_provider != 'local' and file_ext == 'xlsx'):
                logger.info(f"File {filename} is a spreadsheet file, using markitdown...")
                return self._parse_spreadsheet_file(file_path, filename)

            if self.mineru_provider == 'local':
                if file_ext in ['doc', 'ppt']:
                    logger.info(f"File {filename} uses a legacy Office format, using markitdown...")
                    return self._parse_spreadsheet_file(file_path, filename)
                logger.info(f"File {filename} requires local MinerU parsing...")
                batch_id, markdown_content, extract_id, error, failed_count = self._parse_file_with_local_mineru(file_path, filename)
                if error or not markdown_content:
                    return batch_id, markdown_content, extract_id, error, failed_count

                if self._can_generate_captions():
                    enhanced_content, failed_count = self._enhance_markdown_with_captions(markdown_content)
                    return batch_id, enhanced_content, extract_id, None, failed_count

                return batch_id, markdown_content, extract_id, None, failed_count
            
            # For other file types, use MinerU service
            logger.info(f"File {filename} requires MinerU parsing...")
            
            # Step 1: Get upload URL
            logger.info(f"Step 1/4: Requesting upload URL for {filename}...")
            batch_id, upload_url, error = self._get_upload_url(filename)
            if error:
                return None, None, None, error, 0
            
            logger.info(f"Got upload URL. Batch ID: {batch_id}")
            
            # Step 2: Upload file
            logger.info(f"Step 2/4: Uploading file {filename}...")
            error = self._upload_file(file_path, upload_url)
            if error:
                return batch_id, None, None, error, 0
            
            logger.info("File uploaded successfully.")
            
            # Step 3: Poll for parsing result
            logger.info("Step 3/4: Waiting for parsing to complete...")
            markdown_content, extract_id, error = self._poll_result(batch_id)
            if error:
                return batch_id, None, None, error, 0
            
            logger.info("File parsed successfully.")
            
            # Step 4: Enhance markdown with image captions
            if markdown_content and self._can_generate_captions():
                logger.info("Step 4/4: Enhancing markdown with image captions...")
                enhanced_content, failed_count = self._enhance_markdown_with_captions(markdown_content)
                if failed_count > 0:
                    logger.warning(f"Markdown enhanced with image captions, but {failed_count} images failed to generate captions.")
                else:
                    logger.info("Markdown enhanced with image captions (all images succeeded).")
                return batch_id, enhanced_content, extract_id, None, failed_count
            else:
                logger.info("Skipping image caption enhancement (caption model unavailable).")
                return batch_id, markdown_content, extract_id, None, 0
            
        except Exception as e:
            error_msg = f"Unexpected error during file parsing: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return None, None, None, error_msg, 0

    def _parse_file_with_local_mineru(self, file_path: str, filename: str) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str], int]:
        """Parse a file through the local MinerU Gradio API."""
        try:
            result = self._call_local_mineru_gradio(file_path)
            markdown_content, extract_id, error = self._extract_local_mineru_gradio_result(result)
            return None, markdown_content, extract_id, error, 0
        except ImportError as e:
            error_msg = f"Local MinerU Gradio client is not installed: {str(e)}"
            logger.error(error_msg)
            return None, None, None, error_msg, 0
        except Exception as e:
            error_msg = f"Local MinerU request failed: {str(e)}"
            logger.error(error_msg)
            return None, None, None, error_msg, 0

    def _call_local_mineru_gradio(self, file_path: str):
        """Call MinerU's Gradio convert_to_markdown_stream endpoint."""
        from gradio_client import Client, handle_file

        client = Client(self.local_api_base)
        return client.predict(
            file_path=handle_file(file_path),
            end_pages=int(os.getenv("MINERU_LOCAL_END_PAGES", "1000")),
            is_ocr=self._coerce_bool(None, "MINERU_LOCAL_IS_OCR", False),
            formula_enable=self._coerce_bool(None, "MINERU_LOCAL_FORMULA_ENABLE", True),
            table_enable=self._coerce_bool(None, "MINERU_LOCAL_TABLE_ENABLE", True),
            image_analysis=self._coerce_bool(None, "MINERU_LOCAL_IMAGE_ANALYSIS", True),
            language=os.getenv("MINERU_LOCAL_LANGUAGE", "ch (Chinese, English, Chinese Traditional)"),
            backend=self.local_backend,
            url=os.getenv("MINERU_LOCAL_VLM_URL", "http://localhost:30000"),
            api_name="/convert_to_markdown_stream",
        )

    def _extract_local_mineru_gradio_result(self, result) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """Extract markdown from MinerU Gradio tuple output."""
        if not isinstance(result, (list, tuple)):
            return None, None, f"Unexpected local MinerU response format: {type(result).__name__}"

        output_file = result[1] if len(result) > 1 else None
        md_text = result[3] if len(result) > 3 else None
        output_path = self._get_gradio_file_path(output_file)

        if output_path and output_path.exists() and output_path.is_file():
            try:
                return self._extract_markdown_zip(output_path.read_bytes())
            except OSError as e:
                logger.warning(f"Failed to read local MinerU output file {output_path}: {e}")

        if md_text:
            extract_id = str(uuid.uuid4())[:8]
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent
            mineru_storage = project_root / 'uploads' / 'mineru_files' / extract_id
            mineru_storage.mkdir(parents=True, exist_ok=True)
            markdown_file_path = 'result.md'
            (mineru_storage / markdown_file_path).write_text(str(md_text), encoding='utf-8')
            markdown_content = self._replace_image_paths(str(md_text), markdown_file_path, extract_id)
            return markdown_content, extract_id, None

        status = result[0] if result else ""
        return None, None, f"Local MinerU returned no markdown content. Status: {status}"

    @staticmethod
    def _get_gradio_file_path(value) -> Optional[Path]:
        if isinstance(value, (str, os.PathLike)):
            return Path(value)
        if isinstance(value, dict):
            path = value.get("path") or value.get("name")
            return Path(path) if path else None
        return None
    
    def _parse_text_file(self, file_path: str, filename: str) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str], int]:
        """
        Parse plain text file directly without MinerU
        
        Args:
            file_path: Path to the file
            filename: Original filename
            
        Returns:
            Tuple of (batch_id, markdown_content, extract_id, error_message, failed_image_count)
        """
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            logger.info(f"Text file read successfully: {len(content)} characters")
            
            # Enhance markdown with image captions if it contains images
            if content and self._can_generate_captions():
                # Check if content has markdown images
                if '![' in content and '](' in content:
                    logger.info("Text file contains images, enhancing with captions...")
                    enhanced_content, failed_count = self._enhance_markdown_with_captions(content)
                    if failed_count > 0:
                        logger.warning(f"Text file enhanced with image captions, but {failed_count} images failed to generate captions.")
                    else:
                        logger.info("Text file enhanced with image captions (all images succeeded).")
                    return None, enhanced_content, None, None, failed_count
            
            return None, content, None, None, 0
            
        except UnicodeDecodeError:
            # Try with different encoding
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    content = f.read()
                logger.info(f"Text file read successfully with GBK encoding: {len(content)} characters")
                
                if content and self._can_generate_captions() and '![' in content and '](' in content:
                    logger.info("Text file contains images, enhancing with captions...")
                    enhanced_content, failed_count = self._enhance_markdown_with_captions(content)
                    if failed_count > 0:
                        logger.warning(f"Text file enhanced with image captions, but {failed_count} images failed to generate captions.")
                    else:
                        logger.info("Text file enhanced with image captions (all images succeeded).")
                    return None, enhanced_content, None, None, failed_count
                
                return None, content, None, None, 0
            except Exception as e:
                error_msg = f"Failed to read text file with multiple encodings: {str(e)}"
                logger.error(error_msg)
                return None, None, None, error_msg, 0
        except Exception as e:
            error_msg = f"Failed to read text file: {str(e)}"
            logger.error(error_msg)
            return None, None, None, error_msg, 0
    
    def _parse_spreadsheet_file(self, file_path: str, filename: str) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str], int]:
        """
        Parse spreadsheet files (xlsx, xls, csv) using markitdown
        
        Args:
            file_path: Path to the file
            filename: Original filename
            
        Returns:
            Tuple of (batch_id, markdown_content, extract_id, error_message, failed_image_count)
        """
        try:
            # Use markitdown to convert spreadsheet to markdown
            md = MarkItDown()
            result = md.convert(file_path)
            markdown_content = result.text_content
            
            logger.info(f"Spreadsheet file converted successfully: {len(markdown_content)} characters")
            
            # Spreadsheet files typically don't have images, so no need for caption enhancement
            return None, markdown_content, None, None, 0
            
        except Exception as e:
            error_msg = f"Failed to parse spreadsheet file: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return None, None, None, error_msg, 0
    
    def _get_upload_url(self, filename: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """Get upload URL from MinerU"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.mineru_token}"
        }
        
        upload_data = {
            "files": [{"name": filename}],
            "model_version": self.mineru_model_version  # "vlm" or "pipeline"
        }
        
        try:
            response = requests.post(
                self.get_upload_url_api,
                headers=headers,
                json=upload_data,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            
            if result.get("code") != 0:
                error_msg = f"Failed to get upload URL: {result.get('msg')}"
                logger.error(error_msg)
                return None, None, error_msg
            
            batch_id = result["data"]["batch_id"]
            upload_url = result["data"]["file_urls"][0]
            return batch_id, upload_url, None
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error while requesting upload URL: {str(e)}"
            logger.error(error_msg)
            return None, None, error_msg
    
    def _upload_file(self, file_path: str, upload_url: str) -> Optional[str]:
        """Upload file to MinerU"""
        try:
            with open(file_path, 'rb') as f:
                response = requests.put(
                    upload_url,
                    data=f,
                    headers={"Authorization": None},  # Remove auth for upload
                    timeout=300  # 5 minutes timeout for large files
                )
                response.raise_for_status()
            return None
            
        except requests.exceptions.RequestException as e:
            error_msg = f"File upload failed: {str(e)}"
            logger.error(error_msg)
            return error_msg
        except IOError as e:
            error_msg = f"Failed to read file: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    def _poll_result(self, batch_id: str, max_wait_time: int = 600) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """Poll for parsing result
        
        Returns:
            Tuple of (markdown_content, extract_id, error_message)
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.mineru_token}"
        }
        
        result_url = self.get_result_api_template.format(batch_id)
        start_time = time.time()
        
        while True:
            if time.time() - start_time > max_wait_time:
                error_msg = f"Parsing timeout after {max_wait_time} seconds"
                logger.error(error_msg)
                return None, None, error_msg
            
            try:
                response = requests.get(result_url, headers=headers, timeout=30)
                response.raise_for_status()
                task_info = response.json()
                
                if task_info.get("code") != 0:
                    error_msg = f"Failed to query task status: {task_info.get('msg')}"
                    logger.error(error_msg)
                    return None, None, error_msg
                
                task_status = task_info["data"]["extract_result"][0]["state"]
                
                if task_status == "done":
                    logger.info("File parsing completed!")
                    full_zip_url = task_info["data"]["extract_result"][0]["full_zip_url"]
                    # Download and extract markdown
                    return self._download_markdown(full_zip_url)
                elif task_status == "failed":
                    err_msg = task_info["data"]["extract_result"][0].get("err_msg", "Unknown error")
                    error_msg = f"File parsing failed: {err_msg}"
                    logger.error(error_msg)
                    return None, None, error_msg
                else:
                    logger.debug(f"Current task status: {task_status}, waiting...")
                    time.sleep(2)  # Wait 2 seconds before next poll
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"Network error while polling result: {str(e)}, retrying...")
                time.sleep(2)
    
    def _download_markdown(
        self,
        zip_url: str,
        max_attempts: int = 4,
        retry_delay: float = 2.0,
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """Download and extract markdown from result zip, save images to local server
        
        Returns:
            Tuple of (markdown_content, extract_id, error_message)
        """
        last_error = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = requests.get(zip_url, timeout=120)
                response.raise_for_status()
                markdown_content, extract_id, error = self._extract_markdown_zip(response.content)
                if error and "valid ZIP" in error and attempt < max_attempts:
                    last_error = error
                    logger.warning(
                        "Downloaded MinerU result is not a valid ZIP (attempt %s/%s), retrying...",
                        attempt,
                        max_attempts,
                    )
                    time.sleep(retry_delay * attempt)
                    continue
                return markdown_content, extract_id, error
            except requests.exceptions.RequestException as e:
                last_error = e
                if attempt < max_attempts:
                    logger.warning(
                        "Failed to download MinerU result zip (attempt %s/%s): %s",
                        attempt,
                        max_attempts,
                        str(e),
                    )
                    time.sleep(retry_delay * attempt)
                    continue

                error_msg = f"Failed to download result after {max_attempts} attempts: {str(e)}"
                logger.error(error_msg)
                return None, None, error_msg
            except zipfile.BadZipFile as e:
                last_error = e
                if attempt < max_attempts:
                    logger.warning(
                        "Downloaded MinerU result is not a valid ZIP (attempt %s/%s), retrying...",
                        attempt,
                        max_attempts,
                    )
                    time.sleep(retry_delay * attempt)
                    continue

                error_msg = "Downloaded file is not a valid ZIP archive after retrying"
                logger.error(error_msg)
                return None, None, error_msg
            except Exception as e:
                error_msg = f"Failed to process ZIP file: {str(e)}"
                logger.error(error_msg)
                return None, None, error_msg

        error_msg = f"Failed to download result after {max_attempts} attempts: {str(last_error)}"
        logger.error(error_msg)
        return None, None, error_msg

    def _extract_markdown_zip(self, zip_content: bytes) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """Extract a MinerU ZIP response and return rewritten markdown plus extract id."""
        try:
            extract_id = str(uuid.uuid4())[:8]
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent
            mineru_storage = project_root / 'uploads' / 'mineru_files' / extract_id
            mineru_storage.mkdir(parents=True, exist_ok=True)

            logger.info(f"Extracting ZIP to: {mineru_storage}")

            markdown_content = None
            markdown_file_path = None

            with zipfile.ZipFile(io.BytesIO(zip_content)) as z:
                for member in z.infolist():
                    member_path = Path(member.filename)
                    if member_path.is_absolute() or '..' in member_path.parts:
                        logger.warning(f"Skipping unsafe ZIP member path: {member.filename}")
                        continue
                    z.extract(member, mineru_storage)

                logger.info(f"Extracted {len(z.namelist())} files from ZIP")

                for name in z.namelist():
                    if name.endswith(('.md', '.MD')):
                        member_path = Path(name)
                        if member_path.is_absolute() or '..' in member_path.parts:
                            continue
                        markdown_file_path = name
                        md_full_path = mineru_storage / name
                        with open(md_full_path, 'r', encoding='utf-8') as f:
                            markdown_content = f.read()
                        logger.info(f"Found markdown file: {name}")
                        break

            if markdown_content is None or not markdown_file_path:
                error_msg = "No markdown file found in result zip"
                logger.error(error_msg)
                return None, None, error_msg

            self._promote_markdown_sibling_assets(mineru_storage, markdown_file_path)
            markdown_content = self._replace_image_paths(
                markdown_content,
                markdown_file_path,
                extract_id
            )

            return markdown_content, extract_id, None
        except zipfile.BadZipFile:
            error_msg = "Downloaded file is not a valid ZIP archive"
            logger.error(error_msg)
            return None, None, error_msg
        except Exception as e:
            error_msg = f"Failed to process ZIP file: {str(e)}"
            logger.error(error_msg)
            return None, None, error_msg

    def _promote_markdown_sibling_assets(self, mineru_storage: Path, markdown_file_path: str) -> None:
        """Expose files next to the markdown at extract root so /files/mineru/{id}/images works."""
        md_dir = Path(markdown_file_path).parent
        if str(md_dir) == '.':
            return

        source_dir = mineru_storage / md_dir
        if not source_dir.exists() or not source_dir.is_dir():
            return

        for child in source_dir.iterdir():
            if child.name.lower().endswith('.md'):
                continue

            target = mineru_storage / child.name
            if target.exists():
                continue

            if child.is_dir():
                import shutil
                shutil.copytree(child, target)
            elif child.is_file():
                import shutil
                shutil.copy2(child, target)
    
    @staticmethod
    def extract_header_footer_from_layout(extract_id: str) -> str:
        """
        从 MinerU layout.json 的 discarded_blocks 中提取页眉页脚文本。

        Args:
            extract_id: MinerU 解析结果的 extract_id

        Returns:
            提取到的页眉页脚文本，如无则返回空字符串
        """
        import json
        from pathlib import Path

        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        mineru_dir = project_root / 'uploads' / 'mineru_files' / extract_id
        layout_file = mineru_dir / 'layout.json'

        if not layout_file.exists():
            return ''

        try:
            with open(layout_file, 'r', encoding='utf-8') as f:
                layout_data = json.load(f)

            if 'pdf_info' not in layout_data or not layout_data['pdf_info']:
                return ''

            texts = []
            for page_info in layout_data['pdf_info']:
                for block in page_info.get('discarded_blocks', []):
                    block_type = block.get('type', '')
                    if block_type not in ('header', 'footer'):
                        continue
                    for line in block.get('lines', []):
                        for span in line.get('spans', []):
                            if span.get('type') == 'text' and span.get('content', '').strip():
                                content = span['content'].strip()
                                if content != '#':
                                    texts.append(content)

            return '\n'.join(texts)
        except Exception as e:
            logger.warning(f"Failed to extract header/footer from layout.json: {e}")
            return ''

    def _replace_image_paths(self, markdown_content: str, markdown_file_path: str, extract_id: str) -> str:
        """Replace relative image paths in markdown with local server URLs"""
        import os
        
        # Get the directory where the markdown file is located (within the extracted ZIP)
        md_dir = os.path.dirname(markdown_file_path)
        
        def replace_link(match):
            alt_text = match.group(1)
            img_path = match.group(2)
            
            # Skip if already an absolute URL
            if img_path.startswith(('http://', 'https://')):
                return match.group(0)
            
            # Handle /file/ or /files/ paths (MinerU may generate these)
            # These are relative to the extracted directory
            if img_path.startswith('/file/') or img_path.startswith('/files/'):
                # Remove leading slash and use as relative path
                rel_path = img_path.lstrip('/')
                # Remove 'file/' or 'files/' prefix if present
                if rel_path.startswith('file/'):
                    rel_path = rel_path[5:]  # Remove 'file/' prefix
                elif rel_path.startswith('files/'):
                    rel_path = rel_path[6:]  # Remove 'files/' prefix
            else:
                # Calculate the relative path from the markdown file
                if md_dir:
                    # Normalize path separators
                    rel_path = os.path.normpath(os.path.join(md_dir, img_path)).replace('\\', '/')
                else:
                    rel_path = img_path.replace('\\', '/')
            
            rel_path = self._normalize_mineru_asset_path(rel_path)
            new_url = f"/files/mineru/{extract_id}/{rel_path}"
            
            logger.debug(f"Replacing image path: {img_path} -> {new_url}")
            return f"![{alt_text}]({new_url})"
        
        # Match markdown image syntax
        pattern = r"!\[(.*?)\]\((.*?)\)"
        replaced_content = re.sub(pattern, replace_link, markdown_content)
        
        return replaced_content

    @staticmethod
    def _normalize_mineru_asset_path(rel_path: str) -> str:
        """Normalize MinerU image paths to the extract root URL layout."""
        normalized = rel_path.replace('\\', '/').lstrip('/')
        marker = '/images/'
        if marker in normalized:
            return 'images/' + normalized.split(marker, 1)[1]
        if normalized.startswith('images/'):
            return normalized
        return normalized
    
    def _enhance_markdown_with_captions(self, markdown_content: str) -> tuple[str, int]:
        """
        Enhance markdown by adding captions to images that don't have alt text
        
        Args:
            markdown_content: Original markdown content
            
        Returns:
            Tuple of (enhanced_markdown, failed_image_count)
        """
        if not self._can_generate_captions():
            return markdown_content, 0
        
        # Extract all image URLs from markdown (both with and without alt text)
        # Support both http/https URLs and relative paths
        image_pattern = r'!\[(.*?)\]\(([^\)]+)\)'
        matches = list(re.finditer(image_pattern, markdown_content))
        
        logger.info(f"Found {len(matches)} markdown image references")
        
        if not matches:
            logger.info("No markdown image syntax found")
            return markdown_content, 0
        
        # Filter to only images without alt text (empty brackets)
        images_to_caption = []
        for match in matches:
            alt_text = match.group(1).strip()
            image_url = match.group(2).strip()
            logger.debug(f"Image found: alt='{alt_text}', url='{image_url}'")
            
            if not alt_text:  # Only process images with empty alt text
                images_to_caption.append(match)
        
        if not images_to_caption:
            logger.info(f"Found {len(matches)} images in markdown, but all have descriptions. Skipping caption generation.")
            return markdown_content, 0
        
        logger.info(f"Found {len(images_to_caption)} images without descriptions out of {len(matches)} total, generating captions...")
        
        # Generate captions in parallel (only for images without alt text)
        image_urls = [match.group(2) for match in images_to_caption]
        captions, failed_count = self._generate_captions_parallel(image_urls)
        
        # Log results
        success_count = len(images_to_caption) - failed_count
        logger.info(f"Image caption generation completed: {success_count} succeeded, {failed_count} failed out of {len(images_to_caption)} total")
        
        # Replace image syntax with captioned version (in reverse order to maintain positions)
        enhanced_content = markdown_content
        for match, caption in zip(reversed(images_to_caption), reversed(captions)):
            old_text = match.group(0)
            url = match.group(2)
            # Use caption as alt text (empty if generation failed)
            new_text = f"![{caption}]({url})"
            enhanced_content = enhanced_content[:match.start()] + new_text + enhanced_content[match.end():]
        
        return enhanced_content, failed_count
    
    def _generate_captions_parallel(self, image_urls: List[str], max_workers: int = 12, max_retries: int = 3) -> tuple[List[str], int]:
        """
        Generate captions for multiple images in parallel with retry mechanism
        
        Args:
            image_urls: List of image URLs
            max_workers: Maximum number of parallel workers
            max_retries: Maximum number of retries for each image
            
        Returns:
            Tuple of (list of captions, number of failed images)
        """
        captions = [""] * len(image_urls)
        failed_count = 0
        
        def generate_with_retry(url: str, idx: int) -> tuple[int, str, bool]:
            """Generate caption with retry logic"""
            for attempt in range(max_retries):
                try:
                    caption = self._generate_single_caption(url)
                    if caption:
                        logger.debug(f"Generated caption for image {idx + 1}/{len(image_urls)} (attempt {attempt + 1})")
                        return (idx, caption, True)
                    else:
                        logger.warning(f"Empty caption for image {idx + 1} (attempt {attempt + 1}/{max_retries})")
                except Exception as e:
                    logger.warning(f"Failed to generate caption for image {idx + 1} (attempt {attempt + 1}/{max_retries}): {str(e)}")
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(1 * (attempt + 1))  # Exponential backoff: 1s, 2s, 3s
            
            # All retries failed
            logger.error(f"Failed to generate caption for image {idx + 1} after {max_retries} attempts")
            return (idx, "", False)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(generate_with_retry, url, idx): idx
                for idx, url in enumerate(image_urls)
            }
            
            for future in as_completed(future_to_idx):
                try:
                    idx, caption, success = future.result()
                    captions[idx] = caption
                    if not success:
                        failed_count += 1
                except Exception as e:
                    idx = future_to_idx[future]
                    logger.error(f"Unexpected error generating caption for image {idx + 1}: {str(e)}")
                    failed_count += 1
        
        return captions, failed_count
    
    def _generate_single_caption(self, image_url: str, *, raise_on_error: bool = False) -> str:
        """
        Generate caption for a single image (supports both HTTP URLs and local paths)
        
        Args:
            image_url: URL or local path of the image
            raise_on_error: Raise the underlying provider error instead of returning
                an empty caption. This is useful for settings diagnostics.
            
        Returns:
            Generated caption
        """
        try:
            # Load image based on URL type
            if image_url.startswith('http://') or image_url.startswith('https://'):
                # Download from HTTP(S) URL
                response = requests.get(image_url, timeout=30)
                response.raise_for_status()
                image = Image.open(io.BytesIO(response.content))
            elif image_url.startswith('/files/mineru/'):
                # Local MinerU extracted file with prefix matching support
                from utils.path_utils import find_mineru_file_with_prefix
                
                # Find file with prefix matching
                img_path = find_mineru_file_with_prefix(image_url)
                
                if img_path is None or not img_path.exists():
                    logger.warning(f"Local image file not found (with prefix matching): {image_url}")
                    return ""
                
                image = Image.open(img_path)
            else:
                # Unsupported path type
                logger.warning(f"Unsupported image path type: {image_url}")
                return ""
            
            # Generate caption via provider factory
            prompt = prompt_registry.render("caption.image.zh").strip()

            with tempfile.NamedTemporaryFile(prefix='caption_', suffix='.jpg', delete=False) as tmp:
                temp_path = tmp.name
            try:
                if image.mode in ('RGBA', 'LA', 'P'):
                    image = image.convert('RGB')
                image.save(temp_path, format="JPEG", quality=95)
                image.close()

                provider = self._get_caption_provider()
                caption = provider.generate_with_image(prompt, temp_path)
            finally:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

            # Strip <think>...</think> tags from reasoning models
            caption = strip_think_tags(caption)

            return caption
            
        except Exception as e:
            logger.warning(f"Failed to generate caption for {image_url}: {str(e)}")
            if raise_on_error:
                raise RuntimeError(f"图片识别模型调用失败: {str(e)}") from e
            return ""  # Return empty string on failure
