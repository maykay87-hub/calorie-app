#!/usr/bin/env bash
# Deploy the standalone Vault delivery service from authenticated Google Cloud Shell.
set -euo pipefail

fail() { printf '%s\n' "$*" >&2; exit 1; }
vault_usage='Usage: bash deploy.sh test <PDF> <plink-id> | bash deploy.sh prepare-live <PDF> | bash deploy.sh live <PDF>'
[[ $# -ge 2 ]] || fail "$vault_usage"
vault_action="$1"
vault_pdf="$2"
case "$vault_action" in
  test)
    [[ $# -eq 3 && "$3" =~ ^plink_[a-zA-Z0-9]+$ ]] || fail "$vault_usage"
    vault_mode='test'
    vault_stripe_label='Stripe Sandbox'
    vault_match_env="STRIPE_PAYMENT_LINK_ID=$3"
    ;;
  prepare-live|live)
    [[ $# -eq 2 ]] || fail "$vault_usage"
    vault_mode='live'
    vault_stripe_label='Stripe Live'
    vault_match_env='VAULT_PAYMENT_LINK_KEY=eat-and-shop-smart-live'
    ;;
  *) fail "$vault_usage" ;;
esac

vault_project='project-33f98d81-33a6-4270-840'
vault_project_number='402348584723'
vault_region='asia-southeast1'
vault_service="maybloom-vault-${vault_mode}"
vault_label='eat-and-shop-smart'
vault_bucket="gs://${vault_service}-${vault_project_number}"
vault_service_account_id="${vault_service}-runtime"
vault_service_account="${vault_service_account_id}@${vault_project}.iam.gserviceaccount.com"
vault_secret_name="${vault_service}-webhook"
vault_pdf_sha='84e2a420379b6c82cffa59fe1966d816c1b760a1695a2c90491ee5647aa6f357'
vault_pdf_object="products/eat-and-shop-smart-${vault_pdf_sha}.pdf"
vault_expected_url="https://${vault_service}-${vault_project_number}.${vault_region}.run.app"
vault_source="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

cloud() { gcloud --project="$vault_project" --quiet "$@"; }

[[ -f "$vault_pdf" ]] || fail 'The PDF was not found. Upload it to Cloud Shell first.'
vault_actual_sha="$(sha256sum -- "$vault_pdf" | cut -d' ' -f1)"
[[ "$vault_actual_sha" == "$vault_pdf_sha" ]] || fail 'This is a different PDF. Use the approved 54-page file.'
command -v gcloud >/dev/null || fail 'Run this command inside Google Cloud Shell.'
[[ "$(cloud projects describe "$vault_project" --format='value(projectNumber)')" == "$vault_project_number" ]] ||
  fail 'Cloud Shell cannot access the expected May Bloom project.'

if vault_existing_label="$(cloud run services describe "$vault_service" --region="$vault_region" \
  --format='value(metadata.labels.vault-purpose)' 2>/dev/null)"; then
  [[ "$vault_existing_label" == "$vault_label" ]] || fail 'An unrelated Cloud Run service already uses this name.'
fi

if ! cloud iam service-accounts describe "$vault_service_account" >/dev/null 2>&1; then
  cloud iam service-accounts create "$vault_service_account_id" --display-name="May Bloom Vault ${vault_mode} runtime"
fi

if ! cloud storage buckets describe "$vault_bucket" --raw --format=json >/dev/null 2>&1; then
  cloud storage buckets create "$vault_bucket" --location="$vault_region" \
    --uniform-bucket-level-access --public-access-prevention
fi
cloud storage buckets describe "$vault_bucket" --raw --format=json |
  python3 -c 'import json,sys
bucket=json.load(sys.stdin)
iam=bucket.get("iamConfiguration",{})
if (str(bucket.get("projectNumber")) != sys.argv[1]
    or iam.get("publicAccessPrevention") != "enforced"
    or iam.get("uniformBucketLevelAccess",{}).get("enabled") is not True):
    sys.exit("Bucket ownership or privacy verification failed.")
' "$vault_project_number"
for vault_role in roles/storage.objectViewer roles/storage.objectCreator; do
  cloud storage buckets add-iam-policy-binding "$vault_bucket" \
    --member="serviceAccount:${vault_service_account}" --role="$vault_role"
done
cloud storage cp --no-clobber "$vault_pdf" "${vault_bucket}/${vault_pdf_object}"

vault_secret_args=()
if [[ "$vault_action" != prepare-live ]]; then
  if ! cloud secrets describe "$vault_secret_name" >/dev/null 2>&1; then
    cloud secrets create "$vault_secret_name" --replication-policy=automatic --labels="vault-purpose=${vault_label}"
  fi
  [[ "$(cloud secrets describe "$vault_secret_name" --format='value(labels.vault-purpose)')" == "$vault_label" ]] ||
    fail 'An unrelated Secret Manager entry already uses this name.'
  vault_version="$(cloud secrets versions list "$vault_secret_name" --filter='state=ENABLED' \
    --sort-by='~createTime' --limit=1 --format='value(name)')"
  if [[ -z "$vault_version" ]]; then
    printf 'Paste the %s webhook Signing secret (hidden), then press Enter: ' "$vault_stripe_label" >&2
    IFS= read -rs vault_signing_secret </dev/tty
    printf '\n' >&2
    [[ "$vault_signing_secret" =~ ^whsec_[A-Za-z0-9]+$ ]] || fail 'Expected a Stripe webhook signing secret starting whsec_.'
    vault_version="$(printf '%s' "$vault_signing_secret" |
      cloud secrets versions add "$vault_secret_name" --data-file=- --format='value(name)')"
    unset vault_signing_secret
  fi
  vault_version="${vault_version##*/}"
  [[ "$vault_version" =~ ^[0-9]+$ ]] || fail 'Could not identify the signing secret version.'
  cloud secrets add-iam-policy-binding "$vault_secret_name" \
    --member="serviceAccount:${vault_service_account}" --role='roles/secretmanager.secretAccessor'
  vault_secret_args+=(--set-secrets="STRIPE_WEBHOOK_SECRET=${vault_secret_name}:${vault_version}")
fi

cloud run deploy "$vault_service" --source="$vault_source" --region="$vault_region" \
  --service-account="$vault_service_account" --allow-unauthenticated \
  --labels="vault-purpose=${vault_label}" --min-instances=0 --max-instances=2 \
  --update-env-vars="STRIPE_MODE=${vault_mode},${vault_match_env},VAULT_BUCKET=${vault_bucket#gs://},VAULT_PDF_OBJECT=${vault_pdf_object}" \
  "${vault_secret_args[@]}"

curl --fail --silent --show-error "${vault_expected_url}/health"
printf '\n'
vault_status="$(curl --silent --show-error -o /dev/null -w '%{http_code}' \
  -H 'Content-Type: application/json' --data "{\"session_id\":\"cs_${vault_mode}_AAAAAAAAAAAAAAAAAAAAAAAAA\"}" \
  "${vault_expected_url}/download")"
[[ "$vault_status" == 403 ]] || fail "Unpaid download check returned HTTP ${vault_status}, expected 403."
if [[ "$vault_action" == prepare-live ]]; then
  printf 'Live delivery endpoint prepared. Unpaid download blocked (HTTP 403).\n%s\n' "$vault_expected_url"
else
  printf '%s service ready. Unpaid download blocked (HTTP 403).\n%s\n' "$vault_stripe_label" "$vault_expected_url"
fi
