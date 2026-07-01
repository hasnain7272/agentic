"""
Docker Image Builder - Custom Sandbox Image Building

Builds optimized Docker images for sandbox execution with
pre-installed tools and security hardening.
"""
import logging
import docker
from pathlib import Path
from typing import Dict, List, Optional

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


DEFAULT_DOCKERFILE = """
FROM python:3.11-slim

# Security: Create non-root user
RUN groupadd -r sandbox && useradd -r -g sandbox -d /home/sandbox -s /bin/bash sandbox \
    && mkdir -p /home/sandbox && chown sandbox:sandbox /home/sandbox

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    wget \
    ca-certificates \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install common Python tools
RUN pip install --no-cache-dir \
    pytest \
    black \
    ruff \
    mypy \
    requests \
    httpx \
    beautifulsoup4 \
    lxml \
    rich

# Set up workspace
WORKDIR /workspace
RUN chown sandbox:sandbox /workspace

# Security: Drop privileges
USER sandbox:sandbox

# Default command
CMD ["sleep", "infinity"]
"""


class DockerImageBuilder:
    """Builds and manages custom Docker images for sandboxes."""
    
    def __init__(self):
        self._client = docker.from_env()
        self._settings = get_settings()
        self._built_images: Dict[str, str] = {}  # tag -> image_id
    
    def build_base_image(self, tag: str = None) -> str:
        """Build the base sandbox image from default Dockerfile."""
        tag = tag or self._settings.docker_image
        
        logger.info(f"Building base image: {tag}")
        
        image, logs = self._client.images.build(
            fileobj=Path(DEFAULT_DOCKERFILE).read_bytes(),
            tag=tag,
            rm=True,
            forcerm=True,
            pull=True,
        )
        
        self._built_images[tag] = image.id
        logger.info(f"Built image: {tag} ({image.id[:12]})")
        return image.id
    
    def build_custom_image(
        self,
        dockerfile_content: str,
        tag: str,
        build_args: Dict[str, str] = None,
    ) -> str:
        """Build a custom image from provided Dockerfile."""
        logger.info(f"Building custom image: {tag}")
        
        image, logs = self._client.images.build(
            fileobj=dockerfile_content.encode(),
            tag=tag,
            buildargs=build_args or {},
            rm=True,
            forcerm=True,
            pull=True,
        )
        
        self._built_images[tag] = image.id
        logger.info(f"Built custom image: {tag} ({image.id[:12]})")
        return image.id
    
    def build_from_path(
        self,
        context_path: str,
        dockerfile: str = "Dockerfile",
        tag: str = None,
        build_args: Dict[str, str] = None,
    ) -> str:
        """Build image from a directory context."""
        tag = tag or f"agentic/custom-{Path(context_path).name}"
        
        logger.info(f"Building from path: {context_path} -> {tag}")
        
        image, logs = self._client.images.build(
            path=context_path,
            dockerfile=dockerfile,
            tag=tag,
            buildargs=build_args or {},
            rm=True,
            forcerm=True,
        )
        
        self._built_images[tag] = image.id
        return image.id
    
    def push_image(self, tag: str, registry: str = None) -> bool:
        """Push image to registry."""
        full_tag = f"{registry}/{tag}" if registry else tag
        
        try:
            logger.info(f"Pushing image: {full_tag}")
            self._client.images.push(full_tag)
            logger.info(f"Pushed: {full_tag}")
            return True
        except Exception as e:
            logger.error(f"Push failed: {e}")
            return False
    
    def image_exists(self, tag: str) -> bool:
        """Check if image exists locally."""
        try:
            self._client.images.get(tag)
            return True
        except docker.errors.ImageNotFound:
            return False
    
    def remove_image(self, tag: str, force: bool = False) -> bool:
        """Remove image from local cache."""
        try:
            self._client.images.remove(tag, force=force)
            self._built_images.pop(tag, None)
            return True
        except Exception as e:
            logger.error(f"Remove failed: {e}")
            return False
    
    def list_images(self, filter_label: str = "agentic.sandbox") -> List[Dict]:
        """List sandbox images."""
        filters = {"label": filter_label} if filter_label else {}
        images = self._client.images.list(filters=filters)
        
        return [
            {
                "id": img.id[:12],
                "tags": img.tags,
                "size_mb": round(img.attrs.get("Size", 0) / 1024 / 1024, 2),
                "created": img.attrs.get("Created", ""),
            }
            for img in images
        ]
    
    def get_image_info(self, tag: str) -> Optional[Dict]:
        """Get detailed image information."""
        try:
            img = self._client.images.get(tag)
            return {
                "id": img.id,
                "tags": img.tags,
                "size_bytes": img.attrs.get("Size", 0),
                "created": img.attrs.get("Created", ""),
                "architecture": img.attrs.get("Architecture", ""),
                "os": img.attrs.get("Os", ""),
                "config": img.attrs.get("Config", {}),
                "labels": img.attrs.get("Config", {}).get("Labels", {}),
            }
        except docker.errors.ImageNotFound:
            return None


# Singleton
_builder: Optional[DockerImageBuilder] = None


def get_docker_builder() -> DockerImageBuilder:
    """Get or create the global Docker image builder."""
    global _builder
    if _builder is None:
        _builder = DockerImageBuilder()
    return _builder