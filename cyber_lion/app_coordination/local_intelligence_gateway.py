# R10 R2 unified local intelligence gateway. Pure orchestration only.
from __future__ import annotations
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from hashlib import sha256
import json,re,secrets,threading,time,uuid
from html.parser import HTMLParser
from urllib.parse import urljoin,urlsplit,unquote,parse_qs
from .lion_context_provider import build_lion_context
from .rag_tool_adapter import RagIndex
from .repository_read_adapter import RepositoryReader
from .currentness_tool_adapter import read_currentness
