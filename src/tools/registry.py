"""
Dynamic Tool Registry (Hardened)

Auto-discovers tools AND provides manual fallback for core tools.
The system NEVER goes down because of a missing __init__.py or import error.
"""
import importlib
import inspect
import logging
import pkgutil
from typing import Dict, Type, List, Any, Optional

from src.tools.core.base import BaseTool

logger = logging.getLogger(__name__)

# Singleton tool instance cache
_tool_instances: Dict[str, BaseTool] = {}
_discovered = False


def _discover_tools():
    """Walk src.tools subpackages and register all BaseTool subclasses."""
    global _discovered
    if _discovered:
        return
    _discovered = True

    try:
        import src.tools as tools_pkg
        prefix = tools_pkg.__name__ + "."
        for _, modname, ispkg in pkgutil.walk_packages(tools_pkg.__path__, prefix):
            if not ispkg:
                try:
                    importlib.import_module(modname)
                except Exception as e:
                    logger.warning(f"Failed to load tool module {modname}: {e}")
    except Exception as e:
        logger.warning(f"Dynamic tool discovery failed: {e}")

    # Find ALL subclasses recursively (not just immediate children)
    def _all_subclasses(cls):
        result = set()
        for sub in cls.__subclasses__():
            result.add(sub)
            result.update(_all_subclasses(sub))
        return result

    for cls in _all_subclasses(BaseTool):
        if not inspect.isabstract(cls):
            try:
                # Check if constructor has required arguments
                sig = inspect.signature(cls.__init__)
                has_required_args = False
                for name, param in sig.parameters.items():
                    if name == 'self':
                        continue
                    if param.default is inspect.Parameter.empty and param.kind != inspect.Parameter.VAR_KEYWORD and param.kind != inspect.Parameter.VAR_POSITIONAL:
                        has_required_args = True
                        break
                
                if has_required_args:
                    # Skip tools that require specific initialization (e.g. MCPProxyTool)
                    continue

                instance = cls()
                if instance.name and instance.name not in _tool_instances:
                    _tool_instances[instance.name] = instance
            except Exception as e:
                logger.error(f"Failed to instantiate tool {cls.__name__}: {e}")

    # === MANUAL FALLBACK: If discovery missed core tools, force-register them ===
    _ensure_core_tools()

    names = list(_tool_instances.keys())
    logger.info(f"[Registry] Mounted {len(names)} tools: {', '.join(names)}")


def _ensure_core_tools():
    """Guarantee tools exist even if auto-discovery fails."""
    fallback_map = {
        # Core tools
        "bash_execute": "src.tools.execution.bash.BashExecuteTool",
        "read_file": "src.tools.filesystem.read.ReadFileTool",
        "write_file": "src.tools.filesystem.write.WriteFileTool",
        # MCP Git tools
        "git_clone": "src.tools.mcp.git_operations.GitCloneTool",
        "git_read": "src.tools.mcp.git_operations.GitReadTool",
        "git_write": "src.tools.mcp.git_operations.GitWriteTool",
        "git_commit": "src.tools.mcp.git_commit.GitCommitTool",
        "git_create_pr": "src.tools.mcp.git_pr.GitPRTool",
        # Analysis tools
        "security_scan": "src.tools.analysis.security_scan.SecurityScanTool",
        "code_review": "src.tools.analysis.code_review.CodeReviewTool",
        # Generation tools
        "generate_tests": "src.tools.generation.test_generator.TestGeneratorTool",
        "generate_docs": "src.tools.generation.doc_generator.DocGeneratorTool",
        "generate_cicd": "src.tools.generation.cicd_generator.CICDGeneratorTool",
        # Execution tools
        "database_query": "src.tools.execution.database.DatabaseQueryTool",
        "api_test": "src.tools.execution.api_test.APITestTool",
        "manage_dependencies": "src.tools.execution.dependency_manager.DependencyManagerTool",
        # Knowledge tools
        "code_graph_query": "src.tools.knowledge.code_graph.CodeGraphQueryTool",
        "web_search": "src.tools.knowledge.web_search.WebSearchTool",
        "update_agent_memory": "src.tools.knowledge.memory_updater.UpdateAgentMemoryTool",
        "search_past_decisions": "src.tools.knowledge.archival_memory.SearchArchivalMemoryTool",
        "delegate_task": "src.tools.orchestration.delegate_task.DelegateTaskTool",
        "dispatch_output": "src.tools.mcp.dispatch_tool.DispatchOutputTool",
    }
    for name, classpath in fallback_map.items():
        if name not in _tool_instances:
            try:
                module_path, class_name = classpath.rsplit(".", 1)
                mod = importlib.import_module(module_path)
                cls = getattr(mod, class_name)
                _tool_instances[name] = cls()
                logger.info(f"[Registry] Fallback-registered: {name}")
            except Exception as e:
                logger.warning(f"[Registry] Cannot load tool {name}: {e}")


def get_all_tool_schemas() -> List[Dict[str, Any]]:
    """Returns the JSON schemas for all registered tools."""
    if not _discovered:
        _discover_tools()
    return [inst.get_schema() for inst in _tool_instances.values()]


def get_tool_instance(name: str) -> Optional[BaseTool]:
    """Retrieve an instantiated tool by its schema name."""
    if not _discovered:
        _discover_tools()
    return _tool_instances.get(name)


def get_tool_names() -> List[str]:
    """Returns the list of all registered tool names."""
    if not _discovered:
        _discover_tools()
    return list(_tool_instances.keys())


def _tool_origin(instance: BaseTool) -> str:
    module = instance.__class__.__module__
    return "plugin" if module.startswith("src.services.mcp.") else "builtin"


def _tool_category(instance: BaseTool) -> str:
    module = instance.__class__.__module__
    if module.startswith("src.tools."):
        parts = module.split(".")
        return parts[2] if len(parts) > 2 else "core"
    return "plugin"


def get_tool_catalog() -> List[Dict[str, Any]]:
    """Returns metadata the UI can use for tool browsing."""
    if not _discovered:
        _discover_tools()
    catalog = []
    for instance in _tool_instances.values():
        catalog.append({
            "name": instance.name,
            "description": instance.description,
            "category": _tool_category(instance),
            "origin": _tool_origin(instance),
            "requires_sandbox": bool(getattr(instance, "requires_sandbox", False)),
            "parameters": [p.model_dump() for p in getattr(instance, "parameters", [])],
        })
    return sorted(catalog, key=lambda item: (item["origin"], item["category"], item["name"]))
