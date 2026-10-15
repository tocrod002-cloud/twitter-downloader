
const X_HOSTS = new Set([
  'x.com', 'www.x.com',
  'twitter.com', 'www.twitter.com',
  'mobile.twitter.com', 'm.twitter.com'
]);

const MEDIA_HOSTS = new Set([
  'video.twimg.com',
  'pbs.twimg.com'
]);

const wait = ms =>
  new Promise(resolve => setTimeout(resolve, ms));

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff'
    }
  });
}

function parsePostLink(raw) {
  const text = String(raw || '').trim();

  if (!text || text.length > 2048) {
    throw new Error('請貼上完整的 X 帖子連結');
  }

  let url;

  try {
    url = new URL(
      /^https?:\/\//i.test(text)
        ? text
        : `https://${text}`
    );
  } catch {
    throw new Error('連結格式不正確');
  }

  if (
    !['https:', 'http:'].includes(url.protocol) ||
    !X_HOSTS.has(url.hostname.toLowerCase())
  ) {
    throw new Error(
      '只支援 x.com 或 twitter.com 帖子連結'
    );
  }

  const m = url.pathname.match(
    /^\/([^/]+)\/(?:status|statuses)\/(\d+)(?:\/|$)/
  );

  if (!m) {
    throw new Error(
      '找不到帖子 ID，請複製完整帖子連結'
    );
  }

  return {
    handle: m[1],
    id: m[2],
    url: url.toString()
  };
}

function number(value) {
  const n = Number(value);

  return Number.isFinite(n) && n > 0
    ? n
    : 0;
}

function mediaUrl(raw, host) {
  try {
    const u = new URL(raw);

    return (
      u.protocol === 'https:' &&
      u.hostname === host
    ) ? u : null;
  } catch {
    return null;
  }
}

function originalPhoto(raw) {
  const u = mediaUrl(raw, 'pbs.twimg.com');

  if (!u) return null;

  u.searchParams.set('name', 'orig');

  return u.toString();
}

function photoFormat(raw, proposed) {
  const fmt = String(proposed || '').toLowerCase();

  if (['jpg', 'jpeg', 'png', 'webp'].includes(fmt)) {
    return fmt === 'jpeg' ? 'jpg' : fmt;
  }

  try {
    const u = new URL(raw);

    const queryFmt = (
      u.searchParams.get('format') || ''
    ).toLowerCase();

    if (
      ['jpg', 'jpeg', 'png', 'webp'].includes(queryFmt)
    ) {
      return queryFmt === 'jpeg'
        ? 'jpg'
        : queryFmt;
    }

    const pathFmt = u.pathname.match(
      /\.(jpg|jpeg|png|webp)$/i
    )?.[1]?.toLowerCase();

    return pathFmt === 'jpeg'
      ? 'jpg'
      : (pathFmt || 'jpg');
  } catch {
    return 'jpg';
  }
}

function bestMP4(item) {
  const formats = Array.isArray(item.formats)
    ? item.formats
    : [];

  const options = formats.filter(f => {
    if (
      !f?.url ||
      !mediaUrl(f.url, 'video.twimg.com')
    ) {
      return false;
    }

    const container = String(
      f.container || ''
    ).toLowerCase();

    return (
      container === 'mp4' ||
      container === 'video/mp4' ||
      (
        !container &&
        /\.mp4(?:\?|$)/i.test(f.url)
      )
    );
  });

  options.sort((a, b) =>
    number(b.width) * number(b.height) -
    number(a.width) * number(a.height) ||
    number(b.bitrate) - number(a.bitrate) ||
    number(b.size) - number(a.size)
  );

  if (options.length) {
    return options[0];
  }

  if (
    item.url &&
    mediaUrl(item.url, 'video.twimg.com') &&
    /\.mp4(?:\?|$)/i.test(item.url)
  ) {
    return item;
  }

  return null;
}

