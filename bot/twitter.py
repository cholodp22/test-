"""thin async client for fetching tweets via x graphql (cookie auth)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, AsyncIterator

import httpx

log = logging.getLogger(__name__)

BEARER = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
    "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

USER_BY_SCREEN_NAME_URL = (
    "https://x.com/i/api/graphql/G3KGOASz96M-Qu0nwmGXNg/UserByScreenName"
)
USER_TWEETS_URL = (
    "https://x.com/i/api/graphql/HeWHY26ItCfUmm1e6ITjeA/UserTweets"
)


@dataclass(frozen=True)
class NewTweet:
    id: str
    username: str
    text: str
    url: str


def _parse_cookies(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for chunk in raw.split(";"):
        chunk = chunk.strip()
        if "=" in chunk:
            k, v = chunk.split("=", 1)
            out[k.strip()] = v.strip()
    return out


class TwitterClient:
    def __init__(self, cookies: str) -> None:
        self._cookies_str = cookies
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("twitter client not initialised — call start() first")
        return self._client

    async def start(self) -> None:
        cookies = _parse_cookies(self._cookies_str)
        if "auth_token" not in cookies or "ct0" not in cookies:
            raise RuntimeError(
                "X_COOKIES must contain auth_token and ct0 "
                "(e.g. 'auth_token=...; ct0=...')"
            )
        headers = {
            "Authorization": f"Bearer {BEARER}",
            "x-csrf-token": cookies["ct0"],
            "x-twitter-auth-type": "OAuth2Session",
            "x-twitter-active-user": "yes",
            "x-twitter-client-language": "en",
            "Referer": "https://x.com/",
            "Origin": "https://x.com",
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
        }
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
            cookies=cookies,
            headers=headers,
        )
        log.info("x graphql client ready (cookie-based auth)")

    async def stop(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def resolve_user_id(self, username: str) -> str | None:
        username = username.lstrip("@")
        params = {
            "variables": json.dumps(
                {"screen_name": username, "withSafetyModeUserFields": True}
            ),
            "features": json.dumps(_USER_FEATURES),
            "fieldToggles": json.dumps({"withAuxiliaryUserLabels": False}),
        }
        try:
            r = await self.client.get(USER_BY_SCREEN_NAME_URL, params=params)
        except httpx.HTTPError as exc:
            log.warning("user_by_login(%s) failed: %s", username, exc)
            return None
        if r.status_code != 200:
            log.warning(
                "user_by_login(%s) http %s: %s",
                username,
                r.status_code,
                r.text[:200],
            )
            return None
        try:
            data = r.json()
        except ValueError as exc:
            log.warning("user_by_login(%s) bad json: %s", username, exc)
            return None
        res = data.get("data", {}).get("user", {}).get("result")
        if not isinstance(res, dict):
            return None
        if res.get("__typename") == "UserUnavailable":
            return None
        uid = res.get("rest_id") or res.get("legacy", {}).get("id_str")
        return str(uid) if uid else None

    async def fetch_new(
        self,
        user_id: str,
        username: str,
        last_seen_id: str | None,
        limit: int,
    ) -> AsyncIterator[NewTweet]:
        """yield tweets newer than last_seen_id, oldest-first."""
        try:
            uid = str(int(user_id))
        except ValueError:
            log.warning("invalid user_id for %s: %r", username, user_id)
            return

        cutoff = int(last_seen_id) if last_seen_id and last_seen_id.isdigit() else 0
        params = {
            "variables": json.dumps(
                {
                    "userId": uid,
                    "count": max(1, min(limit, 40)),
                    "includePromotedContent": False,
                    "withQuickPromoteEligibilityTweetFields": False,
                    "withVoice": True,
                    "withV2Timeline": True,
                }
            ),
            "features": json.dumps(_TWEET_FEATURES),
        }
        try:
            r = await self.client.get(USER_TWEETS_URL, params=params)
        except httpx.HTTPError as exc:
            log.warning("user_tweets(%s) failed: %s", username, exc)
            return
        if r.status_code != 200:
            log.warning(
                "user_tweets(%s) http %s: %s",
                username,
                r.status_code,
                r.text[:200],
            )
            return
        try:
            data = r.json()
        except ValueError as exc:
            log.warning("user_tweets(%s) bad json: %s", username, exc)
            return

        collected: list[tuple[int, str, str]] = []
        for inner in _walk_timeline_tweets(data):
            legacy = inner.get("legacy", {})
            tid = legacy.get("id_str")
            if not tid or not tid.isdigit():
                continue
            if int(tid) <= cutoff:
                continue
            note = (
                inner.get("note_tweet", {})
                .get("note_tweet_results", {})
                .get("result", {})
                .get("text")
            )
            text = note or legacy.get("full_text") or ""
            collected.append((int(tid), tid, text))

        for _, tid, text in sorted(collected, key=lambda x: x[0]):
            yield NewTweet(
                id=tid,
                username=username,
                text=text,
                url=f"https://x.com/{username}/status/{tid}",
            )


def _walk_timeline_tweets(data: Any) -> list[dict[str, Any]]:
    """walk a UserTweets response and return each tweet's inner result dict."""
    out: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("__typename") == "TimelineTweet":
                tw = node.get("tweet_results", {}).get("result", {})
                inner = (
                    tw.get("tweet")
                    if tw.get("__typename") == "TweetWithVisibilityResults"
                    else tw
                )
                if isinstance(inner, dict):
                    out.append(inner)
                return
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    return out


_USER_FEATURES = {
    "hidden_profile_subscriptions_enabled": True,
    "rweb_tipjar_consumption_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "subscriptions_verification_info_is_identity_verified_enabled": True,
    "subscriptions_verification_info_verified_since_enabled": True,
    "highlights_tweets_tab_ui_enabled": True,
    "responsive_web_twitter_article_notes_tab_enabled": True,
    "subscriptions_feature_can_gift_premium": True,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "responsive_web_graphql_timeline_navigation_enabled": True,
}


_TWEET_FEATURES = {
    "rweb_lists_timeline_redesign_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "tweetypie_unmention_optimization_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": False,
    "tweet_awards_web_tipjar_consumption_enabled": True,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "responsive_web_media_download_video_enabled": False,
    "responsive_web_enhance_cards_enabled": False,
}
