"""Substack API ingestion.

Fetches Substack subscriptions and ingests recent posts for the enabled
(paid) sources in sources.d/substack.yaml. Every request, including the
archive listing and each post body, goes through :class:`SubstackClient`, so
it carries the live ``substack.sid`` and is policed for a dead session.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final
from urllib.parse import urljoin, urlparse

import httpx
import yaml
from dateutil.parser import isoparse

from src.config import settings
from src.config.credentials import (
    SUBSTACK_SESSION_COOKIE,
    CredentialProvider,
    get_credential_provider,
)
from src.config.settings import get_settings
from src.config.sources import SourceFileConfig, SubstackSource
from src.ingestion.credential_failures import (
    CredentialFailureError,
    CredentialsMissingError,
    SessionExpiredError,
)
from src.ingestion.gmail import ContentData
from src.ingestion.log_redaction import log_error_type
from src.ingestion.result import (
    IngestionError,
    IngestionResponse,
    SourceFetchResult,
    build_response_from_source_results,
)
from src.models.content import Content, ContentSource, ContentStatus
from src.parsers.html_markdown import convert_html_to_markdown
from src.storage.database import get_db
from src.utils.content_hash import generate_markdown_hash
from src.utils.html_parser import html_to_text
from src.utils.logging import get_logger
from src.utils.substack import (
    extract_substack_canonical_url,
    find_existing_substack_content,
    normalize_substack_url,
)

logger = get_logger(__name__)


@dataclass
class SubstackSubscription:
    name: str
    url: str
    is_paid: bool = False


@dataclass
class SyncResult:
    """Result of a substack-sync operation."""

    rss_added: int
    rss_existing: int
    rss_removed: int
    substack_added: int
    substack_existing: int


SUBSTACK_SID_COOKIE = "substack.sid"
SUBSTACK_REFRESH_COMMAND = "aca auth session substack"

SESSION_PROBE_URL = "https://substack.com/api/v1/subscriptions"
"""Cheap endpoint that only answers a logged-in reader (also the sync source)."""

_LOGIN_PATHS = ("/sign-in", "/account/login")


def is_dead_session_response(response: httpx.Response) -> bool:
    """True when a JSON API request that CARRIED ``substack.sid`` came back logged out.

    Conservative on purpose: each signal is one a logged-in request never
    produces, so a false positive would need Substack itself to misbehave.

    - ``401``;
    - ``403`` unless it is a Cloudflare challenge (``cf-mitigated`` header),
      which is bot mitigation rather than a verdict on the session;
    - a redirect whose ``Location`` path is a sign-in page (``/sign-in``,
      ``/account/login``); the client never follows redirects;
    - a ``2xx`` ``text/html`` body where the API endpoint returns JSON.

    404, 429, 5xx, and redirects elsewhere are ordinary failures, not session
    verdicts, and are left to the caller's existing handling.
    """
    status = response.status_code
    if status == 401:
        return True
    if status == 403:
        return "cf-mitigated" not in response.headers
    if response.is_redirect:
        path = urlparse(response.headers.get("location", "")).path.rstrip("/").lower()
        return any(path == login or path.startswith(login + "/") for login in _LOGIN_PATHS)
    if response.is_success:
        content_type = response.headers.get("content-type", "").lower()
        return content_type.startswith("text/html")
    return False


# -- paid posts: full body or teaser --------------------------------------------

PAID_AUDIENCES: Final = frozenset({"only_paid", "founding"})
"""``audience`` values of a post that only paying readers see in full."""

BODY_STATE_KEY: Final = "substack_body"
"""``metadata_json`` key recording whether a paid post's stored body is complete."""

BODY_FULL: Final = "full"
BODY_TEASER: Final = "teaser"

TEASER_WORD_RATIO: Final = 0.8
"""A paid body with fewer words than this share of ``wordcount`` is a teaser."""

_SLUG_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._~-]*")


def is_ambiguous_forbidden(response: httpx.Response) -> bool:
    """A non-Cloudflare 403: dead session, or a post this reader's tier cannot see.

    On the probe endpoint it is a dead-session verdict. On publication
    endpoints (archive, post) it is ambiguous, and the client asks the probe.
    """
    return response.status_code == 403 and "cf-mitigated" not in response.headers


class PublicationAccessDeniedError(Exception):
    """A publication endpoint refused a session the probe still accepts.

    Per-post (or per-publication) access, not a session verdict. Carries no
    URL and no credential.
    """


def _raw_body(post: dict[str, Any]) -> str | None:
    body = post.get("body_html") or post.get("html") or post.get("body")
    return body if isinstance(body, str) and body.strip() else None


def _word_count(text: str | None) -> int:
    return len(text.split()) if text else 0


def is_paid_post(post: dict[str, Any]) -> bool:
    """True when the post's ``audience`` restricts the full body to paying readers."""
    return post.get("audience") in PAID_AUDIENCES


