"""Fill Chapter.latitude/longitude for the root-directory pin map.

Strategy (no hard dependency on a paid/enabled Geocoding API):
  1. A built-in lookup of the known null chapter cities (offline, instant).
  2. Google Geocoding API for anything not in the table, IF
     GOOGLE_MAPS_API_KEY is set AND the Geocoding API is enabled.
  3. Anything still unresolved is left null and simply not plotted.

Run: python manage.py geocode_chapters [--all] [--force]
  --all    also geocode inactive chapters
  --force  re-geocode chapters that already have coordinates
"""

from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.chapters.models import Chapter

# Known null / major Indian city coordinates (lat, lng). Keyed by a
# normalized name so "Delhi NCR", "Delhi-NCR", "delhi" all resolve.
KNOWN_CITIES = {
    "bangalore": (12.9716, 77.5946),
    "bengaluru": (12.9716, 77.5946),
    "delhi": (28.6139, 77.2090),
    "delhi ncr": (28.6139, 77.2090),
    "new delhi": (28.6139, 77.2090),
    "mumbai": (19.0760, 72.8777),
    "pune": (18.5204, 73.8567),
    "hyderabad": (17.3850, 78.4867),
    "chennai": (13.0827, 80.2707),
    "kolkata": (22.5726, 88.3639),
    "haryana": (29.0588, 76.0856),
    "chandigarh": (30.7333, 76.7794),
    "ahmedabad": (23.0225, 72.5714),
    "kochi": (9.9312, 76.2673),
    "cochin": (9.9312, 76.2673),
    "trivandrum": (8.5241, 76.9366),
    "thiruvananthapuram": (8.5241, 76.9366),
    "bhopal": (23.2599, 77.4126),
    "indore": (22.7196, 75.8577),
    "jaipur": (26.9124, 75.7873),
    "coimbatore": (11.0168, 76.9558),
    "nagpur": (21.1458, 79.0882),
    "vizag": (17.6868, 83.2185),
    "visakhapatnam": (17.6868, 83.2185),
    "bhubaneswar": (20.2961, 85.8245),
    "guwahati": (26.1445, 91.7362),
    "goa": (15.2993, 74.1240),
    "surat": (21.1702, 72.8311),
    "mangalore": (12.9141, 74.8560),
    "mysore": (12.2958, 76.6394),
    "mysuru": (12.2958, 76.6394),
    "dubai": (25.2048, 55.2708),
    "singapore": (1.3521, 103.8198),
    "london": (51.5074, -0.1278),
}


def _normalize(name):
    return " ".join((name or "").lower().replace("-", " ").split())


class Command(BaseCommand):
    help = "Geocode chapters (city -> lat/lng) for the directory pin map."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="include inactive chapters")
        parser.add_argument("--force", action="store_true", help="re-geocode chapters that already have coords")

    def handle(self, *args, **opts):
        from django.conf import settings

        qs = Chapter.objects.all() if opts["all"] else Chapter.objects.filter(active=True)
        if not opts["force"]:
            qs = qs.filter(latitude__isnull=True)

        api_key = getattr(settings, "GOOGLE_MAPS_API_KEY", "")
        resolved = skipped = 0
        for chapter in qs:
            coords = self._lookup(chapter) or (self._geocode_api(chapter, api_key) if api_key else None)
            if coords:
                chapter.latitude = Decimal(str(round(coords[0], 6)))
                chapter.longitude = Decimal(str(round(coords[1], 6)))
                chapter.save(update_fields=["latitude", "longitude", "updated_at"])
                resolved += 1
                self.stdout.write(f"  {chapter.name}: {coords[0]:.4f}, {coords[1]:.4f}")
            else:
                skipped += 1
                self.stdout.write(self.style.WARNING(f"  {chapter.name}: no coordinates (left unplotted)"))
        self.stdout.write(self.style.SUCCESS(f"Geocoded {resolved}, skipped {skipped}."))

    def _lookup(self, chapter):
        for candidate in (chapter.city, chapter.name):
            hit = KNOWN_CITIES.get(_normalize(candidate))
            if hit:
                return hit
        return None

    def _geocode_api(self, chapter, api_key):
        import requests

        query = ", ".join(p for p in [chapter.city or chapter.name, chapter.state, chapter.country or "India"] if p)
        try:
            resp = requests.get(
                "https://maps.googleapis.com/maps/api/geocode/json",
                params={"address": query, "key": api_key},
                timeout=15,
            )
            data = resp.json()
            if data.get("status") == "OK":
                loc = data["results"][0]["geometry"]["location"]
                return (loc["lat"], loc["lng"])
            self.stdout.write(self.style.WARNING(f"    geocode API status={data.get('status')} for {query!r}"))
        except Exception as exc:  # network / JSON / key issues -> leave unplotted
            self.stdout.write(self.style.WARNING(f"    geocode API error for {query!r}: {exc}"))
        return None
