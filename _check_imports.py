"""Import test - verify all key modules load correctly"""
import sys
import traceback

modules_to_test = [
    "src.backend.llm.client",
    "src.backend.db.models",
    "src.backend.db.database",
    "src.backend.db.crud",
    "src.backend.core.memory",
    "src.backend.core.chunked_generator",
    "src.backend.core.chapter_pipeline",
    "src.backend.core.orchestrator",
    "src.backend.agents.base",
    "src.backend.agents.prompts",
    "src.backend.models.schemas",
]

errors = []
for mod in modules_to_test:
    try:
        __import__(mod)
        print(f"? {mod}")
    except Exception as e:
        errors.append((mod, e))
        print(f"? {mod}: {e}")

if errors:
    print(f"\n? 导入失败 {len(errors)} 个模块")
    sys.exit(1)
else:
    print(f"\n? 全部 {len(modules_to_test)} 个模块导入成功")
    sys.exit(0)
