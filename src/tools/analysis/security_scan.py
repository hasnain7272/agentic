"""Security scanning tool for code vulnerabilities."""
import re
from typing import Any, Dict, List

from src.tools.core.base import BaseTool, ToolParameter
from src.infrastructure.sandbox.kubernetes import get_sandbox_executor


class SecurityScanTool(BaseTool):
    """Scan codebase for security vulnerabilities."""
    name = "security_scan"
    description = "Scan code for secrets, vulnerabilities, and security risks"
    parameters = [
        ToolParameter(name="scan_type", type="string", description="Type: secrets|vulnerabilities|all", default="all"),
        ToolParameter(name="path", type="string", description="Path to scan", default="."),
    ]
    requires_sandbox = True

    DANGEROUS_PATTERNS = [
        (r'password\s*=\s*["\'][^"\']{3,}["\']', "Hardcoded password", "critical"),
        (r'api[_-]?key\s*=\s*["\'][^"\']{10,}["\']', "Hardcoded API key", "critical"),
        (r'secret\s*=\s*["\'][^"\']{10,}["\']', "Hardcoded secret", "critical"),
        (r'eval\s*\(', "Eval usage", "high"),
        (r'exec\s*\(', "Exec usage", "high"),
        (r'subprocess\.call\s*\([^)]*shell\s*=\s*True', "Shell=True subprocess", "high"),
        (r'rm\s+-rf\s+/', "Dangerous rm command", "critical"),
        (r'os\.system\s*\(', "os.system usage", "medium"),
        (r'pickle\.loads?\s*\(', "Unsafe pickle deserialization", "high"),
        (r'yaml\.load\s*\([^)]*Loader\s*=\s*[^S]', "Unsafe YAML loading", "medium"),
    ]

    async def execute(self, session_id: str, **kwargs) -> Dict[str, Any]:
        scan_type = kwargs.get("scan_type", "all")
        path = kwargs.get("path", ".")
        workspace = f"/workspace/{session_id}/repos"

        findings = []

        if scan_type in ["secrets", "all"]:
            findings.extend(await self._scan_secrets(workspace, path))

        if scan_type in ["vulnerabilities", "all"]:
            findings.extend(await self._scan_vulnerabilities(workspace, path))

        # Categorize
        critical = [f for f in findings if f["severity"] == "critical"]
        high = [f for f in findings if f["severity"] == "high"]
        medium = [f for f in findings if f["severity"] == "medium"]

        return {
            "success": True,
            "scan_type": scan_type,
            "path": path,
            "total_findings": len(findings),
            "critical": len(critical),
            "high": len(high),
            "medium": len(medium),
            "findings": findings[:20],  # Limit output
            "passed": len(critical) == 0 and len(high) == 0,
        }

    async def _scan_secrets(self, workspace: str, path: str) -> List[Dict]:
        """Scan for hardcoded secrets."""
        executor = await get_sandbox_executor()
        result = await executor.execute(
            command=f"cd {workspace} && grep -r -n -E '(password|api_key|secret|token)\\s*=\\s*' {path} --include='*.py' --include='*.js' --include='*.ts' --include='*.json' --include='*.env' 2>/dev/null | head -50"
        )

        findings = []
        for line in result.stdout.splitlines():
            if ":" in line:
                filepath, content = line.split(":", 1)
                if any(x in content.lower() for x in ["example", "placeholder", "fake", "test"]):
                    continue
                findings.append({
                    "type": "secret",
                    "severity": "critical",
                    "file": filepath,
                    "content": content[:100],
                    "recommendation": "Move to environment variables or secret manager",
                })

        return findings

    async def _scan_vulnerabilities(self, workspace: str, path: str) -> List[Dict]:
        """Scan for vulnerability patterns."""
        executor = await get_sandbox_executor()
        result = await executor.execute(
            command=f"cd {workspace} && find {path} -type f \\( -name '*.py' -o -name '*.js' -o -name '*.ts' \\) -exec cat {{}} + 2>/dev/null"
        )

        findings = []
        content = result.stdout

        for pattern, description, severity in self.DANGEROUS_PATTERNS:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                # Find line number
                line_num = content[:match.start()].count('\n') + 1
                findings.append({
                    "type": "vulnerability",
                    "severity": severity,
                    "description": description,
                    "line": line_num,
                    "content": match.group()[:50],
                })

        return findings
