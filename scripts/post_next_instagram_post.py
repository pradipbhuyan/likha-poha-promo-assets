"""Post the next pending item in queue/instagram_post_queue.json to
Instagram as a feed post.

Run 3x/day by .github/workflows/daily-post.yml. Split out from the former
combined post_next_content.py so Instagram's cadence runs independently of
WhatsApp's (see post_next_whatsapp_post.py) — each item's "lang" field
("en"/"hi") is informational only; the 2 English : 1 Hindi daily ratio is
guaranteed purely by how queue/instagram_post_queue.json's pending items
are ordered, not by any logic here.

Uses only the Python standard library (urllib) so the GitHub Actions job
needs no pip install step.
"""
import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

GRAPH_API = "https://graph.facebook.com/v20.0"
QUEUE_PATH = os.path.join(os.path.dirname(__file__), "..", "queue", "instagram_post_queue.json")

ACCESS_TOKEN = os.environ["META_ACCESS_TOKEN"].strip()
IG_BUSINESS_ACCOUNT_ID = os.environ["IG_BUSINESS_ACCOUNT_ID"].strip()
PUBLIC_ASSET_BASE_URL = os.environ.get(
    "PUBLIC_ASSET_BASE_URL", "https://pradipbhuyan.github.io/likha-poha-promo-assets"
).strip()


def http_post_form(url, params):
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def image_url_for(asset_path):
    filename = asset_path.replace("\\", "/").split("/")[-1]
    return f"{PUBLIC_ASSET_BASE_URL}/{filename}"


def post_instagram(item):
    image_url = image_url_for(item["asset_path"])
    container = http_post_form(
        f"{GRAPH_API}/{IG_BUSINESS_ACCOUNT_ID}/media",
        {"image_url": image_url, "caption": item["caption"], "access_token": ACCESS_TOKEN},
    )
    creation_id = container["id"]
    http_post_form(
        f"{GRAPH_API}/{IG_BUSINESS_ACCOUNT_ID}/media_publish",
        {"creation_id": creation_id, "access_token": ACCESS_TOKEN},
    )


def main():
    with open(QUEUE_PATH) as f:
        queue = json.load(f)

    next_item = next((q for q in queue if q["status"] == "pending"), None)
    if next_item is None:
        print("Instagram post queue empty — nothing pending. Nothing to do.")
        return

    print(f"Posting {next_item['id']} (lang={next_item.get('lang', 'en')})...")
    try:
        post_instagram(next_item)
    except urllib.error.HTTPError as e:
        print(f"FAILED: {e.code} {e.read().decode('utf-8')}", file=sys.stderr)
        sys.exit(1)

    next_item["status"] = "posted"
    next_item["posted_at"] = datetime.now(timezone.utc).isoformat()

    with open(QUEUE_PATH, "w") as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)

    print(f"Posted and marked {next_item['id']} as posted.")


if __name__ == "__main__":
    main()
