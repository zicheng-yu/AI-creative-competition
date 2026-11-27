"""Regenerate the portable workbench JSON Schema."""

import json

from .contracts import Workspace

if __name__ == "__main__":
    schema = Workspace.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "urn:competition:workbench:workspace:1.0.0"
    print(json.dumps(schema, ensure_ascii=False, indent=2))
