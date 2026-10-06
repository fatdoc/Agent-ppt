#!/usr/bin/env python3
"""Start an isolated education instance. Never loads the general edition .env."""

import argparse
import os
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service", choices=["init", "backend", "frontend"])
    args = parser.parse_args()
    runtime = ROOT / ".education-runtime"
    runtime.mkdir(exist_ok=True)
    os.chmod(runtime, 0o700)
    secret_file = runtime / "secret"
    if not secret_file.exists():
        fd = os.open(secret_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_urlsafe(48))
    os.environ.update(
        APP_EDITION="education",
        LOAD_DOTENV="false",
        DATABASE_URL=f"sqlite:///{runtime / 'education.db'}",
        UPLOAD_FOLDER=str(runtime / "uploads"),
        SECRET_KEY=secret_file.read_text(),
        AUTH_REQUIRED="true",
        AUTH_COOKIE_SECURE="false",
        BACKEND_PORT=os.getenv("EDUCATION_BACKEND_PORT", "5191"),
        FRONTEND_PORT=os.getenv("EDUCATION_FRONTEND_PORT", "3190"),
        CORS_ORIGINS=f"http://127.0.0.1:{os.getenv('EDUCATION_FRONTEND_PORT', '3190')}",
        FLASK_ENV="development",
    )
    # Optional provider-only config belongs to this deployment, never the main .env.
    if args.service != "frontend":
        from dotenv import dotenv_values

        settings = dotenv_values(runtime / "providers.env")
        for key, value in settings.items():
            if value is not None and (
                key.startswith(
                    (
                        "TEXT_",
                        "IMAGE_",
                        "OPENAI_",
                        "GOOGLE_",
                        "GENAI_",
                        "ANTHROPIC_",
                        "MINERU_",
                        "ENABLE_",
                        "MAX_",
                    )
                )
                or key == "AI_PROVIDER_FORMAT"
            ):
                os.environ[key] = value
    if args.service == "frontend":
        os.chdir(ROOT / "frontend")
        os.execvp("npm", ["npm", "run", "dev", "--", "--host", "127.0.0.1"])
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=ROOT / "backend",
        check=True,
    )
    if args.service == "init":
        print(
            "Education database initialized in .education-runtime. Register a separate account in the browser."
        )
        return
    os.chdir(ROOT / "backend")
    sys.path.insert(0, str(ROOT / "backend"))
    from app import create_app

    app = create_app()
    app.run(
        host="127.0.0.1",
        port=int(os.environ["BACKEND_PORT"]),
        debug=False,
        use_reloader=False,
    )


if __name__ == "__main__":
    main()
