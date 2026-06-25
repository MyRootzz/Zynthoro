"""Quick probe with the EXACT payload from the review request (longer idea string),
to confirm the truncation bug fix holds for the bigger prompt too."""
import os, sys, pyotp, requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"
EMAIL = "regie@myrootzz.com"
PASS = "Zynthoro2026!"

client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
db = client[os.environ.get("DB_NAME", "test_database")]
secret = db.users.find_one({"email": EMAIL}).get("totp_secret")

s = requests.Session()
s.headers["Content-Type"] = "application/json"
r = s.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASS}).json()
if r.get("stage") == "2fa_required":
    code = pyotp.TOTP(secret).now()
    r = s.post(f"{API}/auth/2fa/verify", json={"pre_token": r["pre_token"], "method": "totp", "code": code}).json()
s.headers["Authorization"] = f"Bearer {r['token']}"

IDEA = "Just launched our new sustainable coffee blend made from rescued beans."
fails = 0
for platform in ["instagram", "facebook", "linkedin", "tiktok", "x", "youtube"]:
    resp = s.post(f"{API}/marketing/caption", json={"idea": IDEA, "platform": platform}, timeout=40)
    body = resp.json() if resp.status_code == 200 else {}
    cap = body.get("caption", "")
    tags = body.get("hashtags", [])
    bad = (
        resp.status_code != 200
        or not cap
        or cap.lstrip().startswith('{"caption')
        or "```" in cap
        or not isinstance(tags, list)
    )
    flag = "FAIL" if bad else "ok"
    if bad:
        fails += 1
    print(f"[{flag}] {platform:9s} status={resp.status_code} tags={len(tags)} cap[:90]={cap[:90]!r}")

sys.exit(1 if fails else 0)
