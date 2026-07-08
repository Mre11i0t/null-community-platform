from .base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["null.community"])  # noqa: F405

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Under HTTPS + DEBUG=False Django enforces the CSRF Origin/Referer check, so
# form POSTs (login, RSVP, comments) 403 unless the scheme+host is trusted.
# The wildcard covers every chapter subdomain in one entry.
CSRF_TRUSTED_ORIGINS = env.list(  # noqa: F405
    "CSRF_TRUSTED_ORIGINS",
    default=[f"https://{ROOT_DOMAIN}", f"https://*.{ROOT_DOMAIN}"],  # noqa: F405
)

AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="")  # noqa: F405
AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="ap-south-1")  # noqa: F405

# Static: WhiteNoise compressed serving (gzip/brotli). We deliberately use
# CompressedStaticFilesStorage and NOT the *Manifest* variant: the vendored
# Bootstrap/Bootswatch CSS carries a few dangling asset references (e.g.
# css/home.css -> images/bg2.png), and the manifest backend's strict
# reference-rewriting turns each one into a hard collectstatic failure that
# blocks the whole deploy. Without the manifest, a dangling asset simply
# 404s on its own while every real file still serves compressed. (Trade-off:
# no hashed-filename cache-busting. Fix the dangling refs, then switch back
# to CompressedManifestStaticFilesStorage if you want it.)
# Media: S3 when a bucket is set, else local disk so a keyless deployment
# still stores uploads (see MEDIA serving note in urls.py for the local case).
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage"
        if AWS_STORAGE_BUCKET_NAME
        else "django.core.files.storage.FileSystemStorage"
    },
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

REQUIRE_2FA_FOR_PRIVILEGED = env.bool("REQUIRE_2FA_FOR_PRIVILEGED", default=True)  # noqa: F405
