import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except ModuleNotFoundError:  # pragma: no cover - optional dependency guard
    Environment = None  # type: ignore[assignment]
    FileSystemLoader = None  # type: ignore[assignment]
    select_autoescape = None  # type: ignore[assignment]

WEASYPRINT_IMPORT_ERROR: Optional[Exception] = None
try:
    from weasyprint import HTML
except Exception as exc:  # pragma: no cover - optional dependency guard
    HTML = None  # type: ignore[assignment]
    WEASYPRINT_IMPORT_ERROR = exc

logger = logging.getLogger(__name__)


class ReportGenerationUnavailableError(RuntimeError):
    """Raised when PDF generation dependencies are unavailable."""


class ReportGenerator:
    """Generates PDF reports from run data."""

    def __init__(self, templates_dir: str = "templates") -> None:
        if Environment is None or FileSystemLoader is None:
            raise RuntimeError("jinja2 is required to generate reports.")
        if select_autoescape is None:
            raise RuntimeError("jinja2 autoescape support is required to generate reports.")

        self.templates_dir = Path(templates_dir)
        if not self.templates_dir.exists():
            raise ValueError(f"Templates directory not found: {templates_dir}")
        self.pdf_available = HTML is not None
        self.pdf_unavailable_reason = self._build_pdf_unavailable_reason()

        # Report templates render model/user-provided content; keep HTML autoescaping enabled.
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )
        self.template_name = "reports/pdf_report.html"

        # Validate template exists
        try:
            self.env.get_template(self.template_name)
        except Exception as e:
            raise ValueError(f"PDF template not found: {self.template_name}") from e

        if not self.pdf_available:
            logger.warning("PDF generation disabled: %s", self.pdf_unavailable_reason)

    @staticmethod
    def _build_pdf_unavailable_reason() -> str:
        if WEASYPRINT_IMPORT_ERROR is None:
            return "weasyprint is unavailable"
        return f"WeasyPrint is unavailable: {WEASYPRINT_IMPORT_ERROR}"

    def generate_pdf_report(
        self,
        run_data: Dict[str, Any],
        capability: Dict[str, Any],
        insight: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        """
        Generate PDF report binary

        Args:
            run_data: Complete run data
            capability: Capability definition
            insight: Optional analysis insight

        Returns:
            PDF bytes
        """
        if HTML is None:
            raise ReportGenerationUnavailableError(self.pdf_unavailable_reason)

        try:
            template = self.env.get_template(self.template_name)

            # Prepare context
            context = {
                "run": run_data,
                "capability": capability,
                "insight": insight,
                "generated_at": run_data.get("timestamp"),
                "params_json": json.dumps(run_data.get("params", {}), indent=2),
            }

            # Render HTML
            html_content = template.render(**context)

            # Generate PDF
            # Use base_url to allow resolving static assets if needed
            # For now, we'll embed CSS directly or use minimal styling
            return HTML(string=html_content).write_pdf()

        except Exception as e:
            logger.error("PDF generation failed: %s", e)
            raise
