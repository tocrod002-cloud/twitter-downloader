const ALLOWED_X_HOSTS = new Set([
  "x.com",
  "www.x.com",
  "twitter.com",
  "www.twitter.com",
  "mobile.twitter.com",
  "m.twitter.com"
]);

const ALLOWED_MEDIA_HOSTS = new Set([
  "video.twimg.com",
  "pbs.twimg.com"
]);

const STATUS_RE =
  /\/(?:status|statuses)\/(\d+)(?:\/|$)/;

const sleep = ms =>
  new Promise(resolve =>
    setTimeout(resolve, ms)
  );


function jsonResponse(
  data,
  status = 200
) {
  return new Response(
    JSON.stringify(data),
    {
      status,
      headers: {
        "Content-Type":
          "application/json; charset=utf-8",

        "Cache-Control":
          "no-store",

        "X-Content-Type-Options":
          "nosniff"
      }
    }
  );
}


function normalizeXUrl(raw) {
  raw = String(
    raw || ""
  ).trim();

  if (!raw) {
    throw new Error(
      "請貼上 X / Twitter 帖子連結"
    );
  }

  if (
    !/^https?:\/\//i.test(raw)
  ) {
    raw =
      "https://" + raw;
  }

  let parsed;

  try {
    parsed =
      new URL(raw);
  } catch {
    throw new Error(
      "X / Twitter 連結格式不正確"
    );
  }

  if (
    !ALLOWED_X_HOSTS.has(
      parsed.hostname.toLowerCase()
    )
  ) {
    throw new Error(
      "目前只支援 x.com / twitter.com 帖子"
    );
  }

  const match =
    parsed.pathname.match(
      STATUS_RE
    );

  if (!match) {
    throw new Error(
      "找不到帖子 ID，請貼上完整的帖子連結"
    );
  }

  return {
    raw,
    id: match[1]
  };
}


function numberValue(value) {
  const n =
    Number(value);

  return Number.isFinite(n)
    ? n
    : 0;
}


function originalPhotoUrl(
  rawUrl
) {
  try {
    const url =
      new URL(rawUrl);

    if (
      url.hostname ===
      "pbs.twimg.com"
    ) {
      url.searchParams.set(
        "name",
        "orig"
      );
    }

    return url.toString();

  } catch {
    return rawUrl;
  }
}


function bestVideoFormat(
  item
) {
  const formats =
    Array.isArray(
      item?.formats
    )
      ? item.formats
      : [];

  const candidates =
    formats.filter(fmt => {
      if (!fmt?.url) {
        return false;
      }

      const container =
        String(
          fmt.container || ""
        ).toLowerCase();

      /*
       * m3u8 是串流播放清單，
       * 不拿它做直接 MP4 下載。
       */
      return (
        !container ||
        container === "mp4" ||
        container === "video/mp4"
      );
    });

  candidates.sort(
    (a, b) => {
      const areaA =
        numberValue(a.width) *
        numberValue(a.height);

      const areaB =
        numberValue(b.width) *
        numberValue(b.height);

      if (
        areaB !== areaA
      ) {
        return (
          areaB - areaA
        );
      }

      const bitrateDiff =
        numberValue(
          b.bitrate
        ) -
        numberValue(
          a.bitrate
        );

      if (
        bitrateDiff !== 0
      ) {
        return bitrateDiff;
      }

      return (
        numberValue(b.size) -
        numberValue(a.size)
      );
    }
  );

  if (
    candidates.length > 0
  ) {
    return candidates[0];
  }

  if (item?.url) {
    return {
      url:
        item.url,

      width:
        item.width,

      height:
        item.height,

      bitrate:
        item.bitrate,

      container:
        "mp4"
    };
  }

  return null;
}


