"""Network-free builders shaped like X's web Bookmarks GraphQL traffic.

Shapes follow what x.com's web client receives (and what the MIT-licensed
x-bookmarks-exporter parses): ``data.bookmark_timeline_v2.timeline.instructions``
with ``TimelineAddEntries`` entries, one ``TimelineTimelineItem`` per post and
``cursor-top``/``cursor-bottom`` cursor entries; tweet results with ``legacy``,
``core.user_results.result`` (new ``core`` and old ``legacy`` author shapes),
``note_tweet`` long-form text, ``quoted_status_result`` and
``extended_entities.media`` video variants. The HTML and JavaScript builders
mimic the ``/i/bookmarks`` page with its inlined webpack runtime chunk map and
the ``main.<hash>.js`` / chunk bundles that define the ``Bookmarks`` query ID.

Nothing here is a real account, cookie, or post.
"""

from __future__ import annotations

from typing import Any

CLIENT_WEB = "https://abs.twimg.com/responsive-web/client-web"

CREATED_AT = "Wed Oct 10 20:19:24 +0000 2018"


def user_result(
    handle: str = "alice", name: str = "Alice Example", user_id: str = "1001", *, new_shape=True
) -> dict[str, Any]:
    """``core.user_results.result``: X moved screen_name into ``core`` in 2025."""
    names = {"screen_name": handle, "name": name}
    result: dict[str, Any] = {"__typename": "User", "rest_id": user_id, "id": "VXNlcjox"}
    if new_shape:
        result["core"] = {**names, "created_at": CREATED_AT}
        result["legacy"] = {"description": "", "followers_count": 10}
    else:
        result["legacy"] = {**names, "followers_count": 10}
    return result


def url_entity(short: str, expanded: str) -> dict[str, Any]:
    return {
        "display_url": expanded.split("://", 1)[-1][:24],
        "expanded_url": expanded,
        "url": short,
        "indices": [0, len(short)],
    }


def photo_media(short: str = "https://t.co/photo1") -> dict[str, Any]:
    return {
        "type": "photo",
        "url": short,
        "media_url_https": "https://pbs.twimg.com/media/PHOTO1.jpg",
        "expanded_url": "https://x.com/alice/status/1/photo/1",
    }


def video_media(short: str = "https://t.co/video1") -> dict[str, Any]:
    return {
        "type": "video",
        "url": short,
        "media_url_https": "https://pbs.twimg.com/ext_tw_video_thumb/VIDEO1/pu/img/thumb.jpg",
        "video_info": {
            "variants": [
                {"content_type": "application/x-mpegURL", "url": "https://video.twimg.com/v.m3u8"},
                {
                    "bitrate": 256000,
                    "content_type": "video/mp4",
                    "url": "https://video.twimg.com/ext_tw_video/VIDEO1/pu/vid/low.mp4?tag=12",
                },
                {
                    "bitrate": 2176000,
                    "content_type": "video/mp4",
                    "url": "https://video.twimg.com/ext_tw_video/VIDEO1/pu/vid/high.mp4?tag=12",
                },
            ]
        },
    }


def tweet_result(
    post_id: str,
    text: str = "",
    *,
    user: dict[str, Any] | None = None,
    urls: list[dict[str, Any]] | None = None,
    media: list[dict[str, Any]] | None = None,
    note_text: str | None = None,
    note_urls: list[dict[str, Any]] | None = None,
    quoted: dict[str, Any] | None = None,
    conversation_id: str | None = None,
    in_reply_to: str | None = None,
    hashtags: list[str] | None = None,
    mentions: list[str] | None = None,
    visibility_wrapper: bool = False,
) -> dict[str, Any]:
    """One ``tweet_results.result`` object."""
    entities: dict[str, Any] = {
        "hashtags": [{"text": tag, "indices": [0, 1]} for tag in hashtags or []],
        "symbols": [],
        "urls": urls or [],
        "user_mentions": [
            {"screen_name": handle, "name": handle, "id_str": "9"} for handle in mentions or []
        ],
    }
    legacy: dict[str, Any] = {
        "bookmark_count": 3,
        "bookmarked": True,
        "created_at": CREATED_AT,
        "conversation_id_str": conversation_id or post_id,
        "display_text_range": [0, len(text)],
        "entities": entities,
        "favorite_count": 42,
        "full_text": text,
        "id_str": post_id,
        "lang": "en",
        "reply_count": 4,
        "retweet_count": 7,
        "user_id_str": (user or user_result())["rest_id"],
    }
    if media:
        entities["media"] = media
        legacy["extended_entities"] = {"media": media}
    if in_reply_to:
        legacy["in_reply_to_status_id_str"] = in_reply_to
    tweet: dict[str, Any] = {
        "__typename": "Tweet",
        "rest_id": post_id,
        "core": {"user_results": {"result": user or user_result()}},
        "legacy": legacy,
        "views": {"count": "1000", "state": "EnabledWithCount"},
        "source": '<a href="https://mobile.twitter.com">Twitter Web App</a>',
    }
    if note_text is not None:
        tweet["note_tweet"] = {
            "is_expandable": True,
            "note_tweet_results": {
                "result": {
                    "id": "Tm90ZVR3ZWV0OjE=",
                    "text": note_text,
                    "entity_set": {
                        "hashtags": [],
                        "symbols": [],
                        "urls": note_urls or [],
                        "user_mentions": [],
                    },
                }
            },
        }
    if quoted is not None:
        tweet["quoted_status_result"] = {"result": quoted}
        legacy["is_quote_status"] = True
    if visibility_wrapper:
        return {"__typename": "TweetWithVisibilityResults", "tweet": tweet}
    return tweet


