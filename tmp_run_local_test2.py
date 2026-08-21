import os, json
import sys
sys.path.insert(0, 'src')
from mammoth_os.sandbox_runner import run_code
os.environ['FORCE_SUBPROCESS_FALLBACK']='1'
project={'check.py':'print("OK")\nassert 1 + 1 == 2\n'}
test_script="import runpy, sys; runpy.run_path('check.py', run_name='__main__'); sys.exit(0)"
res=run_code(code='', test_script=test_script, timeout=10, memory_limit_mb=64, project_files=project)
print(json.dumps(res, indent=2))
