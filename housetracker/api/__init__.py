"""The JSON API (spec §4, §10): a thin FastAPI layer over the M1-M5 core. No business
logic lives here — routes validate input, call the store/scoring/scrape/enrich/lifecycle
modules, and serialize the result. Bound to the tailnet; membership is the auth."""
