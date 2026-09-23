from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json
import re
import time

ALLOWED_HOSTS = {
    "x.com",
    "www.x.com",
    "twitter.com",
    "www.twitter.com",
    "mobile.twitter.com",
    "m.twitter.com",
}

STATUS_RE = re.compile(r"/(?:status|statuses)/(\d+)(?:/|$)")

# 這些上游錯誤會自動重試
RETRYABLE_HTTP = {
    404,
    408,
    425,
    429,
    500,
    502,
    503,
    504,
}

# 第一次失敗等 0.35 秒
# 第二次失敗等 0.8 秒
# 總共最多嘗試 3 次 v2
RETRY_DELAYS = (
    0.35,
    0.8,
)


def send_json(
    handler,
    status_code,
    payload
):
    body = json.dumps(
        payload,
        ensure_ascii=False
    ).encode("utf-8")

    handler.send_response(
        status_code
    )

    handler.send_header(
        "Content-Type",
        "application/json; charset=utf-8"
    )

    handler.send_header(
        "Cache-Control",
        "no-store"
    )

    handler.send_header(
        "X-Content-Type-Options",
        "nosniff"
    )

    handler.end_headers()

    handler.wfile.write(
        body
    )


def normalize_x_url(raw):

    raw = (
        raw or ""
    ).strip()

    if not raw:
        raise ValueError(
            "請貼上 X / Twitter 帖子連結"
        )

    if len(raw) > 2048:
        raise ValueError(
            "連結太長"
        )

    if not re.match(
        r"^https?://",
        raw,
        re.I
    ):
        raw = (
            "https://" +
            raw
        )

    parsed = urlparse(
        raw
    )

    host = (
        parsed.hostname or ""
    ).lower()

    if host not in ALLOWED_HOSTS:
        raise ValueError(
            "目前只支援 x.com / twitter.com 的公開帖子連結"
        )

    match = STATUS_RE.search(
        parsed.path
    )

    if not match:
        raise ValueError(
            "找不到帖子 ID，請貼上完整的 X 帖子連結"
        )

    return (
        raw,
        match.group(1)
    )


def original_photo_url(
    raw_url
):

    if not raw_url:
        return raw_url

    u = urlparse(
        raw_url
    )

    if (
        u.hostname !=
        "pbs.twimg.com"
    ):
        return raw_url

    q = parse_qs(
        u.query,
        keep_blank_values=True
    )

    q["name"] = [
        "orig"
    ]

    query = urlencode(
        [
            (k, v)

            for k, values
            in q.items()

            for v
            in values
        ]
    )

    return urlunparse(
        (
            u.scheme or "https",
            u.netloc,
            u.path,
            u.params,
            query,
            u.fragment,
        )
    )


def as_int(value):

    try:
        return int(
            value or 0
        )

    except (
        TypeError,
        ValueError
    ):
        return 0


def best_video_format(
    item
):

    formats = (
        item.get("formats")
        or []
    )

    if not isinstance(
        formats,
        list
    ):
        formats = []

    candidates = []

    for fmt in formats:

        if not isinstance(
            fmt,
            dict
        ):
            continue

        url = fmt.get(
            "url"
        )

        if not url:
            continue

        container = (
            fmt.get("container")
            or ""
        ).lower()

        if (
            container and
            container not in (
                "mp4",
                "video/mp4"
            )
        ):
            continue

        width = as_int(
            fmt.get("width")
        )

        height = as_int(
            fmt.get("height")
        )

        bitrate = as_int(
            fmt.get("bitrate")
        )

        size = as_int(
            fmt.get("size")
        )

        codec = (
            fmt.get("codec")
            or ""
        ).lower()

        safari_compat = (
            1

            if codec in (
                "",
                "h264",
                "avc1"
            )

            else 0
        )

        # 優先順序：
        # 1. 解析度
        # 2. bitrate
        # 3. 檔案大小
        # 4. Safari 相容性
        rank = (
            width * height,
            bitrate,
            size,
            safari_compat,
        )

        candidates.append(
            (
                rank,
                fmt
            )
        )

    if candidates:

        candidates.sort(
            key=lambda x: x[0],
            reverse=True
        )

        return (
            candidates[0][1]
        )

    # legacy API 通常已經直接給影片 URL
    if item.get("url"):

        return {
            "url":
                item.get("url"),

            "width":
                item.get("width"),

            "height":
                item.get("height"),

            "bitrate":
                item.get("bitrate"),

            "container":
                item.get("format")
                or "mp4",
        }

    return None


