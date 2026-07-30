"""Post the next pending reel in queue/reel_queue.json to Instagram.

Run daily by .github/workflows/daily-reel.yml, at 4pm IST. Instagram Reels
publishing needs an extra step vs. a normal image post: after creating the
media container, Instagram processes the video server-side, so we poll
status_code until it reports FINISHED before publishing (a plain image is
ready immediately; a video is not).

Uses only the Python standard library (urllib) — no pip install step needed.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

GRAPH_API = "https://graph.facebook.com/v20.0"
QUEUE_PATH = os.path.join(os.path.dirname(__file__), "..", "queue", "reel_queue.json")

ACCESS_TOKEN = os.environ["META_ACCESS_TOKEN"].strip()
IG_BUSINESS_ACCOUNT_ID = os.environ["IG_BUSINESS_ACCOUNT_ID"].strip()
PUBLIC_ASSET_BASE_URL = os.environ.get(
    "PUBLIC_ASSET_BASE_URL", "https://pradipbhuyan.github.io/likha-poha-promo-assets"
).strip()

POLL_INTERVAL_SECONDS = 8
POLL_TIMEOUT_SECONDS = 240  # Reels are short (12-24s) — this is generous


def http_post_form(url, params):
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_get(url, params):
    full = f"{url}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(full) as resp:
        return json.loads(resp.read().decode("utf-8"))


def video_url_for(asset_path):
    filename = asset_path.replace("\\", "/").split("/")[-1]
    return f"{PUBLIC_ASSET_BASE_URL}/reels/{filename}"


def wait_until_ready(creation_id):
    waited = 0
    while waited < POLL_TIMEOUT_SECONDS:
        status = http_get(f"{GRAPH_API}/{creation_id}", {
            "fields": "status_code",
            "access_token": ACCESS_TOKEN,
        })
        code = status.get("status_code")
        print(f"  status: {code} (waited {waited}s)")
        if code == "FINISHED":
            return True
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Reel processing failed: {status}")
        time.sleep(POLL_INTERVAL_SECONDS)
        waited += POLL_INTERVAL_SECONDS
    raise TimeoutError(f"Reel still not FINISHED after {POLL_TIMEOUT_SECONDS}s")


def post_reel(item):
    video_url = video_url_for(item["asset_path"])
    container = http_post_form(
        f"{GRAPH_API}/{IG_BUSINESS_ACCOUNT_ID}/media",
        {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": item["caption"],
            "access_token": ACCESS_TOKEN,
        },
    )
    creation_id = container["id"]
    print(f"  container created: {creation_id}")
    wait_until_ready(creation_id)
    http_post_form(
        f"{GRAPH_API}/{IG_BUSINESS_ACCOUNT_ID}/media_publish",
        {"creation_id": creation_id, "access_token": ACCESS_TOKEN},
    )


def main():
    with open(QUEUE_PATH) as f:
        queue = json.load(f)

    next_item = next((q for q in queue if q["status"] == "pending"), None)
    if next_item is None:
        print("Reel queue empty — nothing pending. Nothing to do.")
        return

    print(f"Posting reel {next_item['id']}...")
    try:
        post_reel(next_item)
    except (urllib.error.HTTPError, RuntimeError, TimeoutError) as e:
        detail = e.read().decode("utf-8") if isinstance(e, urllib.error.HTTPError) else str(e)
        print(f"FAILED: {detail}", file=sys.stderr)
        sys.exit(1)

    next_item["status"] = "posted"
    next_item["posted_at"] = datetime.now(timezone.utc).isoformat()

    with open(QUEUE_PATH, "w") as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)

    print(f"Posted and marked {next_item['id']} as posted.")


if __name__ == "__main__":
    main()
