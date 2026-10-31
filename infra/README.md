# infra: tidehours.com hosting

One CloudFormation stack, `tidehours-site`, in the `tidehours` AWS member
account (932775612205), region us-east-1 (the ACM certificate for CloudFront
must be there). `site.yaml` holds all of it:

- a private, versioned S3 bucket (`tidehours-site-<account>`) read only by
  CloudFront through Origin Access Control; old versions expire after 7 days
- an ACM certificate for tidehours.com and www.tidehours.com, validated by
  DNS in the hosted zone the registrar created
- the CloudFront distribution: HTTPS only (http redirects), TLS 1.2+,
  HTTP/2 and 3, IPv6, PriceClass_100, the managed CachingOptimized policy
- a viewer-request function: www to the apex (301), `/path` to `/path/`
  (301), `/path/` served from `/path/index.html`
- a response-headers policy: HSTS (1 year, no preload), a CSP that allows
  only this site and Google Analytics, nosniff, frame DENY, referrer and
  permissions policies
- 403 and 404 from the bucket served as `/404.html` with status 404
- Route 53 A and AAAA aliases for the apex and www
- the GitHub OIDC provider and the `tidehours-web-deploy` role, which only
  `repo:ChelseaKR/tidehours-web:ref:refs/heads/main` can assume, and which
  can only list, read, write and delete objects in this bucket and invalidate
  this distribution

No logging bucket and no WAF (cost). The repository variables
`AWS_DEPLOY_ROLE_ARN`, `SITE_BUCKET` and `CLOUDFRONT_DISTRIBUTION_ID` come
from the stack outputs.

## Apply

With credentials for the tidehours account (the owner's
`_agent-tools/aws-as-tidehours.sh` wrapper, for example):

    aws cloudformation deploy --region us-east-1 --stack-name tidehours-site \
      --template-file infra/site.yaml --capabilities CAPABILITY_NAMED_IAM \
      --parameter-overrides HostedZoneId=Z10333312RWVL9PZG9ZKF \
      --tags project=tidehours --no-fail-on-empty-changeset

Look at a change set first (`--no-execute-changeset`) for anything that
replaces the distribution or the bucket.

After a change to the function, test it on the real runtime:

    aws cloudfront test-function --name tidehours-viewer-request --stage LIVE \
      --if-match <ETag from describe-function> --event-object fileb://event.json

## Deploy

`publish.yml` does it daily: `scripts/deploy.sh <site> <bucket> <distribution>`
syncs with `--delete` (HTML: browsers 10 minutes, CloudFront a day; other
files: an hour and a day), invalidates `/*` and waits for it. It refuses a
build with fewer than 3,000 pages, so a partial build cannot empty the
bucket.

## Cost

About $1.20 a month: the hosted zone ($0.50), about 112,000 S3 PUTs from
the daily full upload (about $0.56), storage and Route 53 queries (cents).
CloudFront's always-free tier (1 TB and 10 million requests a month) and its
function allowance cover the traffic; ACM and IAM are free.