def is_teaser_body(post: dict[str, Any]) -> bool:
    """True when a paid post's payload carries less than the full body.

    Substack serves a logged-out (or unsubscribed) reader of a paid post the
    same post JSON with ``body_html`` cut at the paywall, or with no
    ``body_html`` at all, while ``wordcount`` still counts the whole post. So a
    paid post is a teaser when it has no body, or when its body holds fewer
    than :data:`TEASER_WORD_RATIO` of ``wordcount`` words. A paid post with a
    body and no usable ``wordcount`` counts as full: the adapter never guesses
    a body is short without evidence. Free posts are never teasers.
    """
    if not is_paid_post(post):
        return False
    body = _raw_body(post)
    if body is None:
        return True
    wordcount = post.get("wordcount")
    if isinstance(wordcount, int) and not isinstance(wordcount, bool) and wordcount > 0:
        return _word_count(html_to_text(body)) < TEASER_WORD_RATIO * wordcount
    return False


_DEFAULT_HEADERS: Final = {
    # The browser-like agent the substack-api library used; the default httpx
    # agent is more likely to meet Cloudflare bot mitigation.
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/91.0.4472.77 Safari/537.36"
    ),
    "Accept": "application/json",
}


class SubstackClient:
    """httpx client for the Substack JSON API that carries the live session.

    Unless an explicit ``session_cookie`` is passed, the ``substack.sid``
    cookie is resolved through the live :class:`CredentialProvider` before
    every HTTP request, so a cookie rotated in OpenBao reaches a long-lived
    client without a restart. Subscriptions, the archive listing, and every
    post body are fetched through :meth:`_get_with_session`, so one
    dead-session policy (refresh once, retry once, fail closed) covers them.
    """

    def __init__(
        self,
        session_cookie: str | None = None,
        *,
        credentials: CredentialProvider | None = None,
        http_client: httpx.Client | None = None,
        request_delay_s: float | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._explicit_cookie = session_cookie or None
        self._credentials = credentials or get_credential_provider()
        self._http = http_client or httpx.Client(timeout=30, headers=_DEFAULT_HEADERS)
        self._applied_cookie: str | None = None
        self._request_delay_s = (
            get_settings().substack_request_delay_s if request_delay_s is None else request_delay_s
        )
        self._sleep = sleep
        self._detail_requested = False
        self._forbidden_probed = False
        self._sync_session_cookie()

    def begin_run(self) -> None:
        """Reset the per-run state: pacing and the one 403 re-probe."""
        self._detail_requested = False
        self._forbidden_probed = False

    @property
    def session_cookie(self) -> str | None:
        """The cookie to send now: the explicit override, else the live credential."""
        if self._explicit_cookie:
            return self._explicit_cookie
        return self._credentials.get(SUBSTACK_SESSION_COOKIE)

    def _sync_session_cookie(self) -> str | None:
        """Point the HTTP client's ``substack.sid`` at the current credential."""
        cookie = self.session_cookie
        if cookie != self._applied_cookie:
            rotated = self._applied_cookie is not None
            # Drop every substack.sid, including one a response set, so the
            # rotated credential is the only session the next request sends.
            self._http.cookies.delete(SUBSTACK_SID_COOKIE)
            if cookie:
                self._http.cookies.set(SUBSTACK_SID_COOKIE, cookie)
            self._applied_cookie = cookie
            if rotated:
                logger.info(
                    "substack.session_cookie_changed: using the current %s", SUBSTACK_SESSION_COOKIE
                )
        return cookie

    def _uses_provider_cookie(self, cookie: str) -> bool:
        """True when ``cookie`` is the provider's current value (not an override)."""
        return (
            not self._explicit_cookie and self._credentials.get(SUBSTACK_SESSION_COOKIE) == cookie
        )

    def _get_with_session(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        verifies_session: bool = False,
        forbidden_is_ambiguous: bool = False,
    ) -> httpx.Response:
        """GET ``url`` with the current ``substack.sid`` and police the answer.

        A dead-session answer (see :func:`is_dead_session_response`) triggers
        one bounded OpenBao refresh and, when that yields a different cookie,
        one retry. A session still refused raises :class:`SessionExpiredError`
        and records the rejection on the provider so readiness reports
        ``session_expired`` until a new cookie is patched in. Requests sent
        without a cookie are never judged: logged out is their expected state.

        ``verifies_session`` marks the provider's cookie verified on a 2xx; set
        it only for endpoints that require a login (the archive is public, so
        its 200 proves nothing about the session).

        ``forbidden_is_ambiguous`` returns a non-Cloudflare 403 to the caller
        unjudged (no refresh, no ``mark_rejected``): on publication endpoints a
        403 may only mean this reader's tier cannot see the post, and the
        caller settles it with the session probe. 401, sign-in redirects and
        HTML stay dead-session verdicts.
        """
        cookie = self._sync_session_cookie()
        response = self._http.get(url, params=params)
        if cookie is None:
            return response
        if forbidden_is_ambiguous and is_ambiguous_forbidden(response):
            return response
        if is_dead_session_response(response):
            response, cookie = self._retry_after_refresh(url, params, rejected=cookie)
        if verifies_session and response.is_success and self._uses_provider_cookie(cookie):
            self._credentials.mark_verified(SUBSTACK_SESSION_COOKIE)
        return response

    def _retry_after_refresh(
        self, url: str, params: dict[str, Any] | None, *, rejected: str
    ) -> tuple[httpx.Response, str]:
        logger.warning(
            "substack.session_rejected: refreshing %s once before failing closed",
            SUBSTACK_SESSION_COOKIE,
        )
        if not self._explicit_cookie:
            # An explicit override did not come from the provider; refreshing
            # OpenBao cannot replace it.
            self._credentials.refresh()
        cookie = self._sync_session_cookie()
        if cookie and cookie != rejected:
            response = self._http.get(url, params=params)
            if not is_dead_session_response(response):
                logger.info("substack.session_recovered: refreshed %s", SUBSTACK_SESSION_COOKIE)
                return response, cookie
            rejected = cookie
        if self._uses_provider_cookie(rejected):
            self._credentials.mark_rejected(SUBSTACK_SESSION_COOKIE)
        raise SessionExpiredError(
            source="substack",
            credential_label=SUBSTACK_SID_COOKIE,
            refresh_command=SUBSTACK_REFRESH_COMMAND,
        )

    def verify_session(self) -> bool:
        """Prove the current cookie with one authenticated request.

        Returns True when Substack accepted it (and marks it verified), False
        when there is no cookie or the answer says nothing about the session
        (network error, 404, 429, 5xx). Raises :class:`SessionExpiredError`
        when Substack refused it even after one refresh.
        """
        if not self._sync_session_cookie():
            return False
        try:
            response = self._get_with_session(SESSION_PROBE_URL, verifies_session=True)
        except httpx.HTTPError as exc:
            logger.warning("substack.session_probe_inconclusive (%s)", log_error_type(exc))
            return False
        if not response.is_success:
            logger.warning("substack.session_probe_inconclusive (HTTP %s)", response.status_code)
            return False
        return True

    def require_session_cookie(self) -> None:
        """Fail closed unless a ``substack.sid`` is configured.

        A missing provider value gets one bounded OpenBao refresh first, so a
        cookie patched in moments ago is not reported missing from a stale
        cache. Raises :class:`CredentialsMissingError` when there is still none.
        """
        if self._sync_session_cookie():
            return
        if not self._explicit_cookie:
            self._credentials.refresh()
        if self._sync_session_cookie():
            return
        raise CredentialsMissingError(
            source="substack",
            credential_label=SUBSTACK_SID_COOKIE,
            refresh_command=SUBSTACK_REFRESH_COMMAND,
        )

    def close(self) -> None:
        self._http.close()

    def fetch_subscriptions(self) -> list[SubstackSubscription]:
        """Return a list of subscriptions (name + url + paid status)."""
        subscriptions = self._fetch_subscriptions_from_http()

        if not subscriptions:
            return []

        results: list[SubstackSubscription] = []
        for entry in subscriptions:
            name = (
                entry.get("name")
                or entry.get("publication")
                or entry.get("title")
                or entry.get("subdomain")
                or "Substack"
            )
            url = (
                entry.get("url")
                or entry.get("publication_url")
                or entry.get("base_url")
                or entry.get("canonical_url")
            )
            if not url and entry.get("subdomain"):
                url = f"https://{entry['subdomain']}.substack.com"
            if not url:
                continue
            is_paid = entry.get("membership_state") not in ("free_signup", None)
            results.append(SubstackSubscription(name=name, url=url, is_paid=is_paid))

        return results

    def _fetch_subscriptions_from_http(self) -> list[dict[str, Any]] | None:
        if not self._sync_session_cookie():
            logger.warning("SUBSTACK_SESSION_COOKIE not set; subscription sync may be incomplete.")
            return None

        endpoints = [
            "https://substack.com/api/v1/subscriptions",
            "https://substack.com/api/v1/user/subscriptions",
        ]
        for endpoint in endpoints:
            try:
                response = self._get_with_session(endpoint, verifies_session=True)
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict) and "subscriptions" in data:
                    return self._join_subscriptions_with_publications(data)
                if isinstance(data, list):
                    return data
            except SessionExpiredError:
                # Never degrade to "no subscriptions": sync would then rewrite
                # substack.yaml with an empty source list.
                raise
            except Exception as exc:
                logger.warning("Substack HTTP subscription fetch failed (%s)", log_error_type(exc))
                continue
        return None

    def _join_subscriptions_with_publications(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Join subscription records with publication metadata.

        The API returns subscriptions (user-publication junction records) and
        publications (metadata with name, subdomain, base_url) as separate arrays.
        We merge them so each result has the fields fetch_subscriptions expects.
        """
        subs = data.get("subscriptions", [])
        pubs = data.get("publications", [])
        pub_by_id: dict[int, dict[str, Any]] = {p["id"]: p for p in pubs if "id" in p}

        results: list[dict[str, Any]] = []
        for sub in subs:
            pub = pub_by_id.get(sub.get("publication_id", -1), {})
            merged = {**sub, **pub}
            # Ensure the fields that fetch_subscriptions looks for are present
            if "url" not in merged and pub.get("base_url"):
                merged["url"] = pub["base_url"]
            if "name" not in merged and pub.get("subdomain"):
                merged["name"] = pub["subdomain"]
            results.append(merged)

        return results

    def fetch_posts(self, publication_url: str, max_entries: int = 10) -> list[dict[str, Any]]:
        """Recent posts of one publication, each with its body, through the session.

        Lists ``/api/v1/archive`` (which carries no body), then fetches each
        post from ``/api/v1/posts/<slug>`` on the configured publication host.
        Both requests carry the live ``substack.sid``, so a paying reader gets
        the full body of a paid post. A post whose detail request fails for an
        ordinary reason (404, 429, 5xx, network) keeps its archive entry and is
        reported by the caller; a dead session raises
        :class:`SessionExpiredError`.
        """
        posts: list[dict[str, Any]] = []
        for entry in self._fetch_archive(publication_url, max_entries)[:max_entries]:
            detail = self._fetch_post_detail(publication_url, entry.get("slug"))
            posts.append({**entry, **detail} if detail else entry)
        return posts

    def _pace(self) -> None:
        """Wait ``request_delay_s`` between post-detail requests (not before the first)."""
        if self._detail_requested and self._request_delay_s > 0:
            self._sleep(self._request_delay_s)
        self._detail_requested = True

    def _get_publication_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        """GET a publication API URL through the session and decode its JSON.

        A publication that moved hosts answers with a redirect to the same API
        path on its new host; that one redirect is followed (the client never
        follows redirects on its own, so a sign-in redirect is still judged
        as a dead session). Any other redirect or error status raises
        ``httpx.HTTPStatusError``; an ambiguous 403 that the session probe
        does not confirm as dead raises :class:`PublicationAccessDeniedError`.
        """
        response = self._get_publication(url, params)
        if response.is_redirect:
            moved = _same_path_redirect(url, response)
            if moved is not None:
                response = self._get_publication(moved, params)
        response.raise_for_status()
        return response.json()

    def _get_publication(self, url: str, params: dict[str, Any] | None) -> httpx.Response:
        response = self._get_with_session(url, params=params, forbidden_is_ambiguous=True)
        sent = self._applied_cookie
        if sent is None or not is_ambiguous_forbidden(response):
            return response
        # Dead session, or a post this tier cannot see? Ask the probe, once per
        # run. It raises SessionExpiredError (after its own refresh and retry,
        # recording the rejection) when the session is dead.
        if not self._forbidden_probed:
            self._forbidden_probed = True
            self.verify_session()
        if self._sync_session_cookie() != sent:
            # The probe's refresh rotated the cookie: the 403 was for the old one.
            response = self._get_with_session(url, params=params, forbidden_is_ambiguous=True)
            if not is_ambiguous_forbidden(response):
                return response
        raise PublicationAccessDeniedError

    def _fetch_archive(self, publication_url: str, max_entries: int) -> list[dict[str, Any]]:
        archive_url = urljoin(publication_url.rstrip("/") + "/", "api/v1/archive")
        try:
            data = self._get_publication_json(
                archive_url, params={"sort": "new", "offset": 0, "limit": max_entries}
            )
        except SessionExpiredError:
            raise
        except PublicationAccessDeniedError:
            logger.warning("substack.archive_access_denied: the session cannot list this archive")
            return []
        except Exception as exc:
            logger.warning("Substack archive fetch failed (%s)", log_error_type(exc))
            return []
        if isinstance(data, dict):
            data = data.get("posts")
        if not isinstance(data, list):
            return []
        return [entry for entry in data if isinstance(entry, dict)]

    def _fetch_post_detail(self, publication_url: str, slug: Any) -> dict[str, Any] | None:
        """The post's full JSON (with ``body_html``), or None when unavailable."""
        if not isinstance(slug, str) or not _SLUG_RE.fullmatch(slug):
            return None
        post_url = urljoin(publication_url.rstrip("/") + "/", f"api/v1/posts/{slug}")
        self._pace()
        try:
            data = self._get_publication_json(post_url)
        except SessionExpiredError:
            raise
        except PublicationAccessDeniedError:
            # The slug passed _SLUG_RE, so it is safe to log; nothing else is.
            logger.warning("substack.post_access_denied: slug=%s (keeping the teaser)", slug)
            return None
        except Exception as exc:
            logger.warning("Substack post fetch failed (%s)", log_error_type(exc))
            return None
        return data if isinstance(data, dict) else None


def _same_path_redirect(url: str, response: httpx.Response) -> str | None:
    """The redirect target when it is the same API path on another https host."""
    try:
        target = httpx.URL(url).join(response.headers.get("location", ""))
    except Exception:
        return None
    requested = httpx.URL(url)
    if target.scheme != "https" or target.path != requested.path:
        return None
    if target.host == requested.host:
        return None
    return str(requested.copy_with(scheme="https", host=target.host, port=None))


class SubstackContentIngestionService:
    """Service for ingesting Substack posts into the unified Content model.

    The ``substack`` source type holds paid subscriptions (``substack-sync``
    routes free ones to RSS), so a run needs the session cookie: without one
    it fails closed with ``credentials_missing`` instead of ingesting teasers.
    """

    def __init__(
        self,
        session_cookie: str | None = None,
        *,
        credentials: CredentialProvider | None = None,
    ) -> None:
        self.client = SubstackClient(session_cookie=session_cookie, credentials=credentials)

    def close(self) -> None:
        self.client.close()

    def ingest_content(
        self,
        sources: list[SubstackSource] | None = None,
        max_entries_per_source: int = 10,
        after_date: datetime | None = None,
        force_reprocess: bool = False,
    ) -> IngestionResponse:
        logger.info("Starting Substack content ingestion...")
        source_results: list[SourceFetchResult] = []

        if sources is None:
            sources_config = settings.get_sources_config()
            sources = sources_config.get_substack_sources()

        if not sources:
            logger.warning("No Substack sources configured. Add sources to sources.d/substack.yaml")
            return build_response_from_source_results(
                command="ingest.substack",
                source="substack",
                items_ingested=0,
                source_results=source_results,
            )

        enabled_sources = [s for s in sources if s.enabled]
        logger.info(
            f"Fetching from {len(enabled_sources)} Substack sources "
            f"({len(sources) - len(enabled_sources)} disabled)"
        )

        # Every fetch finishes before the first row is written, so failing
        # closed here persists nothing: a missing or dead session is never a
        # partial run.
        try:
            contents = self._fetch_contents(
                enabled_sources, source_results, max_entries_per_source, after_date
            )
        except CredentialFailureError as exc:
            logger.error("substack.%s: ingestion failed closed with zero rows", exc.code)
            return IngestionResponse(
                command="ingest.substack",
                source="substack",
                status="error",
                items_ingested=0,
                errors=[exc.to_ingestion_error()],
            )

        if not contents:
            logger.info("No Substack content found")
            return build_response_from_source_results(
                command="ingest.substack",
                source="substack",
                items_ingested=0,
                source_results=source_results,
            )

        count = 0
        persistence_errors: list[IngestionError] = []
        with get_db() as db:
            for content_data, _source_result in contents:
                try:
                    existing = (
                        db.query(Content)
                        .filter(
                            Content.source_type == content_data.source_type,
                            Content.source_id == content_data.source_id,
                        )
                        .first()
                    )

                    substack_duplicate = None
                    if not existing:
                        canonical_url = normalize_substack_url(content_data.source_url)
                        substack_duplicate = find_existing_substack_content(db, canonical_url)

                    content_duplicate = None
                    if not existing and not substack_duplicate and content_data.content_hash:
                        content_duplicate = (
                            db.query(Content)
                            .filter(Content.content_hash == content_data.content_hash)
                            .first()
                        )

                    if existing:
                        if force_reprocess:
                            _overwrite_content(existing, content_data)
                            existing.status = ContentStatus.PARSED
                            existing.error_message = None
                            count += 1
                            logger.info(f"Updated for reprocessing: {content_data.title}")
                            continue
                        if is_teaser_upgrade(existing, content_data):
                            _upgrade_teaser(db, existing, content_data)
                            count += 1
                            logger.info(
                                "substack.teaser_upgraded: stored the full paid body of "
                                f"{content_data.source_id}"
                            )
                            continue
                        logger.debug(
                            "Content already exists (use --force to reprocess): "
                            f"{content_data.source_id}"
                        )
                        continue

                    if substack_duplicate:
                        content = Content(
                            source_type=content_data.source_type,
                            source_id=content_data.source_id,
                            source_url=content_data.source_url,
                            title=content_data.title,
                            author=content_data.author,
                            publication=content_data.publication,
                            published_date=content_data.published_date,
                            markdown_content=content_data.markdown_content,
                            links_json=content_data.links_json,
                            metadata_json=content_data.metadata_json,
                            raw_content=content_data.raw_content,
                            raw_format=content_data.raw_format,
                            parser_used=content_data.parser_used,
                            content_hash=content_data.content_hash,
                            canonical_id=substack_duplicate.id,
                            status=ContentStatus.COMPLETED,
                        )
                        db.add(content)
                        count += 1
                        logger.info(f"Linked duplicate to canonical ID {substack_duplicate.id}")
                        continue

                    if content_duplicate:
                        content = Content(
                            source_type=content_data.source_type,
                            source_id=content_data.source_id,
                            source_url=content_data.source_url,
                            title=content_data.title,
                            author=content_data.author,
                            publication=content_data.publication,
                            published_date=content_data.published_date,
                            markdown_content=content_data.markdown_content,
                            links_json=content_data.links_json,
                            metadata_json=content_data.metadata_json,
                            raw_content=content_data.raw_content,
                            raw_format=content_data.raw_format,
                            parser_used=content_data.parser_used,
                            content_hash=content_data.content_hash,
                            canonical_id=content_duplicate.id,
                            status=ContentStatus.COMPLETED,
                        )
                        db.add(content)
                        count += 1
                        logger.info(f"Linked duplicate to canonical ID {content_duplicate.id}")
                        continue

                    content = Content(
                        source_type=content_data.source_type,
                        source_id=content_data.source_id,
                        source_url=content_data.source_url,
                        title=content_data.title,
                        author=content_data.author,
                        publication=content_data.publication,
                        published_date=content_data.published_date,
                        markdown_content=content_data.markdown_content,
                        links_json=content_data.links_json,
                        metadata_json=content_data.metadata_json,
                        raw_content=content_data.raw_content,
                        raw_format=content_data.raw_format,
                        parser_used=content_data.parser_used,
                        content_hash=content_data.content_hash,
                        status=ContentStatus.PARSED,
                    )
                    db.add(content)
                    db.flush()  # Ensure content.id is assigned for indexing

                    # Index for search (fail-safe — never blocks ingestion)
                    from src.services.indexing import index_content

                    index_content(content, db)

                    count += 1
                    logger.info(f"Ingested: {content_data.title}")

                except Exception as exc:
                    logger.error(f"Error storing content: {exc}")
                    db.rollback()
                    persistence_errors.append(
                        IngestionError(
                            code="persistence_error",
                            message=str(exc),
                            url=content_data.source_url,
                        )
                    )
                    continue

        logger.info(f"Successfully ingested {count} Substack items")
        return build_response_from_source_results(
            command="ingest.substack",
            source="substack",
            items_ingested=count,
            source_results=source_results,
            extra_item_errors=persistence_errors,
            extra_items_failed=len(persistence_errors),
        )

    def _fetch_contents(
        self,
        enabled_sources: list[SubstackSource],
        source_results: list[SourceFetchResult],
        max_entries_per_source: int,
        after_date: datetime | None,
    ) -> list[tuple[ContentData, SourceFetchResult]]:
        """Fetch and convert every enabled source; persist nothing.

        Requires a configured cookie (:class:`CredentialsMissingError`) and
        proves it first with one authenticated request, because the archive
        and post endpoints are public and would silently serve a logged-out
        reader teasers. Raises :class:`SessionExpiredError` when Substack
        refuses the session.
        """
        if enabled_sources:
            self.client.begin_run()
            self.client.require_session_cookie()
            self.client.verify_session()

        # Track contents alongside the source they came from so per-source
        # diagnostics survive the flat persistence loop in ingest_content.
        contents: list[tuple[ContentData, SourceFetchResult]] = []
        for source in enabled_sources:
            fetch_result = SourceFetchResult(url=source.url, name=source.name)
            source_results.append(fetch_result)
            max_entries = source.max_entries or max_entries_per_source
            posts = self.client.fetch_posts(source.url, max_entries=max_entries)
            for post in posts:
                coerced = self._coerce_post(post)
                content = self._post_to_content(coerced, source)
                if content is None:
                    fetch_result.items_failed += 1
                    post_url = coerced.get("canonical_url") or coerced.get("url") or source.url
                    fetch_result.item_errors.append(
                        IngestionError(
                            code="extraction_failed",
                            message="Empty or paywalled post body",
                            url=post_url,
                        )
                    )
                    continue
                if after_date and content.published_date and content.published_date < after_date:
                    continue
                contents.append((content, fetch_result))
        teasers = sum(
            1
            for content, _ in contents
            if (content.metadata_json or {}).get(BODY_STATE_KEY) == BODY_TEASER
        )
        if teasers:
            # The session is valid (probed above) but does not unlock these
            # posts: not subscribed to that tier, or a custom domain that does
            # not honour substack.sid. They stay upgradeable on a later run.
            logger.warning("substack.paid_teasers: %d paid post(s) returned only a teaser", teasers)
        return contents

    def _post_to_content(self, post: dict[str, Any], source: SubstackSource) -> ContentData | None:
        title = post.get("title") or post.get("subject") or "Untitled"
        raw_html = _raw_body(post)
        markdown_content = (
            post.get("body_markdown")
            or post.get("markdown")
            or (convert_html_to_markdown(html=raw_html) if raw_html else "")
        )
        if not markdown_content and raw_html:
            markdown_content = html_to_text(raw_html)
        if not markdown_content and is_paid_post(post):
            # No body we may read (e.g. access denied): keep the archive's
            # preview text as a teaser row that a later run can upgrade.
            preview = post.get("truncated_body_text")
            markdown_content = preview.strip() if isinstance(preview, str) else ""

        if not markdown_content:
            logger.debug(f"Skipping Substack post with empty content: {title}")
            return None

        link_candidate = post.get("canonical_url") or post.get("url") or post.get("post_url")
        link_candidates = [link_candidate] if isinstance(link_candidate, str) else []
        canonical_url = extract_substack_canonical_url(
            links=link_candidates,
            source_url=source.url,
        )
        if canonical_url is None and post.get("slug"):
            canonical_url = normalize_substack_url(f"{source.url.rstrip('/')}/p/{post['slug']}")
        canonical_url = canonical_url or source.url

        published_date = self._parse_date(post.get("post_date") or post.get("published_at"))

        metadata = {
            "publication_url": source.url,
            "substack_url": canonical_url,
            "post_id": post.get("id") or post.get("post_id"),
            "slug": post.get("slug"),
        }
        if is_paid_post(post):
            metadata["audience"] = post.get("audience")
            metadata[BODY_STATE_KEY] = BODY_TEASER if is_teaser_body(post) else BODY_FULL

        source_id = str(post.get("id") or post.get("post_id") or canonical_url)
        content_hash = generate_markdown_hash(markdown_content)

        publication = source.name
        if not publication:
            pub_value = post.get("publication")
            if isinstance(pub_value, dict):
                publication = pub_value.get("name")
            elif isinstance(pub_value, str):
                publication = pub_value

        return ContentData(
            source_type=ContentSource.SUBSTACK,
            source_id=source_id,
            source_url=canonical_url,
            title=title,
            author=self._extract_author(post),
            publication=publication,
            published_date=published_date,
            markdown_content=markdown_content,
            links_json=None,
            metadata_json=metadata,
            raw_content=raw_html,
            raw_format="html" if raw_html else "text",
            parser_used="substack_api",
            content_hash=content_hash,
        )

    def _coerce_post(self, post: Any) -> dict[str, Any]:
        if isinstance(post, dict):
            return post
        if hasattr(post, "dict"):
            return post.dict()  # type: ignore[no-any-return]
        fields = (
            "title",
            "subject",
            "body_html",
            "html",
            "body",
            "body_markdown",
            "markdown",
            "canonical_url",
            "url",
            "post_url",
            "slug",
            "post_date",
            "published_at",
            "id",
            "post_id",
            "author",
            "audience",
            "wordcount",
            "truncated_body_text",
        )
        return {field: getattr(post, field, None) for field in fields}

    def _extract_author(self, post: dict[str, Any]) -> str | None:
        author = post.get("author")
        if isinstance(author, dict):
            return author.get("name") or author.get("handle")
        return author

    def _parse_date(self, value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            parsed = isoparse(str(value))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed
        except Exception:
            return None


def _overwrite_content(existing: Content, content_data: ContentData) -> None:
    """Replace a stored post's fetched fields with a fresh fetch."""
    existing.title = content_data.title
    existing.author = content_data.author
    existing.publication = content_data.publication
    existing.published_date = content_data.published_date
    existing.markdown_content = content_data.markdown_content
    existing.links_json = content_data.links_json
    existing.metadata_json = content_data.metadata_json
    existing.raw_content = content_data.raw_content
    existing.raw_format = content_data.raw_format
    existing.parser_used = content_data.parser_used
    existing.content_hash = content_data.content_hash


def is_teaser_upgrade(existing: Content, incoming: ContentData) -> bool:
    """True when ``incoming`` is the full body of a paid post stored as a teaser.

    Deliberately narrow, so dedup still skips everything else:

    - the fresh fetch must be a paid post whose body is complete
      (``substack_body == "full"``) and differ from what is stored;
    - the stored row must be a teaser: recorded as one, or, for a row stored
      before bodies were classified (always fetched logged out), holding fewer
      than :data:`TEASER_WORD_RATIO` of the fresh body's words;
    - a row being summarized right now is left for the next run.
    """
    incoming_meta = incoming.metadata_json or {}
    if incoming_meta.get(BODY_STATE_KEY) != BODY_FULL:
        return False
    if existing.content_hash == incoming.content_hash:
        return False
    if existing.status == ContentStatus.PROCESSING:
        return False
    stored_state = (existing.metadata_json or {}).get(BODY_STATE_KEY)
    if stored_state == BODY_TEASER:
        return True
    if stored_state is None:
        stored_words = _word_count(existing.markdown_content)
        return stored_words < TEASER_WORD_RATIO * _word_count(incoming.markdown_content)
    return False


def _upgrade_teaser(db: Any, existing: Content, content_data: ContentData) -> None:
    """Store the full body over a teaser row and queue it for summarization again.

    The teaser's summaries are deleted (the summarizer skips content that has
    one), the status returns to ``parsed``, and the search chunks are rebuilt
    from the new body. A row the ingestion filter rejected keeps
    ``filtered_out``: the new body is stored, and ``aca filter rerun`` decides
    whether it now deserves a summary.
    """
    from src.models.summary import Summary
    from src.services.indexing import reindex_content

    _overwrite_content(existing, content_data)
    existing.error_message = None
    if existing.status != ContentStatus.FILTERED_OUT:
        existing.status = ContentStatus.PARSED
    db.query(Summary).filter(Summary.content_id == existing.id).delete()
    db.flush()
    reindex_content(existing, db)  # fail-safe; a no-op unless search indexing is on


def sync_substack_sources(
    output_path: Path | None = None,
    session_cookie: str | None = None,
) -> SyncResult:
    """Sync Substack subscriptions: paid → substack.yaml, free → rss.yaml."""
    sources_dir = Path(settings.sources_config_dir)
    substack_path = output_path or sources_dir / "substack.yaml"
    rss_path = sources_dir / "rss.yaml"
    substack_path.parent.mkdir(parents=True, exist_ok=True)

    client = SubstackClient(session_cookie=session_cookie)
    subscriptions = client.fetch_subscriptions()
    client.close()

    paid = [s for s in subscriptions if s.is_paid]
    free = [s for s in subscriptions if not s.is_paid]
    logger.info(f"Found {len(subscriptions)} subscriptions: {len(paid)} paid, {len(free)} free")

    substack_result = _sync_paid_to_substack(paid, substack_path)
    paid_urls = {s.url for s in paid}
    rss_result = _sync_free_to_rss(free, rss_path, exclude_urls=paid_urls)

    result = SyncResult(
        rss_added=rss_result[0],
        rss_existing=rss_result[1],
        rss_removed=rss_result[2],
        substack_added=substack_result[0],
        substack_existing=substack_result[1],
    )
    logger.info(
        f"Sync complete: "
        f"{result.substack_added} paid added to substack.yaml "
        f"({result.substack_existing} existing), "
        f"{result.rss_added} free added to rss.yaml "
        f"({result.rss_existing} already present, "
        f"{result.rss_removed} removed — now in substack.yaml)"
    )
    return result


def _sync_paid_to_substack(
    subscriptions: list[SubstackSubscription], path: Path
) -> tuple[int, int]:
    """Write paid subscriptions to substack.yaml, preserving existing entries.

    Returns (added, existing) counts.
    """
    existing_entries: dict[str, dict[str, Any]] = {}
    if path.exists():
        try:
            raw_config = yaml.safe_load(path.read_text())
            existing_config = (
                SourceFileConfig.model_validate(raw_config) if raw_config else SourceFileConfig()
            )
            for entry in existing_config.sources:
                url = normalize_substack_url(entry.get("url")) or entry.get("url")
                if url:
                    existing_entries[url] = entry
        except Exception as exc:
            logger.warning(f"Failed to read existing Substack sources: {exc}")

    added = 0
    existing = 0
    merged_sources: list[dict[str, Any]] = []
    for subscription in subscriptions:
        canonical_url = normalize_substack_url(subscription.url) or subscription.url
        entry = existing_entries.get(canonical_url)
        if entry:
            merged_sources.append(entry)
            existing += 1
        else:
            merged_sources.append(
                {
                    "name": subscription.name,
                    "url": canonical_url,
                    "enabled": True,
                    "tags": [],
                }
            )
            added += 1

    config = {
        "defaults": {"type": "substack"},
        "sources": merged_sources,
    }
    path.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True))
    return added, existing


