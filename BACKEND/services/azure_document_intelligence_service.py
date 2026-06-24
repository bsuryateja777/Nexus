"""
Azure Document Intelligence Service for extracting text from documents
Supports PDFs, images, Word docs, and more
"""

import logging
import os
from typing import Optional, Dict, Any, List
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from services.credential_provider import get_credential_provider

logger = logging.getLogger(__name__)


class AzureDocumentIntelligenceService:
    """Extract text and structured data from documents using Azure AI"""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        key: Optional[str] = None,
        credential=None
    ):
        """
        Initialize Document Intelligence Service

        Args:
            endpoint: Azure Document Intelligence endpoint (from .env if not provided)
            key: Azure Document Intelligence API key (from .env if not provided)
            credential: Azure credential object (DefaultAzureCredential if not provided)
        """
        self.endpoint = endpoint or os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
        self.key = key or os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")
        self.credential_provider = get_credential_provider()
        self.client = None

        if not self.endpoint:
            logger.warning("Document Intelligence endpoint not configured")
            return

        try:
            if self.key:
                credentials = AzureKeyCredential(self.key)
                logger.info("Using API key for Document Intelligence")
            else:
                credentials = credential or self.credential_provider.get_azure_credential()
                if not credentials:
                    logger.warning("No credentials available for Document Intelligence")
                    return
                logger.info("Using managed identity for Document Intelligence")

            self.client = DocumentIntelligenceClient(
                endpoint=self.endpoint,
                credential=credentials
            )
            logger.info("✓ Azure Document Intelligence Service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Document Intelligence: {str(e)}")
            self.client = None

    def is_configured(self) -> bool:
        """Check if Document Intelligence is properly configured"""
        return self.client is not None

    async def extract_text_from_url(
        self,
        document_url: str,
        model_id: str = "prebuilt-read"
    ) -> Optional[Dict[str, Any]]:
        """
        Extract text and images from a document via URL (Blob Storage URI)

        Args:
            document_url: Full URL to document in Blob Storage
            model_id: Model to use (prebuilt-read for OCR/text extraction)

        Returns:
            Dictionary with 'text' and 'images' keys, or None if failed
        """
        if not self.is_configured():
            logger.warning("Document Intelligence not configured")
            return None

        try:
            logger.info(f"Extracting text and images from URL: {document_url}")

            # Analyze document from URL
            poller = self.client.begin_analyze_document_from_url(
                model_id=model_id,
                document_url=document_url
            )
            result = poller.result()

            # Extract text from all pages
            extracted_text = ""
            if hasattr(result, 'pages') and result.pages:
                for page in result.pages:
                    if hasattr(page, 'lines') and page.lines:
                        for line in page.lines:
                            extracted_text += line.content + "\n"

            # Alternative: try to get text from paragraphs
            elif hasattr(result, 'paragraphs') and result.paragraphs:
                for para in result.paragraphs:
                    extracted_text += para.content + "\n"

            # Extract images metadata
            images_data = []
            if hasattr(result, 'figures') and result.figures:
                for idx, figure in enumerate(result.figures):
                    images_data.append({
                        "index": idx,
                        "type": "figure",
                        "page": getattr(figure, 'page_number', 'unknown'),
                        "description": getattr(figure, 'caption', f'Figure {idx + 1}')
                    })
                logger.info(f"✓ Found {len(images_data)} figures/images")

            if not extracted_text:
                logger.warning(f"No text extracted from {document_url}")
                return None

            logger.info(f"✓ Extracted {len(extracted_text)} characters from document")
            return {
                "text": extracted_text,
                "images": images_data,
                "has_visual_content": len(images_data) > 0
            }

        except Exception as e:
            logger.error(f"✗ Failed to extract text from {document_url}: {str(e)}")
            return None

    async def extract_text_from_bytes(
        self,
        document_bytes: bytes,
        content_type: str = "application/pdf",
        model_id: str = "prebuilt-read"
    ) -> Optional[Dict[str, Any]]:
        """
        Extract text and images from document bytes (for local files)

        Args:
            document_bytes: Document content as bytes
            content_type: MIME type (application/pdf, image/png, etc.)
            model_id: Model to use

        Returns:
            Dictionary with 'text' and 'images' keys, or None if failed
        """
        if not self.is_configured():
            return None

        try:
            logger.info(f"Extracting text and images from document ({len(document_bytes)} bytes)")

            # Analyze document from bytes using correct API signature
            poller = self.client.begin_analyze_document(
                model_id,
                document_bytes,
                content_type=content_type
            )
            result = poller.result()

            # Extract text
            extracted_text = ""
            if hasattr(result, 'pages') and result.pages:
                for page in result.pages:
                    if hasattr(page, 'lines') and page.lines:
                        for line in page.lines:
                            extracted_text += line.content + "\n"

            # Alternative: try paragraphs
            if not extracted_text and hasattr(result, 'paragraphs') and result.paragraphs:
                for para in result.paragraphs:
                    extracted_text += para.content + "\n"

            # Extract images metadata
            images_data = []
            if hasattr(result, 'figures') and result.figures:
                for idx, figure in enumerate(result.figures):
                    images_data.append({
                        "index": idx,
                        "type": "figure",
                        "page": getattr(figure, 'page_number', 'unknown'),
                        "description": getattr(figure, 'caption', f'Figure {idx + 1}')
                    })
                logger.info(f"✓ Found {len(images_data)} figures/images")

            if extracted_text:
                logger.info(f"✓ Extracted {len(extracted_text)} characters")
            else:
                logger.warning("No text extracted - document may be image-based")

            return {
                "text": extracted_text,
                "images": images_data,
                "has_visual_content": len(images_data) > 0
            }

        except Exception as e:
            logger.error(f"✗ Failed to extract text from bytes: {str(e)}")
            return None

    async def extract_tables(
        self,
        document_url: str,
        model_id: str = "prebuilt-read"
    ) -> List[Dict[str, Any]]:
        """
        Extract tables from a document

        Args:
            document_url: Full URL to document
            model_id: Model to use

        Returns:
            List of tables with their data
        """
        if not self.is_configured():
            return []

        try:
            logger.info(f"Extracting tables from: {document_url}")

            poller = self.client.begin_analyze_document_from_url(
                model_id=model_id,
                document_url=document_url
            )
            result = poller.result()

            tables = []
            if result.tables:
                for table in result.tables:
                    table_data = {
                        "rows": table.row_count,
                        "columns": table.column_count,
                        "cells": []
                    }

                    for cell in table.cells:
                        table_data["cells"].append({
                            "row": cell.row_index,
                            "column": cell.column_index,
                            "content": cell.content,
                            "is_header": cell.is_header,
                            "is_total": cell.is_total,
                        })

                    tables.append(table_data)

            logger.info(f"Extracted {len(tables)} tables")
            return tables

        except Exception as e:
            logger.error(f"Failed to extract tables: {str(e)}")
            return []

    async def extract_key_value_pairs(
        self,
        document_url: str,
        model_id: str = "prebuilt-forms"
    ) -> Dict[str, str]:
        """
        Extract key-value pairs from forms/structured documents

        Args:
            document_url: Full URL to document
            model_id: Model to use

        Returns:
            Dictionary of key-value pairs
        """
        if not self.is_configured():
            return {}

        try:
            logger.info(f"Extracting key-value pairs from: {document_url}")

            poller = self.client.begin_analyze_document_from_url(
                model_id=model_id,
                document_url=document_url
            )
            result = poller.result()

            key_values = {}
            if result.key_value_pairs:
                for pair in result.key_value_pairs:
                    key = pair.key.content if pair.key else "unknown"
                    value = pair.value.content if pair.value else "empty"
                    key_values[key] = value

            logger.info(f"Extracted {len(key_values)} key-value pairs")
            return key_values

        except Exception as e:
            logger.error(f"Failed to extract key-value pairs: {str(e)}")
            return {}

    def get_status(self) -> Dict[str, Any]:
        """Get service status"""
        return {
            "configured": self.is_configured(),
            "endpoint": self.endpoint if self.is_configured() else None,
        }
