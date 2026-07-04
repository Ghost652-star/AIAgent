from __future__ import annotations



from pathlib import Path



from bugdoctor.tools.base import ToolRegistry

from bugdoctor.tools.edit_file import EditFileTool
from bugdoctor.tools.get_environment import GetEnvironmentTool
from bugdoctor.tools.glob_files import GlobFilesTool
from bugdoctor.tools.grep_code import GrepCodeTool
from bugdoctor.tools.load_skill import LoadSkillTool
from bugdoctor.tools.read_file import ReadFileTool
from bugdoctor.tools.read_tracker import ReadTracker
from bugdoctor.tools.run_command import RunCommandTool
from bugdoctor.tools.write_file import WriteFileTool





def create_registry(
    project_root: Path,
    *,
    load_skill_tool: LoadSkillTool | None = None,
) -> tuple[ToolRegistry, ReadTracker]:
    """工具注册表工厂——启动时调用，注册所有可用工具"""

    read_tracker = ReadTracker()
    registry = ToolRegistry()

    registry.register(ReadFileTool(project_root, read_tracker=read_tracker))
    registry.register(GlobFilesTool(project_root))
    registry.register(GrepCodeTool(project_root))
    registry.register(RunCommandTool(project_root))
    registry.register(GetEnvironmentTool(project_root))
    registry.register(WriteFileTool(project_root))
    registry.register(EditFileTool(project_root, read_tracker=read_tracker))

    if load_skill_tool is not None:
        registry.register(load_skill_tool)

    return registry, read_tracker

