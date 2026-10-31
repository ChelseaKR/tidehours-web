#!/usr/bin/env bash
# Sync a built site to the tidehours.com bucket and invalidate CloudFront.
#
#   scripts/deploy.sh <site-dir> <bucket> <distribution-id>
#
# Used by publish.yml's deploy job (hosted runner, OIDC credentials) and for
# the first deploy by hand. Needs AWS credentials in the environment and
# nothing else; it never prints them.
#
# Cache-Control per type. HTML changes every day, so browsers keep it for
# 10 minutes; CloudFront keeps it for a day and every deploy invalidates
# "/*". style.css is not fingerprinted, so it gets a day, not a year.
#
# Two passes, each with --delete over only its own files, so every stale file
# is removed and nothing is uploaded without its Cache-Control.
set -euo pipefail

site=${1:?usage: deploy.sh <site-dir> <bucket> <distribution-id>}
bucket=${2:?bucket}
distribution=${3:?distribution id}

# Refuse to sync something that is not a full build: --delete would empty
# the bucket.
test -f "$site/index.html"
test -f "$site/404.html"
test -f "$site/sitemap.xml"
pages=$(find "$site" -name '*.html' -type f | wc -l | tr -d ' ')
if [ "$pages" -lt 3000 ]; then
  echo "deploy: only $pages HTML files in $site; refusing to sync with --delete" >&2
  exit 1
fi

aws s3 sync "$site" "s3://$bucket" --delete --only-show-errors \
  --exclude '*' --include '*.html' \
  --content-type 'text/html; charset=utf-8' \
  --cache-control 'public, max-age=600, s-maxage=86400'

aws s3 sync "$site" "s3://$bucket" --delete --only-show-errors \
  --exclude '*.html' \
  --cache-control 'public, max-age=3600, s-maxage=86400'

id=$(aws cloudfront create-invalidation --distribution-id "$distribution" \
  --paths '/*' --query 'Invalidation.Id' --output text)
if [ -z "$id" ] || [ "$id" = "None" ]; then
  echo "deploy: no invalidation id returned" >&2
  exit 1
fi
aws cloudfront wait invalidation-completed --distribution-id "$distribution" --id "$id"
echo "deploy: synced $pages pages to s3://$bucket; invalidation $id complete"