def _sync_free_to_rss(
    subscriptions: list[SubstackSubscription],
    rss_path: Path,
    exclude_urls: set[str] | None = None,
) -> tuple[int, int, int]:
    """Append free Substack subscriptions to rss.yaml, deduplicating by URL.

    Removes any existing RSS entries whose base URL matches exclude_urls
    (paid subscriptions that moved to substack.yaml).

    Returns (added, already_existing, removed) counts.
    """
    # Build normalized set of paid URLs to exclude
    exclude_normalized: set[str] = set()
    if exclude_urls:
        for url in exclude_urls:
            exclude_normalized.add(_normalize_feed_url(url))

    # Load existing RSS entries and build a set of known feed URLs
    existing_urls: set[str] = set()
    existing_sources: list[dict[str, Any]] = []
    rss_defaults: dict[str, Any] = {"type": "rss"}
    removed = 0

    if rss_path.exists():
        try:
            raw_config = yaml.safe_load(rss_path.read_text())
            if raw_config:
                existing_config = SourceFileConfig.model_validate(raw_config)
                rss_defaults = raw_config.get("defaults", rss_defaults)
                for entry in existing_config.sources:
                    url = entry.get("url", "")
                    normalized = _normalize_feed_url(url)
                    if normalized in exclude_normalized:
                        logger.info(
                            f"Removing RSS entry (now in substack.yaml): {entry.get('name', url)}"
                        )
                        removed += 1
                        continue
                    existing_sources.append(entry)
                    existing_urls.add(normalized)
        except Exception as exc:
            logger.warning(f"Failed to read existing RSS sources: {exc}")

    added = 0
    already_existing = 0
    for sub in subscriptions:
        feed_url = sub.url.rstrip("/") + "/feed"
        normalized = _normalize_feed_url(feed_url)

        if normalized in existing_urls:
            already_existing += 1
            continue

        existing_sources.append({"name": sub.name, "url": feed_url})
        existing_urls.add(normalized)
        added += 1

    config = {
        "defaults": rss_defaults,
        "sources": existing_sources,
    }
    rss_path.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True))
    return added, already_existing, removed


def _normalize_feed_url(url: str) -> str:
    """Normalize a feed URL for dedup comparison.

    Strips scheme, www., and trailing /feed to compare base domains + paths.
    """
    from urllib.parse import urlparse

    parsed = urlparse(url.lower())
    host = parsed.netloc
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path.rstrip("/")
    if path.endswith("/feed"):
        path = path[: -len("/feed")]
    return f"{host}{path}"
