#!/usr/bin/env python3
"""Verify the fallback decision in isolation, using the real Searcher methods."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.chdir("/nas-tools"); sys.path.insert(0, "/nas-tools")

from app.searcher import Searcher
from app.media import Media
from app.utils.types import MediaType, SearchType

se = Searcher()
m = Media()
H = se._Searcher__has_matched_media

print("=== A. __has_matched_media exists and behaves ===")
mi = m.get_media_info(title="特工 2018", mtype=MediaType.MOVIE, strict=True)
if mi and mi.tmdb_id:
    print("  target tmdb =", mi.tmdb_id, "en_title =", m.get_tmdb_en_title(mi))
    # build fake results
    class R:
        def __init__(self, t, n, y):
            self.tmdb_id, self._n, self.year = t, n, y
        def get_name(self): return self._n
    wrong = [R("454992", "我的间谍前男友", "2018")]
    right = [R("517991", "特工", "2018")]
    print("  wrong-only  -> has_matched =", H(wrong, mi), "(expect False)")
    print("  right       -> has_matched =", H(right, mi), "(expect True)")
    print("  mixed       -> has_matched =", H(wrong + right, mi), "(expect True)")
    print("  empty       -> has_matched =", H([], mi), "(expect False)")
else:
    print("  TMDB unavailable")

print()
print("=== B. search 馒头 only, CN vs EN keyword ===")
fa = {"year": "2018", "type": MediaType.MOVIE, "site": ["馒头"], "seeders": True}
for kw in ("特工", "The Spy Gone North"):
    try:
        r = se.search_medias(key_word=kw, filter_args=dict(fa))
        matched = H(r, mi) if mi else None
        print("  %-22r -> %2d results, has_matched=%s" % (kw, len(r or []), matched))
    except Exception as e:
        print("  %-22r -> EXC %s" % (kw, str(e)[:90]))

print()
print("=== C. simulate the new decision ===")
if mi:
    cn = se.search_medias(key_word="特工", filter_args=dict(fa))
    need_fb = not H(cn, mi)
    print("  CN search gives %d results; needs fallback? %s" % (len(cn or []), need_fb))
    if need_fb:
        en = se.search_medias(key_word="The Spy Gone North", filter_args=dict(fa))
        print("  EN search gives %d results; has_matched=%s" % (len(en or []), H(en, mi)))
        print("  -> would adopt EN results: %s" % bool(en and H(en, mi)))
print("__DONE__")
