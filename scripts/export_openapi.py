import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app import app  # noqa: E402

Path("openapi.json").write_text(json.dumps(app.openapi(), sort_keys=True, indent=2) + "\n")
