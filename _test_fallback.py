"""Local unit test for the search-fallback condition (no network)."""


def has_matched(media_list, media_info):
    """Mirror of Searcher.__has_matched_media."""
    if not media_list:
        return False
    if not media_info:
        return True
    target = str(media_info["tmdb_id"]) if media_info.get("tmdb_id") else None
    for m in media_list:
        if target:
            if str(m["tmdb_id"]) == target:
                return True
        elif m.get("tmdb_id") is None:
            if m["name"] == media_info.get("name") and str(m["year"]) == str(media_info.get("year")):
                return True
    return False


def should_fallback(first_list, second_name, first_name, media_info):
    """Mirror of the new fallback condition in search_one_media."""
    if second_name and second_name != first_name and not has_matched(first_list, media_info):
        return True
    return False


def check(label, cond):
    print("  [%s] %s" % ("PASS" if cond else "FAIL", label))
    return cond


TARGET = {"tmdb_id": "517991", "name": "特工", "year": "2018"}
CN, EN = "特工", "The Spy Gone North"

print("=== 1. 复现 bug：中文名有 2 条无关结果 ===")
cn_only_wrong = [{"tmdb_id": "454992", "name": "我的间谍前男友", "year": "2018"},
                 {"tmdb_id": "517991", "name": "特工", "year": "2018"}]
# 旧逻辑：len != 0 -> 不回退
old_fallback = len(cn_only_wrong) == 0
check("旧逻辑不回退（这就是搜不到的原因）", old_fallback is False)

print()
print("=== 2. 中文名全是无关结果 -> 应该回退 ===")
cn_wrong = [{"tmdb_id": "454992", "name": "我的间谍前男友", "year": "2018"}]
check("新逻辑判定需要回退", should_fallback(cn_wrong, EN, CN, TARGET) is True)

print()
print("=== 3. 中文名已有正确命中 -> 不该回退 ===")
cn_right = [{"tmdb_id": "517991", "name": "特工", "year": "2018"}]
check("已有正确命中，不触发回退", should_fallback(cn_right, EN, CN, TARGET) is False)

print()
print("=== 4. 混合结果（含正确命中）-> 不该回退 ===")
check("混合结果不触发回退",
      should_fallback(cn_only_wrong, EN, CN, TARGET) is False)

print()
print("=== 5. 英文名搜到正确结果 -> 替换 ===")
en_right = [{"tmdb_id": "517991", "name": "特工", "year": "2018"}]
check("英文结果含正确命中，会被采纳", has_matched(en_right, TARGET) is True)

print()
print("=== 6. 英文名也没命中 -> 保留原有结果（不丢）===")
en_wrong = [{"tmdb_id": "1", "name": "Other", "year": "2018"}]
check("英文结果未命中，不会被采纳", has_matched(en_wrong, TARGET) is False)

print()
print("=== 7. 没有第二个名字时不应回退 ===")
check("second_name 为空不回退", should_fallback(cn_wrong, None, CN, TARGET) is False)
check("两个名字相同时不回退", should_fallback(cn_wrong, CN, CN, TARGET) is False)

print()
print("=== 8. 空结果仍应回退（保持原行为）===")
check("空结果触发回退", should_fallback([], EN, CN, TARGET) is True)

print()
print("=== 9. media_info 无 tmdb_id 时退化为名称+年份 ===")
t2 = {"tmdb_id": None, "name": "某片", "year": "2001"}
check("名称年份一致算命中",
      has_matched([{"tmdb_id": None, "name": "某片", "year": "2001"}], t2) is True)
check("名称一致但年份不同不算命中",
      has_matched([{"tmdb_id": None, "name": "某片", "year": "2002"}], t2) is False)
