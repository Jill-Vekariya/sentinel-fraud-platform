"""Run one bounded worker for the synthetic, ephemeral deployment demo."""

import logging
import os

import uvicorn


def main():
    if os.getenv("FRAUD_ENV") != "production":
        raise SystemExit("Demo deployment requires FRAUD_ENV=production and a private API_KEY")
    port = int(os.getenv("PORT", "10000"))
    if not 1 <= port <= 65535:
        raise SystemExit("PORT must be between 1 and 65535")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    uvicorn.run(
        "fraud.api:app",
        host="0.0.0.0",
        port=port,
        workers=1,
        limit_concurrency=16,
        timeout_keep_alive=5,
        access_log=False,
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()
