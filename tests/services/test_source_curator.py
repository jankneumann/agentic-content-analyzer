"""Tests for source curation: health classification, plan building, and the
line-based YAML mutation that must preserve comments/ordering."""

from __future__ import annotations

import yaml

from src.services.source_curator import (
    CurationPlan,
    FeedHealth,
    FeedStatus,
    MovedCandidate,
    _candidate_feed_urls,
    _identity_tokens,
    _youtube_channel_rss_fix,
    apply_plan_to_text,
    apply_relocations_to_text,
    best_to_candidate,
    build_curation_plan,
    detect_overlaps,
)


def _h(url, status, name="", detail=""):
    return FeedHealth(url=url, name=name or url, status=status, detail=detail)


# --- build_curation_plan policy ---


def test_failing_feeds_are_disabled():
    results = [
        _h("https://a/feed", FeedStatus.FAIL_HTTP, detail="404"),
        _h("https://b/feed", FeedStatus.FAIL_NET, detail="ConnectError"),
        _h("https://c/feed", FeedStatus.OK),
    ]
    plan = build_curation_plan(results)
    assert {h.url for h in plan.disable} == {"https://a/feed", "https://b/feed"}


def test_reddit_empty_is_rewritten_not_disabled():
    results = [_h("https://www.reddit.com/r/MachineLearning", FeedStatus.EMPTY)]
    plan = build_curation_plan(results)
    assert plan.disable == []
    assert plan.rewrite == [(results[0], "https://www.reddit.com/r/MachineLearning/.rss")]


def test_youtube_channel_page_empty_is_rewritten_to_feed():
    # a pasted channel-page URL parses to 0 entries -> rewrite to the Atom feed,
    # never disable (mirrors the Reddit /.rss fix for YouTube sources)
    results = [_h("https://www.youtube.com/channel/UCabc123_DEF", FeedStatus.EMPTY)]
    plan = build_curation_plan(results)
    assert plan.disable == []
    assert plan.rewrite == [
        (results[0], "https://www.youtube.com/feeds/videos.xml?channel_id=UCabc123_DEF")
    ]


def test_youtube_videos_xml_empty_is_disabled_not_rewritten():
    # an actual channel feed that is genuinely empty (no uploads) has no fix and
    # should be disabled like any other dead feed
    url = "https://www.youtube.com/feeds/videos.xml?channel_id=UCdeadchannel0000000000"
    results = [_h(url, FeedStatus.EMPTY)]
    plan = build_curation_plan(results)
    assert plan.rewrite == []
    assert [h.url for h in plan.disable] == [url]


def test_arxiv_empty_is_kept_flagged():
    results = [_h("https://arxiv.org/rss/cs.LG", FeedStatus.EMPTY)]
    plan = build_curation_plan(results)
    assert plan.disable == []
    assert [h.url for h in plan.keep_flagged] == ["https://arxiv.org/rss/cs.LG"]


def test_generic_empty_is_disabled():
    results = [_h("https://dead.example/feed", FeedStatus.EMPTY)]
    assert build_curation_plan(results).disable[0].url == "https://dead.example/feed"


def test_blocked_is_kept_flagged_by_default():
    results = [_h("https://blocked.example/feed", FeedStatus.BLOCKED, detail="403")]
    plan = build_curation_plan(results)
    assert plan.disable == []
    assert [h.url for h in plan.keep_flagged] == ["https://blocked.example/feed"]


def test_blocked_disabled_only_when_opted_in():
    results = [_h("https://blocked.example/feed", FeedStatus.BLOCKED, detail="403")]
    plan = build_curation_plan(results, disable_blocked=True)
    assert [h.url for h in plan.disable] == ["https://blocked.example/feed"]


def test_stale_disabled_only_when_opted_in():
    results = [_h("https://old.example/feed", FeedStatus.STALE)]
    assert build_curation_plan(results).disable == []
    assert build_curation_plan(results, disable_stale=True).disable[0].url == (
        "https://old.example/feed"
    )


# --- apply_plan_to_text: must stay valid YAML and preserve comments ---


def test_disable_bare_url_entry():
    text = "sources:\n- url: https://dead/feed\n- url: https://live/feed\n"
    plan = CurationPlan(disable=[_h("https://dead/feed", FeedStatus.FAIL_HTTP)])
    new, stats = apply_plan_to_text(text, plan)
    assert stats["disabled"] == 1
    data = yaml.safe_load(new)["sources"]
    assert {"url": "https://dead/feed", "enabled": False} in data
    assert {"url": "https://live/feed"} in data


def test_disable_name_url_entry_preserves_comment():
    text = (
        "sources:\n# keep this comment\n- name: Dead Feed\n  url: https://dead/feed\n  tags: [ai]\n"
    )
    plan = CurationPlan(disable=[_h("https://dead/feed", FeedStatus.FAIL_HTTP)])
    new, _ = apply_plan_to_text(text, plan)
    assert "# keep this comment" in new
    entry = yaml.safe_load(new)["sources"][0]
    assert entry["enabled"] is False
    assert entry["name"] == "Dead Feed"
    assert entry["tags"] == ["ai"]


