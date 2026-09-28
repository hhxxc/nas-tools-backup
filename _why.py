#!/usr/bin/env python3
"""Pin down WHY the CN search returns 2 results and what they are."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.chdir("/nas-tools"); sys.path.insert(0, "/nas-tools")

from app.searcher import Searcher
from app.media import Media
from app.utils.types import MediaType

se = Searcher(); m = Media()
mi = m.get_media_info(title="特工 2018", mtype=MediaType.MOVIE, strict=True)
print("=== target ===")
print("  title           =", mi.title)
print("  org_string      =", mi.org_string)
print("  cn_name         =", mi.cn_name)
print("  en_name         =", mi.en_name)
print("  original_title  =", mi.original_title)
print("  tmdb_id         =", mi.tmdb_id)
print()

fa = {"year": "2018", "type": MediaType.MOVIE, "site": ["馒头"], "seeders": True}
print("=== CN search '特工' results in detail ===")
for x in (se.search_medias(key_word="特工", filter_args=dict(fa)) or []):
    print("  title=%-40s tmdb=%-9s year=%s seeders=%s" % (
        x.title[:40], x.tmdb_id, x.year, x.seeders))
    print("     org_string=%r original_title=%r" % (x.org_string, x.original_title))

print()
print("=== what the indexer's name_match actually compares ===")
print("  match_media.org_string     =", repr(mi.org_string))
print("  match_media.original_title =", repr(mi.original_title))
print("  -> 馒头 returns titles in ENGLISH (The Spy Gone North ...)")
print("  -> '特工' in 'The Spy Gone North...' =", "特工" in "The Spy Gone North 2018 1080p")
print("  -> '공작' in 'The Spy Gone North...' =", "공작" in "The Spy Gone North 2018 1080p")
print()
print("=== so how did '特工' match 2 results? check their raw titles ===")
en = se.search_medias(key_word="The Spy Gone North", filter_args=dict(fa)) or []
print("  EN search gives %d" % len(en))
for x in en[:3]:
    print("     %-58s tmdb=%s" % (x.title[:58], x.tmdb_id))
print("__DONE__")
