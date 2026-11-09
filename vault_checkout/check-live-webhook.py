"""Check the deployed Vault signature handler without creating a Stripe charge."""

import hashlib
import hmac
import json
import subprocess
import time
import urllib.request


PROJECT = "project-33f98d81-33a6-4270-840"
SERVICE = "maybloom-vault-live"
REGION = "asia-southeast1"
EXPECTED_URL = "https://maybloom-vault-live-402348584723.asia-southeast1.run.app"
SECRET = f"{SERVICE}-webhook"


def cloud(*args):
    return subprocess.check_output(["gcloud", f"--project={PROJECT}", "--quiet", *args])


def main():
    service = json.loads(cloud("run", "services", "describe", SERVICE, f"--region={REGION}", "--format=json"))
    env = service["spec"]["template"]["spec"]["containers"][0]["env"]
    secret_ref = next(item["valueFrom"]["secretKeyRef"] for item in env if item["name"] == "STRIPE_WEBHOOK_SECRET")
    if secret_ref["name"] != SECRET:
        raise SystemExit("Unexpected deployed signing secret reference.")
    secret = cloud("secrets", "versions", "access", secret_ref["key"], f"--secret={SECRET}").strip()

    timestamp = int(time.time())
    payload = json.dumps({
        "id": "evt_maybloom_webhook_smoke",
        "object": "event",
        "type": "vault.webhook.smoke_test",
        "livemode": True,
        "data": {"object": {}},
    }).encode()
    digest = hmac.new(secret, str(timestamp).encode() + b"." + payload, hashlib.sha256).hexdigest()
    request = urllib.request.Request(f"{EXPECTED_URL}/stripe/webhook", data=payload, headers={
        "Content-Type": "application/json",
        "Stripe-Signature": f"t={timestamp},v1={digest}",
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200 or json.load(response) != {"received": True}:
            raise SystemExit("Unexpected response from the live webhook.")
    print("Live signed webhook check passed (HTTP 200). No payment or order was created.")


if __name__ == "__main__":
    main()
