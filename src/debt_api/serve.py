"""Development server: `debt-api` runs uvicorn with reload on port 8000."""

from __future__ import annotations

import os


def main() -> None:
    import uvicorn

    uvicorn.run(
        "debt_api.main:app",
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
        reload=os.environ.get("RELOAD", "true").lower() == "true",
    )


if __name__ == "__main__":
    main()
