"""Lifecycle: the daily sweep (sold-detection, asking-price tracking via Boligsiden with
the agency page as fallback, realized sold prices from Boligsiden). Network access is
behind seams (Prober, Boligsiden, Geocoder), so the core is tested against fakes and no
live network runs in the suite. Every sweep is best-effort: a failed probe or lookup
degrades to 'did less'."""