def tombstone_result() -> dict[str, Any]:
    return {
        "__typename": "TweetTombstone",
        "tombstone": {"text": {"text": "This Post is unavailable."}},
    }


def bookmarks_response(
    results: list[dict[str, Any]], *, bottom_cursor: str | None = None
) -> dict[str, Any]:
    """A full Bookmarks GraphQL response body (one ``TimelineAddEntries``)."""
    entries: list[dict[str, Any]] = []
    for index, result in enumerate(results):
        post_id = (result.get("tweet") or result).get("rest_id", f"x{index}")
        entries.append(
            {
                "entryId": f"tweet-{post_id}",
                "sortIndex": str(1_800_000_000_000_000_000 - index),
                "content": {
                    "entryType": "TimelineTimelineItem",
                    "__typename": "TimelineTimelineItem",
                    "itemContent": {
                        "itemType": "TimelineTweet",
                        "__typename": "TimelineTweet",
                        "tweet_results": {"result": result},
                        "tweetDisplayType": "Tweet",
                    },
                },
            }
        )
    entries.append(
        {
            "entryId": "cursor-top-1800000000000000000",
            "sortIndex": "1800000000000000000",
            "content": {
                "entryType": "TimelineTimelineCursor",
                "__typename": "TimelineTimelineCursor",
                "value": "HBaTOP==",
                "cursorType": "Top",
            },
        }
    )
    if bottom_cursor is not None:
        entries.append(
            {
                "entryId": "cursor-bottom-1700000000000000000",
                "sortIndex": "1700000000000000000",
                "content": {
                    "entryType": "TimelineTimelineCursor",
                    "__typename": "TimelineTimelineCursor",
                    "value": bottom_cursor,
                    "cursorType": "Bottom",
                },
            }
        )
    return {
        "data": {
            "bookmark_timeline_v2": {
                "timeline": {
                    "instructions": [{"type": "TimelineAddEntries", "entries": entries}],
                    "responseObjects": {"feedbackActions": []},
                }
            }
        }
    }


def query_not_found_response() -> dict[str, Any]:
    return {"errors": [{"message": "Query not found", "extensions": {"code": "NOT_FOUND"}}]}


BOOKMARKS_CHUNK_NAME = "shared~bundle.BookmarkFolders~bundle.Bookmarks"
BOOKMARKS_CHUNK_ID = "38265"
BOOKMARKS_CHUNK_HASH = "7c3f1ad"
MAIN_BUNDLE_URL = f"{CLIENT_WEB}/main.5b2f0c1e.js"


def bookmarks_chunk_url(suffix: str = "") -> str:
    return f"{CLIENT_WEB}/{BOOKMARKS_CHUNK_NAME}.{BOOKMARKS_CHUNK_HASH}{suffix}.js"


def bookmarks_page_html(*, with_runtime: bool = True, with_main: bool = True) -> str:
    """The logged-in ``/i/bookmarks`` shell: webpack runtime inline, main.js by src."""
    runtime = (
        "window.__SCRIPTS_LOADED__={};(()=>{var e={},g={};"
        'g.u=e=>(({"12":"vendor",'
        f'{BOOKMARKS_CHUNK_ID}:"{BOOKMARKS_CHUNK_NAME}",'
        '"4410":"bundle.Explore"}[e]||e)+"."+{'
        f'12:"0a1b2c3",{BOOKMARKS_CHUNK_ID}:"{BOOKMARKS_CHUNK_HASH}",4410:"9f8e7d6"'
        '}[e]+"a.js")})();'
    )
    scripts = [f'<script nonce="n0nce">{runtime}</script>'] if with_runtime else []
    if with_main:
        scripts.append(f'<script type="text/javascript" charset="utf-8" src="{MAIN_BUNDLE_URL}">')
        scripts.append("</script>")
    return (
        '<!DOCTYPE html><html dir="ltr" lang="en"><head><meta charset="utf-8" />'
        '<meta name="viewport" content="width=device-width" />'
        + "".join(scripts)
        + '</head><body><div id="react-root"></div></body></html>'
    )


def bundle_js(query_id: str) -> str:
    """A bundle that defines the Bookmarks operation, among others."""
    return (
        'e.exports={queryId:"AbCdEfGhIjKlMnOp",operationName:"BookmarkFolderTimeline",'
        'operationType:"query",metadata:{featureSwitches:[]}};'
        f'e.exports={{queryId:"{query_id}",operationName:"Bookmarks",operationType:"query",'
        'metadata:{featureSwitches:["graphql_timeline_v2_bookmark_timeline"]}};'
    )