def media_from_status(
    status
):

    media = (
        status.get("media")
        or {}
    )

    if not isinstance(
        media,
        dict
    ):
        return []

    items = (
        media.get("all")
        or []
    )

    if not items:

        items = (
            (media.get("photos") or [])
            +
            (media.get("videos") or [])
        )

    result = []

    photo_no = 0
    video_no = 0

    for item in items:

        if not isinstance(
            item,
            dict
        ):
            continue

        mtype = (
            item.get("type")
            or ""
        ).lower()

        if mtype == "photo":

            photo_no += 1

            url = original_photo_url(
                item.get("url")
            )

            if not url:
                continue

            fmt = (
                item.get("format")
                or
                parse_qs(
                    urlparse(
                        url
                    ).query
                ).get(
                    "format",
                    ["jpg"]
                )[0]
                or
                "jpg"
            )

            fmt = (
                str(fmt)
                .lower()
                .replace(
                    "jpeg",
                    "jpg"
                )
            )

            result.append(
                {
                    "type":
                        "photo",

                    "label":
                        f"相片 {photo_no}",

                    "url":
                        url,

                    "preview":
                        (
                            item.get("url")
                            or
                            url
                        ),

                    "width":
                        item.get(
                            "width"
                        ),

                    "height":
                        item.get(
                            "height"
                        ),

                    "format":
                        fmt,
                }
            )

            continue


        if mtype in (
            "video",
            "gif"
        ):

            video_no += 1

            best = (
                best_video_format(
                    item
                )
            )

            if (
                not best
                or
                not best.get("url")
            ):
                continue

            result.append(
                {
                    "type":
                        (
                            "gif"

                            if mtype ==
                            "gif"

                            else
                            "video"
                        ),

                    "label":
                        (
                            f"GIF {video_no}"

                            if mtype ==
                            "gif"

                            else
                            f"影片 {video_no}"
                        ),

                    "url":
                        best.get("url"),

                    "preview":
                        (
                            item.get(
                                "thumbnail_url"
                            )
                            or ""
                        ),

                    "width":
                        (
                            best.get(
                                "width"
                            )
                            or
                            item.get(
                                "width"
                            )
                        ),

                    "height":
                        (
                            best.get(
                                "height"
                            )
                            or
                            item.get(
                                "height"
                            )
                        ),

                    "bitrate":
                        best.get(
                            "bitrate"
                        ),

                    "format":
                        "mp4",
                }
            )

            continue


        if (
            mtype ==
            "mosaic_photo"
        ):

            formats = (
                item.get("formats")
                or {}
            )

            if isinstance(
                formats,
                dict
            ):

                mosaic_url = (
                    formats.get("jpeg")
                    or
                    formats.get("webp")
                )

                if mosaic_url:

                    photo_no += 1

                    result.append(
                        {
                            "type":
                                "photo",

                            "label":
                                f"相片拼圖 {photo_no}",

                            "url":
                                mosaic_url,

                            "preview":
                                mosaic_url,

                            "width":
                                item.get(
                                    "width"
                                ),

                            "height":
                                item.get(
                                    "height"
                                ),

                            "format":
                                (
                                    "jpg"

                                    if formats.get(
                                        "jpeg"
                                    )

                                    else
                                    "webp"
                                ),
                        }
                    )

    return result


def read_http_error_json(
    exc
):

    try:

        raw = exc.read()

        if not raw:
            return None

        return json.loads(
            raw.decode(
                "utf-8",
                errors="replace"
            )
        )

    except Exception:
        return None


