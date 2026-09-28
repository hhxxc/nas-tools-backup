#!/usr/bin/env python3
"""Correct test: pass match_media, only 馒头, see the REAL subscription search result."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.chdir("/nas-tools"); sys.path.insert(0, "/nas-tools")

from app.searcher import Searcher
from app.media import Media
from app.utils.types import MediaType

se = Searcher(); m = Media()
mi = m.get_media_info(title="特工 2018", mtype=MediaType.MOVIE, strict=True)
print("target: %s (%s) tmdb=%s" % (mi.title, mi.year, mi.tmdb_id))

fa = {"year": "2018", "type": MediaType.MOVIE, "site": ["馒头"], "seeders": True}

print()
print("=== CN keyword WITH match_media (this is the real subscription call) ===")
cn = se.search_medias(key_word="特工", filter_args=dict(fa), match_media=mi)
print("  -> %d results" % len(cn or []))
for x in (cn or [])[:5]:
    print("     %-52s tmdb=%s seeders=%s" % (x.title[:52], x.tmdb_id, x.seeders))

print()
print("=== EN keyword WITH match_media ===")
en = se.search_medias(key_word="The Spy Gone North", filter_args=dict(fa), match_media=mi)
print("  -> %d results" % len(en or []))
for x in (en or [])[:5]:
    print("     %-52s tmdb=%s seeders=%s" % (x.title[:52], x.tmdb_id, x.seeders))

print()
print("=== conclusion ===")
print("  CN matched=%s  EN matched=%s" % (bool(cn), bool(en)))
print("__DONE__")
