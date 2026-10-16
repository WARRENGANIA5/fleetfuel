"""Prepare the folder that is uploaded to Vercel (.vercel_build/).

Vercel runs the app as a serverless function, so the upload holds only what
the web app needs at run time: the code, templates, static files, the trained
model and the datasets. Training-only libraries (statsmodels, matplotlib,
seaborn) are left out so the function stays within Vercel's size limit; the
model is trained on the office computer and uploaded with the app.

Usage (from the project folder):
    venv\\Scripts\\python.exe deploy\\build_vercel.py
    cd .vercel_build
    vercel deploy --prod
"""
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, ".vercel_build")

FILES = ["app.py", "config.py", "db.py", "timeutil.py", "init_db.py", "backup_database.py"]
FOLDERS = ["templates", "static", "model", "data", "database"]
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc", "*.tmp", "avatars", "*.synthetic_*")

REQUIREMENTS = """Flask==3.0.3
Flask-WTF==1.2.1
PyMySQL==1.1.1
cryptography==43.0.0
pandas==2.2.2
numpy==1.26.4
scikit-learn==1.5.1
joblib==1.4.2
python-dotenv==1.0.1
Werkzeug==3.0.3
Pillow==12.3.0
"""

ENTRY = '''# Vercel entry point: the Flask app serves every page, API call and static file.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402,F401
'''

VERCEL_JSON = """{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "functions": {
    "api/index.py": {
      "maxDuration": 30,
      "includeFiles": "{templates,static,model,data,database}/**"
    }
  },
  "rewrites": [{ "source": "/(.*)", "destination": "/api/index" }]
}
"""


def main():
    os.makedirs(OUT, exist_ok=True)
    # Keep .vercel/ (the link to the Vercel project); replace everything else.
    for name in os.listdir(OUT):
        if name == ".vercel":
            continue
        path = os.path.join(OUT, name)
        shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
    for name in FILES:
        shutil.copy2(os.path.join(ROOT, name), OUT)
    for name in FOLDERS:
        shutil.copytree(os.path.join(ROOT, name), os.path.join(OUT, name), ignore=SKIP)
    os.makedirs(os.path.join(OUT, "static", "images", "avatars"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "api"), exist_ok=True)
    with open(os.path.join(OUT, "api", "index.py"), "w", encoding="utf-8") as f:
        f.write(ENTRY)
    with open(os.path.join(OUT, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write(REQUIREMENTS)
    with open(os.path.join(OUT, "vercel.json"), "w", encoding="utf-8") as f:
        f.write(VERCEL_JSON)
    print(f" * Vercel upload folder ready: {OUT}")


if __name__ == "__main__":
    main()
