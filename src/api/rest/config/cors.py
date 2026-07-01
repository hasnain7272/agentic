"""CORS configuration for production and development."""
import os
from typing import List, Tuple

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def get_cors_config() -> Tuple[List[str], List[str], List[str], bool]:
    """Get CORS configuration based on environment.

    Returns: (origins, methods, headers, is_production)
    """
    is_prod = os.environ.get("ENVIRONMENT") == "production"

    if is_prod:
        origins = os.environ.get(
            "ALLOWED_ORIGINS",
            "https://app.antigravity.dev,https://api.antigravity.dev,https://*.github.io,https://*.trycloudflare.com"
        ).split(",")
        methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]
        headers = ["Authorization", "Content-Type", "X-Tenant-Id", "X-Request-ID"]
    else:
        origins = [
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:8089",
            "http://localhost:8089",
            "http://0.0.0.0:8089",
            "ws://localhost:8089",
        ]
        methods = ["*"]
        headers = ["*"]

    return origins, methods, headers, is_prod


def setup_cors(app: FastAPI):
    """Configure CORS middleware for the app."""
    origins, methods, headers, is_prod = get_cors_config()

    if is_prod:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=methods,
            allow_headers=headers,
            expose_headers=["X-Request-ID"],
            max_age=600,
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origin_regex=".*",
            allow_credentials=True,
            allow_methods=methods,
            allow_headers=headers,
            expose_headers=["X-Request-ID"],
            max_age=3600,
        )
