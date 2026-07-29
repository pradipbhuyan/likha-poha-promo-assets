"""Post the next pending item in queue/content_queue.json to Instagram or WhatsApp.

Run daily by .github/workflows/daily-post.yml. Uses only the Python standard
library (urllib) so the GitHub Actions job needs no pip install step.
"""
import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

GRAPH_API = "https://graph.facebook.com/v20.0"
QUEUE_PATH = os.path.join(os.path.dirname(__file__), "..", "queue", "content_queue.json")

ACCESS_TOKEN = os.environ["META_ACCESS_TOKEN"].strip()
IG_BUSINESS_ACCOUNT_ID = os.environ["IG_BUSINESS_ACCOUNT_ID"].strip()
WHATSAPP_PHONE_NUMBER_ID = os.environ["WHATSAPP_PHONE_NUMBER_ID"].strip()
WHATSAPP_TEST_RECIPIENT = os.environ["WHATSAPP_TEST_RECIPIENT"].strip()
PUBLIC_ASSET_BASE_URL = os.environ.get(
    "PUBLIC_ASSET_BASE_URL", "https://pradipbhuyan.github.io/likha-poha-promo-assets"
).strip()


def http_post_form(url, params):
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_post_json(url, payload, headers):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers=headers)
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


def post_whatsapp(item):
    image_url = image_url_for(item["asset_path"])
    http_post_json(
        f"{GRAPH_API}/{WHATSAPP_PHONE_NUMBER_ID}/messages",
        {
            "messaging_product": "whatsapp",
            "to": WHATSAPP_TEST_RECIPIENT,
            "type": "image",
            "image": {"link": image_url, "caption": item["caption"]},
        },
        {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"},
    )


def main():
    with open(QUEUE_PATH) as f:
        queue = json.load(f)

    next_item = next((q for q in queue if q["status"] == "pending"), None)
    if next_item is None:
        print("Queue empty — nothing pending. Nothing to do.")
        return

    print(f"Posting {next_item['id']} ({next_item['channel']})...")
    try:
        if next_item["channel"] == "instagram":
            post_instagram(next_item)
        elif next_item["channel"] == "whatsapp":
            post_whatsapp(next_item)
        else:
            raise ValueError(f"Unknown channel: {next_item['channel']}")
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
