"""Import real chapters from the public null.community API v2.

Only PUBLIC data is available (chapters, and public events) — the API does
not expose user emails/PII, so this seeds the community's real chapter list
for the directory + map, not private member accounts.

Run: python manage.py import_null_community [--base URL] [--geocode]
  --base     API base (default https://null.community/api-v2)
  --geocode  run geocode_chapters afterwards to fill map coordinates
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.chapters.models import Chapter


class Command(BaseCommand):
    help = "Import chapters from the public null.community API v2."

    def add_arguments(self, parser):
        parser.add_argument("--base", default="https://null.community/api-v2")
        parser.add_argument("--geocode", action="store_true", help="geocode imported chapters afterwards")
        parser.add_argument("--activate", action="store_true", help="mark imported chapters active")

    def handle(self, *args, **opts):
        import requests

        base = opts["base"].rstrip("/")
        try:
            resp = requests.get(f"{base}/chapters", params={"all": "true"}, timeout=30)
            resp.raise_for_status()
            rows = resp.json()
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Failed to fetch {base}/chapters: {exc}"))
            return

        created = updated = 0
        for row in rows:
            name = (row.get("name") or "").strip()
            if not name:
                continue
            # Derive a unique subdomain; the API name may contain spaces ("Delhi NCR").
            sub = slugify(name)[:63]
            defaults = {
                "description": row.get("description") or f"The {name} chapter of null — the open security community.",
                "city": row.get("city") or name.split()[0],
                "country": row.get("country") or "India",
                "subdomain": sub,
            }
            if opts["activate"]:
                defaults["active"] = True
            obj, was_created = Chapter.objects.get_or_create(name=name, defaults=defaults)
            if was_created:
                created += 1
            else:
                # backfill city/subdomain if missing, without clobbering local edits
                changed = False
                if not obj.city and defaults["city"]:
                    obj.city = defaults["city"]; changed = True
                if not obj.subdomain:
                    obj.subdomain = sub; changed = True
                if changed:
                    obj.save()
                    updated += 1

        self.stdout.write(self.style.SUCCESS(f"Imported {created} new chapters, updated {updated} (total API rows: {len(rows)})."))
        if opts["geocode"]:
            self.stdout.write("Geocoding imported chapters...")
            call_command("geocode_chapters", "--all")