function extractMedia(
  status
) {
  const media =
    status?.media || {};

  let all =
    Array.isArray(media.all)
      ? media.all
      : [];

  if (!all.length) {
    all = [
      ...(
        Array.isArray(
          media.photos
        )
          ? media.photos
          : []
      ),

      ...(
        Array.isArray(
          media.videos
        )
          ? media.videos
          : []
      )
    ];
  }

  const output = [];

  let photoIndex = 0;
  let videoIndex = 0;

  for (
    const item of all
  ) {
    if (
      !item ||
      typeof item !==
        "object"
    ) {
      continue;
    }

    const type =
      String(
        item.type || ""
      ).toLowerCase();


    if (
      type === "photo"
    ) {
      const url =
        originalPhotoUrl(
          item.url
        );

      if (!url) {
        continue;
      }

      photoIndex += 1;

      output.push({
        type:
          "photo",

        label:
          `相片 ${photoIndex}`,

        url,

        preview:
          item.url || url,

        width:
          item.width || null,

        height:
          item.height || null,

        format:
          (
            item.format ||
            new URL(url)
              .searchParams
              .get("format") ||
            "jpg"
          )
          .toLowerCase()
          .replace(
            "jpeg",
            "jpg"
          )
      });

      continue;
    }


    if (
      type === "video" ||
      type === "gif"
    ) {
      const best =
        bestVideoFormat(
          item
        );

      if (!best?.url) {
        continue;
      }

      videoIndex += 1;

      output.push({
        type:
          type === "gif"
            ? "gif"
            : "video",

        label:
          type === "gif"
            ? `GIF ${videoIndex}`
            : `影片 ${videoIndex}`,

        url:
          best.url,

        preview:
          item.thumbnail_url ||
          "",

        width:
          best.width ||
          item.width ||
          null,

        height:
          best.height ||
          item.height ||
          null,

        bitrate:
          best.bitrate ||
          null,

        format:
          "mp4"
      });

      continue;
    }


    if (
      type ===
      "mosaic_photo"
    ) {
      const formats =
        item.formats || {};

      const imageUrl =
        formats.jpeg ||
        formats.webp;

      if (!imageUrl) {
        continue;
      }

      photoIndex += 1;

      output.push({
        type:
          "photo",

        label:
          `相片 ${photoIndex}`,

        url:
          imageUrl,

        preview:
          imageUrl,

        width:
          item.width || null,

        height:
          item.height || null,

        format:
          formats.jpeg
            ? "jpg"
            : "webp"
      });
    }
  }

  return output;
}


async function fetchFxStatus(
  statusId
) {
  const apiUrl =
    "https://api.fxtwitter.com/" +
    "2/status/" +
    encodeURIComponent(
      statusId
    );

  /*
   * 上游偶發 404 / 5xx 時，
   * Worker 自己重試，
   * 不再需要使用者一直按按鈕。
   */
  const delays = [
    0,
    300,
    800,
    1500
  ];

  let lastStatus = 0;

  for (
    let i = 0;
    i < delays.length;
    i++
  ) {
    if (delays[i]) {
      await sleep(
        delays[i]
      );
    }

    try {
      const response =
        await fetch(
          apiUrl,
          {
            headers: {
              "Accept":
                "application/json",

              "User-Agent":
                "X-Media-Downloader/3.0",

              "Cache-Control":
                "no-cache"
            },

            cf: {
              cacheTtl: 0
            }
          }
        );

      lastStatus =
        response.status;

      let payload = null;

      try {
        payload =
          await response.json();
      } catch {
        payload = null;
      }

      if (
        response.ok &&
        payload?.status &&
        payload.status.type !==
          "tombstone"
      ) {
        return payload.status;
      }

      /*
       * 400 / 401 / 403 等通常不是
       * 短暫故障，不需要一直 retry。
       */
      if (
        response.status === 400 ||
        response.status === 401 ||
        response.status === 403
      ) {
        break;
      }

    } catch (error) {
      console.log(
        "FxTwitter attempt failed:",
        String(error)
      );
    }
  }

  const error =
    new Error(
      lastStatus === 404
        ? "解析服務暫時未取得這則帖子，請稍後再試"
        : "X 解析服務暫時無法使用，請稍後再試"
    );

  error.status =
    lastStatus || 503;

  throw error;
}


async function handleApi(
  request
) {
  const requestUrl =
    new URL(
      request.url
    );

  const raw =
    requestUrl.searchParams.get(
      "url"
    );

  let parsed;

  try {
    parsed =
      normalizeXUrl(
        raw
      );
  } catch (error) {
    return jsonResponse(
      {
        ok: false,
        error:
          error.message
      },
      400
    );
  }

  try {
    const status =
      await fetchFxStatus(
        parsed.id
      );

    const media =
      extractMedia(
        status
      );

    if (
      media.length === 0
    ) {
      return jsonResponse(
        {
          ok: false,

          error:
            "這則帖子沒有找到可下載的圖片或影片"
        },
        404
      );
    }

    const author =
      status.author || {};

    return jsonResponse(
      {
        ok: true,

        post: {
          id:
            status.id ||
            parsed.id,

          url:
            status.url ||
            parsed.raw,

          text:
            status.text ||
            "",

          author: {
            name:
              author.name ||
              author.display_name ||
              "",

            username:
              author.screen_name ||
              author.username ||
              ""
          }
        },

        media
      }
    );

  } catch (error) {
    const status =
      Number(
        error.status
      ) || 503;

    return jsonResponse(
      {
        ok: false,

        error:
          error.message ||
          "解析服務暫時無法使用"
      },
      (
        status >= 400 &&
        status < 600
      )
        ? status
        : 503
    );
  }
}


