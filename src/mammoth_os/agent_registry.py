from mammoth_os.agents.deepseek import ask as deepseek
from mammoth_os.agents.llama import ask as llama
from mammoth_os.agents.hermes import ask as hermes

AGENTS = {
    "deepseek": deepseek,
    "llama": llama,
    "hermes": hermes,
}