def test_disable_replaces_existing_enabled_true():
    text = "sources:\n- name: X\n  url: https://x/feed\n  enabled: true\n"
    plan = CurationPlan(disable=[_h("https://x/feed", FeedStatus.FAIL_HTTP)])
    new, _ = apply_plan_to_text(text, plan)
    # exactly one enabled key, set to false (no duplicate-key YAML error)
    assert new.count("enabled:") == 1
    assert yaml.safe_load(new)["sources"][0]["enabled"] is False


def test_rewrite_reddit_url():
    text = "sources:\n- url: https://www.reddit.com/r/ML\n"
    plan = CurationPlan(
        rewrite=[
            (
                _h("https://www.reddit.com/r/ML", FeedStatus.EMPTY),
                "https://www.reddit.com/r/ML/.rss",
            )
        ]
    )
    new, stats = apply_plan_to_text(text, plan)
    assert stats["rewritten"] == 1
    assert yaml.safe_load(new)["sources"][0]["url"] == "https://www.reddit.com/r/ML/.rss"


def test_idempotent_reapply():
    text = "sources:\n- url: https://dead/feed\n"
    plan = CurationPlan(disable=[_h("https://dead/feed", FeedStatus.FAIL_HTTP)])
    once, _ = apply_plan_to_text(text, plan)
    twice, _ = apply_plan_to_text(once, plan)
    # url line still present so it re-inserts; guard: the loader must not crash and
    # the second pass should not corrupt YAML.
    assert yaml.safe_load(twice)["sources"][0]["enabled"] is False


def test_quoted_url_value_matches():
    text = 'sources:\n- url: "https://dead/feed"\n'
    plan = CurationPlan(disable=[_h("https://dead/feed", FeedStatus.FAIL_HTTP)])
    new, stats = apply_plan_to_text(text, plan)
    assert stats["disabled"] == 1
    assert yaml.safe_load(new)["sources"][0]["enabled"] is False


def test_unrelated_url_untouched():
    text = "sources:\n- url: https://keep/feed\n"
    plan = CurationPlan(disable=[_h("https://other/feed", FeedStatus.FAIL_HTTP)])
    new, stats = apply_plan_to_text(text, plan)
    assert new == text
    assert stats["disabled"] == 0


# --- overlap detection ---


class _S:
    def __init__(self, url):
        self.url = url
        self.name = url


def test_detect_overlaps_same_host_and_path_prefix():
    # feed and blog index on the same site (www. and /rss stripped) -> overlap
    rss = [_S("https://www.together.ai/blog/rss"), _S("https://other.com/feed")]
    blogs = [_S("https://together.ai/blog"), _S("https://anthropic.com/news")]
    overlaps = detect_overlaps(rss, blogs)
    assert [o.domain for o in overlaps] == ["together.ai"]
    assert overlaps[0].blog_urls == ["https://together.ai/blog"]


def test_sibling_subblogs_on_shared_host_not_flagged():
    # different sub-blogs on aws.amazon.com must NOT be treated as redundant
    rss = [_S("https://aws.amazon.com/blogs/machine-learning/feed/")]
    blogs = [
        _S("https://aws.amazon.com/blogs/architecture/"),
        _S("https://aws.amazon.com/blogs/aws/"),
    ]
    assert detect_overlaps(rss, blogs) == []


def test_different_subdomains_not_flagged():
    # crfm.stanford.edu (feed) vs hai.stanford.edu (blog) are distinct orgs
    rss = [_S("https://crfm.stanford.edu/feed")]
    blogs = [_S("https://hai.stanford.edu/news")]
    assert detect_overlaps(rss, blogs) == []


# --- find-moved candidate derivation ---


def test_candidate_urls_skips_aggregators():
    results = [
        "https://muckrack.com/media-outlet/semianalysis",
        "https://x.com/SemiAnalysis_",
        "https://newsletter.semianalysis.com/about",
    ]
    cands = _candidate_feed_urls(results)
    # aggregator/social hosts dropped; real host seeds feed guesses
    assert all("muckrack" not in c and "x.com" not in c for c in cands)
    assert "https://newsletter.semianalysis.com/feed" in cands


def test_candidate_urls_uses_feed_looking_url_as_is():
    results = ["https://blog.example.com/rss.xml"]
    cands = _candidate_feed_urls(results)
    assert cands[0] == "https://blog.example.com/rss.xml"


def test_best_to_candidate_none_means_not_found():
    c = best_to_candidate("https://dead/feed", "Dead", None)
    assert c.new_url is None
    assert c.detail == "no fresh feed found"