function fromFx(status) {
  const media = status?.media || {};

  const all =
    Array.isArray(media.all) && media.all.length
      ? media.all
      : [
          ...(Array.isArray(media.photos)
            ? media.photos : []),
          ...(Array.isArray(media.videos)
            ? media.videos : [])
        ];

  const output = [];
  let p = 0;
  let v = 0;

  for (const item of all) {
    if (!item || typeof item !== 'object') {
      continue;
    }

    const type = String(
      item.type || ''
    ).toLowerCase();

    if (type === 'photo' || type === 'image') {
      const url = originalPhoto(item.url);

      if (!url) continue;

      output.push({
        type: 'photo',
        label: `相片 ${++p}`,
        url,
        preview: item.url || url,
        width: item.width || null,
        height: item.height || null,
        format: photoFormat(url, item.format)
      });

    } else if (
      type === 'video' ||
      type === 'gif' ||
      type === 'animated_gif'
    ) {
      const best = bestMP4(item);

      if (!best) continue;

      output.push({
        type: type === 'video' ? 'video' : 'gif',
        label:
          `${type === 'video' ? '影片' : 'GIF'} ${++v}`,
        url: best.url,
        preview: item.thumbnail_url || '',
        width: best.width || item.width || null,
        height: best.height || item.height || null,
        bitrate: best.bitrate || null,
        format: 'mp4'
      });

    } else if (type === 'mosaic_photo') {
      const u =
        item.formats?.jpeg ||
        item.formats?.webp;

      if (!u || !mediaUrl(u, 'pbs.twimg.com')) {
        continue;
      }

      output.push({
        type: 'photo',
        label: `相片 ${++p}`,
        url: originalPhoto(u),
        preview: u,
        width: item.width || null,
        height: item.height || null,
        format: photoFormat(u)
      });
    }
  }

  return output;
}

function fromVx(data) {
  const output = [];
  let p = 0;
  let v = 0;

  const entries =
    Array.isArray(data.media_extended) &&
    data.media_extended.length
      ? data.media_extended
      : (
          Array.isArray(data.mediaURLs)
            ? data.mediaURLs.map(url => ({ url }))
            : []
        );

  for (const item of entries) {
    if (!item?.url) continue;

    let host = '';

    try {
      host = new URL(item.url).hostname;
    } catch {
      continue;
    }

    if (host === 'pbs.twimg.com') {
      const url = originalPhoto(item.url);

      output.push({
        type: 'photo',
        label: `相片 ${++p}`,
        url,
        preview: item.thumbnail_url || item.url,
        width: item.size?.width || null,
        height: item.size?.height || null,
        format: photoFormat(url)
      });

    } else if (
      host === 'video.twimg.com' &&
      /\.mp4(?:\?|$)/i.test(item.url)
    ) {
      output.push({
        type: 'video',
        label: `影片 ${++v}`,
        url: item.url,
        preview: item.thumbnail_url || '',
        width: item.size?.width || null,
        height: item.size?.height || null,
        bitrate: null,
        format: 'mp4'
      });
    }
  }

  return output;
}

async function getJson(url) {
  const response = await fetch(url, {
    headers: {
      'Accept': 'application/json'
    },
    signal: AbortSignal.timeout(7000),
    redirect: 'follow'
  });

  let data;

  try {
    data = await response.json();
  } catch {
    throw new Error(
      `HTTP ${response.status} 非 JSON 回應`
    );
  }

  if (
    !response.ok ||
    !data ||
    (data.code && data.code !== 200)
  ) {
    throw new Error(
      `HTTP ${response.status} / code ${data?.code || '?'}`
    );
  }

  return data;
}

async function resolvePost(post) {
  const paths = [
    {
      name: 'FxTwitter v2',
      url:
        `https://api.fxtwitter.com/2/status/${post.id}`,
      parse: d => ({
        status: d.status,
        media: fromFx(d.status)
      })
    },
    {
      name: 'FxTwitter 備援',
      url:
        'https://api.fxtwitter.com/' +
        `${encodeURIComponent(post.handle)}/status/${post.id}`,
      parse: d => ({
        status: d.tweet || d.status,
        media: fromFx(d.tweet || d.status)
      })
    },
    {
      name: 'VXTwitter 備援',
      url:
        'https://api.vxtwitter.com/' +
        `${encodeURIComponent(post.handle)}/status/${post.id}`,
      parse: d => ({
        status: {
          id: d.tweetID || post.id,
          text: d.text || '',
          author: {
            name: d.user_name || '',
            screen_name: d.user_screen_name || ''
          }
        },
        media: fromVx(d)
      })
    }
  ];

  const errors = [];

  for (const path of paths) {
    const attempts =
      path.name === 'FxTwitter v2' ? 2 : 1;

    for (let i = 0; i < attempts; i++) {
      if (i) await wait(500);

      try {
        const data = await getJson(path.url);
        const parsed = path.parse(data);

        if (
          !parsed.status ||
          parsed.status.type === 'tombstone'
        ) {
          throw new Error('帖子不可公開讀取');
        }

        if (!parsed.media.length) {
          throw new Error('未找到可用 MP4／圖片');
        }

        return {
          ...parsed,
          source: path.name
        };

      } catch (e) {
        errors.push(
          `${path.name}: ${
            String(e?.message || e).slice(0, 65)
          }`
        );
      }
    }
  }

  console.log(
    'X parsing failures',
    post.id,
    errors.join(' | ')
  );

  return { errors };
}

