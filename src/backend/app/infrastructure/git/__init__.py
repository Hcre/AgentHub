"""Git infrastructure: clone, pull, scan, parse template source repos."""

from app.infrastructure.git.git_manager import GitManager
from app.infrastructure.git.template_parser import TemplateParser

__all__ = ["GitManager", "TemplateParser"]
