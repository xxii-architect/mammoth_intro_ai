# quick_smoke_test.py (or run these lines in REPL)

from mammoth_os.cortex import build_cortex
from mammoth_os.cortex.approval_handlers import simple_console_approval
from mammoth_os.core_types import ExecutionConfig

cfg = ExecutionConfig(default_timeout=5.0, default_retries=1, risk_threshold=0.6)
cortex = build_cortex(approval_mode="vs_code_webview", approval_handler=simple_console_approval, execution_config=cfg)

# Low risk (allowed)
print("LOW RISK -> expect execute or allowed result")
print(cortex.handle_task("BrandVoiceAgent", "generate_copy", "docs/marketing.txt", {"theme":"smoke test"}))

# Medium risk (warn but proceed)
print("MEDIUM RISK -> should log a warning and proceed")
print(cortex.handle_task("CurriculumAgent", "create_directory", "content/new_course", {}))

# High risk (requires approval)
print("HIGH RISK -> should prompt for approval")
print(cortex.handle_task("CodingAgent", "delete_file", "some/important/file.txt", {}))
