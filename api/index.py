from http.server import BaseHTTPRequestHandler
from urllib.parse import (
    urlparse,
    parse_qs,
    urlencode,
    urlunparse,
)
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import json
import re


ALLOWED_HOSTS = {
    "x.com",
    "www.x.com",
    "twitter.com",
    "www.twitter.com",
    "mobile.twitter.com",
    "m.twitter.com",
}


STATUS_RE = re.compile(
    r"/(?:status|statuses)/(\d+)(?:/|$)"
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


def best_video_format(
    item
):

    formats = (
        item.get("formats")
        or []
    )


    candidates = []


    for fmt in formats:

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
            container != "mp4"
        ):

            continue


        width = int(
            fmt.get("width")
            or 0
        )


        height = int(
            fmt.get("height")
            or 0
        )


        bitrate = int(
            fmt.get("bitrate")
            or 0
        )


        size = int(
            fmt.get("size")
            or 0
        )


        codec = (
            fmt.get("codec")
            or ""
        ).lower()


        compat = (
            1

            if codec in (
                "",
                "h264"
            )

            else 0
        )


        rank = (
            width * height,
            bitrate,
            size,
            compat,
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


    if item.get("url"):

        return {

            "url":
                item.get("url"),

            "width":
                item.get("width"),

            "height":
                item.get("height"),

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
                or "jpg"
            ).lower().replace(
                "jpeg",
                "jpg"
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
                        url,

                    "width":
                        item.get("width"),

                    "height":
                        item.get("height"),

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


            width = (
                best.get("width")
                or
                item.get("width")
            )


            height = (
                best.get("height")
                or
                item.get("height")
            )


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
                        width,

                    "height":
                        height,

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
                            (
                                f"相片拼圖 "
                                f"{photo_no}"
                            ),

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


            api_url = (
                "https://api.fxtwitter.com/"
                f"2/status/{status_id}"
            )


            req = Request(
                api_url,
                headers={
                    "User-Agent":
                        "XMediaDownloader/1.0",

                    "Accept":
                        "application/json",
                },
            )


            with urlopen(
                req,
                timeout=15
            ) as response:

                payload = json.loads(
                    response
                    .read()
                    .decode("utf-8")
                )


            code = int(
                payload.get("code")
                or 200
            )


            status = payload.get(
                "status"
            )


            if (
                code != 200
                or
                not isinstance(
                    status,
                    dict
                )
            ):

                message = (
                    payload.get(
                        "message"
                    )
                    or
                    "無法取得這則帖子，可能已刪除、受保護或暫時無法讀取"
                )


                send_json(
                    self,

                    (
                        404
                        if code == 404
                        else 502
                    ),

                    {
                        "ok": False,
                        "error": message,
                    },
                )


                return


            media = media_from_status(
                status
            )


            if not media:

                send_json(
                    self,
                    404,
                    {
                        "ok": False,

                        "error":
                            "這則帖子沒有可下載的 X 圖片或影片",
                    },
                )


                return


            author = (
                status.get("author")
                or {}
            )


            send_json(
                self,
                200,
                {
                    "ok":
                        True,

                    "post":
                        {
                            "id":
                                (
                                    status.get("id")
                                    or
                                    status_id
                                ),

                            "url":
                                (
                                    status.get("url")
                                    or
                                    raw_url
                                ),

                            "text":
                                (
                                    status.get("text")
                                    or ""
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
                                            or ""
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
                                            or ""
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
                    "ok": False,

                    "error":
                        str(exc),
                },
            )


        except HTTPError as exc:

            status_code = (
                404

                if exc.code == 404

                else 502
            )


            send_json(
                self,
                status_code,
                {
                    "ok": False,

                    "error":
                        (
                            "上游服務回應錯誤"
                            f"（HTTP {exc.code}）"
                        ),
                },
            )


        except URLError:

            send_json(
                self,
                502,
                {
                    "ok": False,

                    "error":
                        "目前無法連線到 X 媒體解析服務，請稍後再試",
                },
            )


        except Exception:

            send_json(
                self,
                500,
                {
                    "ok": False,

                    "error":
                        "伺服器發生未預期錯誤，請稍後再試",
                },
            )
