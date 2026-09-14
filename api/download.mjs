const ALLOWED_HOSTS = new Set([
  "video.twimg.com",
  "pbs.twimg.com"
]);

function errorResponse(message, status = 400) {
  return new Response(message, {
    status,
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-store"
    }
  });
}

function makeFilename(rawName, mediaUrl) {
  let name = (rawName || "").trim();

  if (!name) {
    const path = mediaUrl.pathname.toLowerCase();

    if (path.endsWith(".mp4")) {
      name = "X-video.mp4";
    } else {
      const format =
        mediaUrl.searchParams.get("format") ||
        path.split(".").pop() ||
        "jpg";

      name = `X-photo.${format}`;
    }
  }

  // 防止 header 注入及奇怪字符
  name = name
    .replace(/[\r\n"]/g, "")
    .slice(0, 160);

  return name || "X-media";
}

function asciiFilename(name) {
  return name
    .replace(/[^\x20-\x7E]/g, "_")
    .replace(/[\\/:*?"<>|]/g, "_");
}

export default {
  async fetch(request) {
    if (
      request.method !== "GET" &&
      request.method !== "HEAD"
    ) {
      return errorResponse(
        "Method not allowed",
        405
      );
    }

    const requestUrl = new URL(request.url);

    const rawUrl =
      requestUrl.searchParams.get("url");

    const requestedFilename =
      requestUrl.searchParams.get("filename");

    if (!rawUrl) {
      return errorResponse(
        "Missing media URL"
      );
    }

    let mediaUrl;

    try {
      mediaUrl = new URL(rawUrl);
    } catch {
      return errorResponse(
        "Invalid media URL"
      );
    }

    if (
      mediaUrl.protocol !== "https:" ||
      !ALLOWED_HOSTS.has(mediaUrl.hostname)
    ) {
      return errorResponse(
        "Media host is not allowed",
        403
      );
    }

    /*
     * Safari 的下載管理器會使用 Range request。
     * 一定要把 Range / If-Range 傳到 Twitter CDN。
     */
    const upstreamHeaders = new Headers();

    upstreamHeaders.set(
      "Accept",
      "*/*"
    );

    upstreamHeaders.set(
      "Accept-Encoding",
      "identity"
    );

    const range =
      request.headers.get("range");

    const ifRange =
      request.headers.get("if-range");

    const ifNoneMatch =
      request.headers.get("if-none-match");

    const ifModifiedSince =
      request.headers.get(
        "if-modified-since"
      );

    if (range) {
      upstreamHeaders.set(
        "Range",
        range
      );
    }

    if (ifRange) {
      upstreamHeaders.set(
        "If-Range",
        ifRange
      );
    }

    if (ifNoneMatch) {
      upstreamHeaders.set(
        "If-None-Match",
        ifNoneMatch
      );
    }

    if (ifModifiedSince) {
      upstreamHeaders.set(
        "If-Modified-Since",
        ifModifiedSince
      );
    }

    let upstream;

    try {
      upstream = await fetch(
        mediaUrl.toString(),
        {
          method: request.method,

          headers:
            upstreamHeaders,

          redirect:
            "follow",

          cache:
            "no-store"
        }
      );
    } catch (error) {
      console.error(
        "Upstream fetch failed:",
        error
      );

      return errorResponse(
        "Unable to connect to media server",
        502
      );
    }

    /*
     * 保留 Safari 下載及續傳所需要的 header。
     */
    const responseHeaders =
      new Headers();

    const copyHeaders = [
      "content-type",
      "content-length",
      "content-range",
      "accept-ranges",
      "etag",
      "last-modified"
    ];

    for (const header of copyHeaders) {
      const value =
        upstream.headers.get(header);

      if (value) {
        responseHeaders.set(
          header,
          value
        );
      }
    }

    /*
     * 如果 Twitter CDN 沒有明確提供 Accept-Ranges，
     * 我們仍告訴 Safari 可以使用 byte ranges。
     */
    if (
      !responseHeaders.has(
        "accept-ranges"
      )
    ) {
      responseHeaders.set(
        "Accept-Ranges",
        "bytes"
      );
    }

    const filename =
      makeFilename(
        requestedFilename,
        mediaUrl
      );

    const fallbackName =
      asciiFilename(filename);

    const encodedName =
      encodeURIComponent(filename);

    responseHeaders.set(
      "Content-Disposition",
      `attachment; filename="${fallbackName}"; filename*=UTF-8''${encodedName}`
    );

    responseHeaders.set(
      "X-Content-Type-Options",
      "nosniff"
    );

    responseHeaders.set(
      "Cache-Control",
      "private, no-store"
    );

    /*
     * HEAD request 只回 headers，不傳 body。
     */
    if (
      request.method === "HEAD"
    ) {
      return new Response(
        null,
        {
          status:
            upstream.status,

          headers:
            responseHeaders
        }
      );
    }

    /*
     * 關鍵：
     * 不把影片讀成 ArrayBuffer / Blob。
     * 直接把 Twitter CDN 的 ReadableStream
     * 串流到 Safari。
     */
    return new Response(
      upstream.body,
      {
        status:
          upstream.status,

        headers:
          responseHeaders
      }
    );
  }
};
