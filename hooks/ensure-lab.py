"""sessionStart hook: explain the explicit Veyra first-run command."""

from __future__ import annotations

import json


def main() -> None:
    print(
        json.dumps(
            {
                "additional_context": (
                    "Veyra Scientific is available. Installation is explicit: run "
                    "python hooks/bootstrap.py --dev, or use Veyra: Doctor. "
                    "Then call start_laboratory if the Workbench is needed "
                    "(http://127.0.0.1:8765/). Do not invent numeric results."
                )
            }
        )
    )


if __name__ == "__main__":
    main()