function safeFilename(
  filename
) {
  return String(
    filename ||
    "X-media"
  )
    .replace(
      /[\r\n"]/g,
      ""
    )
    .slice(
      0,
      180
    );
}


function asciiFilename(
  filename
) {
  return safeFilename(
    filename
  )
    .replace(
      /[^\x20-\x7E]/g,
      "_"
    )
    .replace(
      /[\\/:*?"<>|]/g,
      "_"
    );
}


async function handleDownload(
  request
) {
  if (
    request.method !== "GET" &&
    request.method !== "HEAD"
  ) {
    return new Response(
      "Method not allowed",
      {
        status: 405
      }
    );
  }

  const requestUrl =
    new URL(
      request.url
    );

  const rawMediaUrl =
    requestUrl.searchParams.get(
      "url"
    );

  if (!rawMediaUrl) {
    return new Response(
      "Missing media URL",
      {
        status: 400
      }
    );
  }

  let mediaUrl;

  try {
    mediaUrl =
      new URL(
        rawMediaUrl
      );
  } catch {
    return new Response(
      "Invalid media URL",
      {
        status: 400
      }
    );
  }

  if (
    mediaUrl.protocol !==
      "https:" ||
    !ALLOWED_MEDIA_HOSTS.has(
      mediaUrl.hostname
    )
  ) {
    return new Response(
      "Media host not allowed",
      {
        status: 403
      }
    );
  }

  const upstreamHeaders =
    new Headers();

  upstreamHeaders.set(
    "Accept",
    "*/*"
  );

  upstreamHeaders.set(
    "Accept-Encoding",
    "identity"
  );

  /*
   * Safari 下載管理器會送 Range，
   * 一定要原樣傳給 Twitter CDN。
   */
  const passthrough =
    [
      "range",
      "if-range",
      "if-none-match",
      "if-modified-since"
    ];

  for (
    const headerName
    of passthrough
  ) {
    const value =
      request.headers.get(
        headerName
      );

    if (value) {
      upstreamHeaders.set(
        headerName,
        value
      );
    }
  }

  let upstream;

  try {
    upstream =
      await fetch(
        mediaUrl.toString(),
        {
          method:
            request.method,

          headers:
            upstreamHeaders,

          redirect:
            "follow"
        }
      );

  } catch (error) {
    return new Response(
      "Unable to connect to media server",
      {
        status: 502
      }
    );
  }

  if (
    upstream.status >= 400
  ) {
    return new Response(
      `Media server returned HTTP ${upstream.status}`,
      {
        status:
          upstream.status
      }
    );
  }

  const headers =
    new Headers();

  /*
   * Safari 顯示下載大小、
   * 進度及續傳所需要的 headers。
   */
  const copyHeaders = [
    "content-type",
    "content-length",
    "content-range",
    "accept-ranges",
    "etag",
    "last-modified"
  ];

  for (
    const name of copyHeaders
  ) {
    const value =
      upstream.headers.get(
        name
      );

    if (value) {
      headers.set(
        name,
        value
      );
    }
  }

  if (
    !headers.has(
      "accept-ranges"
    )
  ) {
    headers.set(
      "Accept-Ranges",
      "bytes"
    );
  }

  const requestedName =
    safeFilename(
      requestUrl.searchParams.get(
        "filename"
      ) ||
      (
        mediaUrl.hostname ===
        "video.twimg.com"
          ? "X-video.mp4"
          : "X-photo.jpg"
      )
    );

  const fallbackName =
    asciiFilename(
      requestedName
    );

  headers.set(
    "Content-Disposition",
    `attachment; filename="${fallbackName}"; filename*=UTF-8''${encodeURIComponent(requestedName)}`
  );

  headers.set(
    "X-Content-Type-Options",
    "nosniff"
  );

  headers.set(
    "Cache-Control",
    "private, no-store"
  );

  if (
    request.method ===
    "HEAD"
  ) {
    return new Response(
      null,
      {
        status:
          upstream.status,

        headers
      }
    );
  }

  /*
   * 不讀成 Blob / ArrayBuffer。
   * 直接串流給 Safari。
   */
  return new Response(
    upstream.body,
    {
      status:
        upstream.status,

      headers
    }
  );
}


export default {
  async fetch(
    request,
    env
  ) {
    const url =
      new URL(
        request.url
      );

    if (
      url.pathname ===
        "/api" ||
      url.pathname ===
        "/api/"
    ) {
      return handleApi(
        request
      );
    }

    if (
      url.pathname ===
        "/download" ||
      url.pathname ===
        "/download/"
    ) {
      return handleDownload(
        request
      );
    }

    /*
     * 其他路徑交給 public/
     * 靜態檔案。
     */
    return env.ASSETS.fetch(
      request
    );
  }
};