def fetch_json_once(
    url,
    timeout=5
):

    req = Request(
        url,
        headers={
            "User-Agent":
                "XMediaDownloader/2.0",

            "Accept":
                "application/json",

            "Cache-Control":
                "no-cache",
        },
    )

    with urlopen(
        req,
        timeout=timeout
    ) as response:

        return json.loads(
            response
            .read()
            .decode("utf-8")
        )


def fetch_fxtwitter_v2(
    status_id
):

    url = (
        "https://api.fxtwitter.com/"
        f"2/status/{status_id}"
    )

    last_error = None

    attempts = (
        len(RETRY_DELAYS)
        +
        1
    )

    for attempt in range(
        attempts
    ):

        try:

            payload = (
                fetch_json_once(
                    url,
                    timeout=5
                )
            )

            code = (
                as_int(
                    payload.get(
                        "code"
                    )
                )
                or
                200
            )

            status = (
                payload.get(
                    "status"
                )
            )

            if (
                code == 200
                and
                isinstance(
                    status,
                    dict
                )
            ):

                return (
                    status,
                    None
                )

            # 有些錯誤會以 HTTP 200
            # 但 JSON code != 200 回傳
            if (
                code in RETRYABLE_HTTP
                and
                attempt <
                attempts - 1
            ):

                time.sleep(
                    RETRY_DELAYS[
                        attempt
                    ]
                )

                continue

            return (
                None,
                {
                    "http":
                        code,

                    "message":
                        (
                            payload.get(
                                "message"
                            )
                            or
                            "API_FAIL"
                        ),

                    "payload":
                        payload,
                }
            )


        except HTTPError as exc:

            body = (
                read_http_error_json(
                    exc
                )
            )

            last_error = {
                "http":
                    exc.code,

                "message":
                    (
                        (
                            body or {}
                        ).get(
                            "message"
                        )

                        if isinstance(
                            body,
                            dict
                        )

                        else
                        None
                    ),

                "payload":
                    body,
            }

            if (
                exc.code
                in RETRYABLE_HTTP
                and
                attempt <
                attempts - 1
            ):

                time.sleep(
                    RETRY_DELAYS[
                        attempt
                    ]
                )

                continue

            return (
                None,
                last_error
            )


        except (
            URLError,
            TimeoutError,
            json.JSONDecodeError
        ) as exc:

            last_error = {
                "http":
                    0,

                "message":
                    str(exc),

                "payload":
                    None,
            }

            if (
                attempt <
                attempts - 1
            ):

                time.sleep(
                    RETRY_DELAYS[
                        attempt
                    ]
                )

                continue

            return (
                None,
                last_error
            )

    return (
        None,
        last_error
        or
        {
            "http": 0,
            "message": "unknown",
            "payload": None,
        }
    )


def fetch_fxtwitter_legacy(
    status_id
):

    url = (
        "https://api.fxtwitter.com/"
        f"i/status/{status_id}"
    )

    try:

        payload = (
            fetch_json_once(
                url,
                timeout=5
            )
        )

        code = (
            as_int(
                payload.get(
                    "code"
                )
            )
            or
            200
        )

        tweet = (
            payload.get(
                "tweet"
            )
        )

        if (
            code == 200
            and
            isinstance(
                tweet,
                dict
            )
        ):

            return (
                tweet,
                None
            )

        return (
            None,
            {
                "http":
                    code,

                "message":
                    (
                        payload.get(
                            "message"
                        )
                        or
                        "API_FAIL"
                    ),

                "payload":
                    payload,
            }
        )


    except HTTPError as exc:

        body = (
            read_http_error_json(
                exc
            )
        )

        return (
            None,
            {
                "http":
                    exc.code,

                "message":
                    (
                        (
                            body or {}
                        ).get(
                            "message"
                        )

                        if isinstance(
                            body,
                            dict
                        )

                        else
                        None
                    ),

                "payload":
                    body,
            }
        )


    except (
        URLError,
        TimeoutError,
        json.JSONDecodeError
    ) as exc:

        return (
            None,
            {
                "http":
                    0,

                "message":
                    str(exc),

                "payload":
                    None,
            }
        )