def test_relocation_reenables_and_rewrites_moved_feed():
    text = "sources:\n- name: SemiAnalysis\n  url: https://old.semi/feed\n  enabled: false\n"
    cands = [MovedCandidate("https://old.semi/feed", "SemiAnalysis", "https://new.semi/feed", "ok")]
    new, stats = apply_relocations_to_text(text, cands)
    assert stats == {"reenabled": 1, "rewritten": 1}
    entry = yaml.safe_load(new)["sources"][0]
    assert entry["url"] == "https://new.semi/feed"
    assert entry["enabled"] is True
    assert entry["name"] == "SemiAnalysis"


def test_relocation_live_again_only_reenables():
    # new_url == original_url -> re-enable in place, no URL rewrite
    text = "sources:\n- url: https://x/feed\n  enabled: false\n"
    cands = [MovedCandidate("https://x/feed", "X", "https://x/feed", "live")]
    new, stats = apply_relocations_to_text(text, cands)
    assert stats == {"reenabled": 1, "rewritten": 0}
    entry = yaml.safe_load(new)["sources"][0]
    assert entry["url"] == "https://x/feed"
    assert entry["enabled"] is True


def test_relocation_rewrites_enabled_stale_feed_without_recount():
    # an enabled (not disabled) feed that relocated: rewrite URL, reenabled stays 0
    text = "sources:\n- url: https://stale/feed\n"
    cands = [MovedCandidate("https://stale/feed", "S", "https://fresh/feed", "moved")]
    new, stats = apply_relocations_to_text(text, cands)
    assert stats == {"reenabled": 0, "rewritten": 1}
    assert yaml.safe_load(new)["sources"][0]["url"] == "https://fresh/feed"


def test_relocation_preserves_comments():
    text = (
        "sources:\n# semianalysis moved to substack\n"
        "- name: SemiAnalysis\n  url: https://old/feed\n  enabled: false\n  tags: [ai]\n"
    )
    cands = [MovedCandidate("https://old/feed", "SemiAnalysis", "https://new/feed", "ok")]
    new, _ = apply_relocations_to_text(text, cands)
    assert "# semianalysis moved to substack" in new
    entry = yaml.safe_load(new)["sources"][0]
    assert entry["enabled"] is True
    assert entry["tags"] == ["ai"]


def test_relocation_ignores_not_found_candidates():
    text = "sources:\n- url: https://x/feed\n  enabled: false\n"
    cands = [MovedCandidate("https://x/feed", "X", None, "no fresh feed found")]
    new, stats = apply_relocations_to_text(text, cands)
    assert new == text
    assert stats == {"reenabled": 0, "rewritten": 0}


def test_relocation_idempotent_reapply():
    text = "sources:\n- url: https://old/feed\n  enabled: false\n"
    cands = [MovedCandidate("https://old/feed", "X", "https://new/feed", "ok")]
    once, _ = apply_relocations_to_text(text, cands)
    # second pass: the original URL is gone, so nothing matches -> no-op
    twice, stats = apply_relocations_to_text(once, cands)
    assert twice == once
    assert stats == {"reenabled": 0, "rewritten": 0}


def test_youtube_channel_rss_fix_rewrites_channel_page_url():
    assert (
        _youtube_channel_rss_fix("https://www.youtube.com/channel/UCabc-123_X")
        == "https://www.youtube.com/feeds/videos.xml?channel_id=UCabc-123_X"
    )
    # trailing slash and m. mobile host both normalize
    assert (
        _youtube_channel_rss_fix("https://m.youtube.com/channel/UCabc123/")
        == "https://www.youtube.com/feeds/videos.xml?channel_id=UCabc123"
    )


def test_youtube_channel_rss_fix_leaves_feeds_and_handles_alone():
    # already a feed URL -> no fix
    assert (
        _youtube_channel_rss_fix(
            "https://www.youtube.com/feeds/videos.xml?channel_id=UCabc123"
        )
        is None
    )
    # @handle can't be resolved to a channel id without an API call -> no fix
    assert _youtube_channel_rss_fix("https://www.youtube.com/@somehandle") is None
    # non-YouTube host -> no fix
    assert _youtube_channel_rss_fix("https://example.com/channel/UCabc123") is None


def test_identity_tokens_extract_publication_terms():
    # domain label + meaningful name words, minus generic stopwords
    toks = _identity_tokens("SemiAnalysis", "https://www.semianalysis.com/feed")
    assert "semianalysis" in toks

    # "Artificialis - Medium": platform label "medium" is a stopword, brand kept
    toks = _identity_tokens("Artificialis - Medium", "https://medium.com/feed/artificialis")
    assert "artificialis" in toks
    assert "medium" not in toks

    # generic name yields no distinguishing tokens
    assert _identity_tokens("AI News Blog", "https://medium.com/feed/foo") == set()
