"""Location enrichment: DAWA geocoding, OpenRouteService routing, and the GeoFA
school-district map embed. Network access is behind seams (Geocoder, Router) so the
core is tested against fakes and no live API call runs in the suite."""