def fetch_status_resilient(
    status_id
):

    status, v2_error = (
        fetch_fxtwitter_v2(
            status_id
        )
    )

    if status:

        return (
            status,
            "v2",
            None
        )

    # v2 連續失敗後
    # 自動改走 legacy API
    legacy_status, legacy_error = (
        fetch_fxtwitter_legacy(
            status_id
        )
    )

    if legacy_status:

        return (
            legacy_status,
            "legacy",
            None
        )

    return (
        None,
        None,
        {
            "v2":
                v2_error,

            "legacy":
                legacy_error,
        }
    )


def final_error_from_upstream(
    errors
):

    v2 = (
        (errors or {}).get(
            "v2"
        )
        or {}
    )

    legacy = (
        (errors or {}).get(
            "legacy"
        )
        or {}
    )

    codes = {
        as_int(
            v2.get("http")
        ),

        as_int(
            legacy.get("http")
        ),
    }

    messages = (
        " ".join(
            str(x or "")

            for x in (
                v2.get("message"),
                legacy.get("message"),
            )
        )
        .upper()
    )

    if (
        401 in codes
        or
        403 in codes
        or
        "PRIVATE"
        in messages
    ):

        return (
            403,
            "這則帖子可能是私人／受保護內容，公開解析服務無法讀取"
        )

    # 只有 v2 和 legacy
    # 都明確回 404
    # 才當成真正不存在
    if codes == {404}:

        return (
            404,
            "找不到這則帖子，可能已刪除、網址無效或目前無法公開讀取"
        )

    # 只要其中一路 timeout / 5xx / 429
    # 就視為上游暫時故障
    return (
        503,
        "X 解析服務暫時不穩定，系統已自動重試仍未成功，請稍後再試"
    )


class handler(
    BaseHTTPRequestHandler
):

    def do_GET(self):

        try:

            parsed_request = (
                urlparse(
                    self.path
                )
            )

            qs = parse_qs(
                parsed_request.query
            )

            raw_url = (
                qs.get("url")
                or [""]
            )[0]

            _, status_id = (
                normalize_x_url(
                    raw_url
                )
            )

            (
                status,
                source,
                errors
            ) = (
                fetch_status_resilient(
                    status_id
                )
            )

            if not status:

                (
                    http_status,
                    message
                ) = (
                    final_error_from_upstream(
                        errors
                    )
                )

                send_json(
                    self,
                    http_status,
                    {
                        "ok":
                            False,

                        "error":
                            message,

                        "retryable":
                            (
                                http_status
                                ==
                                503
                            ),
                    },
                )

                return


            media = (
                media_from_status(
                    status
                )
            )

            if not media:

                send_json(
                    self,
                    404,
                    {
                        "ok":
                            False,

                        "error":
                            "這則帖子沒有可下載的 X 圖片或影片",
                    },
                )

                return


            author = (
                status.get(
                    "author"
                )
                or {}
            )

            send_json(
                self,
                200,
                {
                    "ok":
                        True,

                    "source":
                        source,

                    "post":
                        {
                            "id":
                                (
                                    status.get(
                                        "id"
                                    )
                                    or
                                    status_id
                                ),

                            "url":
                                (
                                    status.get(
                                        "url"
                                    )
                                    or
                                    raw_url
                                ),

                            "text":
                                (
                                    status.get(
                                        "text"
                                    )
                                    or
                                    ""
                                ),

                            "author":
                                {
                                    "name":
                                        (
                                            author.get(
                                                "name"
                                            )
                                            or
                                            author.get(
                                                "display_name"
                                            )
                                            or
                                            ""
                                        ),

                                    "username":
                                        (
                                            author.get(
                                                "screen_name"
                                            )
                                            or
                                            author.get(
                                                "username"
                                            )
                                            or
                                            ""
                                        ),
                                },
                        },

                    "media":
                        media,
                },
            )


        except ValueError as exc:

            send_json(
                self,
                400,
                {
                    "ok":
                        False,

                    "error":
                        str(exc),
                },
            )


        except Exception as exc:

            print(
                "Unhandled error:",
                repr(exc)
            )

            send_json(
                self,
                500,
                {
                    "ok":
                        False,

                    "error":
                        "伺服器發生未預期錯誤，請稍後再試",
                },
            )