async function handleApi(request) {
  let post;

  try {
    post = parsePostLink(
      new URL(request.url).searchParams.get('url')
    );
  } catch (e) {
    return json({
      ok: false,
      error: e.message
    }, 400);
  }

  const result = await resolvePost(post);

  if (result.errors) {
    const details = result.errors
      .map(x => x
        .replace('FxTwitter v2: ', 'v2 ')
        .replace('FxTwitter 備援: ', 'Fx備援 ')
        .replace('VXTwitter 備援: ', 'VX備援 ')
      )
      .join('；')
      .slice(0, 190);

    return json({
      ok: false,
      error: '公開解析來源都未能讀取帖子。' + details,
      detail: result.errors.join('；'),
      retryable: true
    }, 503);
  }

  const author = result.status.author || {};

  return json({
    ok: true,
    source: result.source,

    post: {
      id: result.status.id || post.id,
      url: result.status.url || post.url,
      text: result.status.text || '',
      author: {
        name:
          author.name ||
          author.display_name ||
          '',
        username:
          author.screen_name ||
          author.username ||
          ''
      }
    },

    media: result.media
  });
}

function cleanFilename(value, fallback) {
  const name = String(value || fallback)
    .replace(/[\r\n\\/"<>:|?*\x00-\x1F]/g, '_')
    .slice(0, 120);

  return name || fallback;
}

async function handleDownload(request) {
  if (!['GET', 'HEAD'].includes(request.method)) {
    return new Response('Method not allowed', {
      status: 405
    });
  }

  const params =
    new URL(request.url).searchParams;

  let upstreamUrl;

  try {
    upstreamUrl = new URL(
      params.get('url')
    );
  } catch {
    return new Response('Invalid media URL', {
      status: 400
    });
  }

  if (
    upstreamUrl.protocol !== 'https:' ||
    !MEDIA_HOSTS.has(upstreamUrl.hostname)
  ) {
    return new Response(
      'Media host not allowed',
      { status: 403 }
    );
  }

  const headers = new Headers({
    'Accept': '*/*',
    'Accept-Encoding': 'identity'
  });

  for (
    const h of [
      'range',
      'if-range',
      'if-none-match',
      'if-modified-since'
    ]
  ) {
    const value = request.headers.get(h);

    if (value) {
      headers.set(h, value);
    }
  }

  let upstream;

  try {
    upstream = await fetch(
      upstreamUrl.toString(),
      {
        method: request.method,
        headers,
        redirect: 'follow'
      }
    );
  } catch {
    return new Response(
      'Media CDN temporarily unavailable',
      { status: 502 }
    );
  }

  if (!upstream.ok) {
    return new Response(
      `Media CDN HTTP ${upstream.status}`,
      { status: upstream.status }
    );
  }

  const resHeaders = new Headers();

  for (
    const h of [
      'content-type',
      'content-length',
      'content-range',
      'accept-ranges',
      'etag',
      'last-modified'
    ]
  ) {
    const value = upstream.headers.get(h);

    if (value) {
      resHeaders.set(h, value);
    }
  }

  const fallback =
    upstreamUrl.hostname === 'video.twimg.com'
      ? 'X-video.mp4'
      : 'X-photo.jpg';

  const filename = cleanFilename(
    params.get('filename'),
    fallback
  );

  const ascii = filename.replace(
    /[^\x20-\x7E]/g,
    '_'
  );

  resHeaders.set(
    'Content-Disposition',
    `attachment; filename="${ascii}"; filename*=UTF-8''${encodeURIComponent(filename)}`
  );

  resHeaders.set(
    'Cache-Control',
    'private, no-store'
  );

  resHeaders.set(
    'X-Content-Type-Options',
    'nosniff'
  );

  return new Response(
    request.method === 'HEAD'
      ? null
      : upstream.body,
    {
      status: upstream.status,
      headers: resHeaders
    }
  );
}

export default {
  async fetch(request, env) {
    const path =
      new URL(request.url).pathname;

    if (
      path === '/api' ||
      path === '/api/'
    ) {
      if (request.method !== 'GET') {
        return json({
          ok: false,
          error: 'Method not allowed'
        }, 405);
      }

      try {
        return await handleApi(request);
      } catch (e) {
        console.error('API failure', e);

        return json({
          ok: false,
          error: '解析器內部錯誤，請查看 Cloudflare Logs'
        }, 500);
      }
    }

    if (
      path === '/download' ||
      path === '/download/'
    ) {
      return handleDownload(request);
    }

    return env.ASSETS.fetch(request);
  }
};
