import { createServer } from "node:http";
import { readFileSync } from "node:fs";

const port = Number(process.env.PORT || 8080);
const engineBase = (process.env.ACE_ENGINE_BASE_URL || "").replace(/\/$/, "");
const publicBase = (process.env.PUBLIC_BASE_URL || "").replace(/\/$/, "");
const channelFile = process.env.CHANNELS_FILE || "config/authorized-channels.json";
const tokenStore = new Map();
const TOKEN_TTL_MS = 90_000;

function loadChannels() {
  const document = JSON.parse(readFileSync(channelFile, "utf8"));
  const channels = Array.isArray(document.channels) ? document.channels : [];
  const accepted = new Map();
  for (const channel of channels) {
    const id = String(channel.id || "").trim();
    const contentId = String(channel.content_id || "").trim();
    const rights = String(channel.rights_attestation || "").trim();
    if (!/^[a-z0-9-]{2,64}$/i.test(id) || !contentId || !rights) continue;
    accepted.set(id, { id, contentId, rights, name: String(channel.name || id) });
  }
  return accepted;
}

function send(response, status, body, contentType = "text/plain; charset=utf-8") {
  response.writeHead(status, {
    "content-type": contentType,
    "cache-control": "no-store",
    "access-control-allow-origin": "*"
  });
  response.end(body);
}

function issueToken(url) {
  const token = crypto.randomUUID().replaceAll("-", "");
  tokenStore.set(token, { url, expires: Date.now() + TOKEN_TTL_MS });
  return token;
}

function consumeToken(token) {
  const entry = tokenStore.get(token);
  tokenStore.delete(token);
  if (!entry || entry.expires < Date.now()) return null;
  return entry.url;
}

function hlsType(url) {
  return url.includes(".m3u8") ? "application/vnd.apple.mpegurl" : "video/mp2t";
}

function rewriteManifest(body, manifestUrl, channelId) {
  return body.split(/\r?\n/).map((line) => {
    const value = line.trim();
    if (!value || value.startsWith("#")) return line;
    const resolved = new URL(value, manifestUrl).toString();
    return `/hls/${encodeURIComponent(channelId)}/segment/${issueToken(resolved)}`;
  }).join("\n");
}

async function fetchUpstream(url) {
  const response = await fetch(url, { redirect: "follow", signal: AbortSignal.timeout(20_000) });
  if (!response.ok) throw new Error(`upstream HTTP ${response.status}`);
  return response;
}

const server = createServer(async (request, response) => {
  const url = new URL(request.url || "/", `http://${request.headers.host || "localhost"}`);
  if (url.pathname === "/healthz") {
    return send(response, 200, JSON.stringify({ ok: true, engine_configured: Boolean(engineBase), channels: loadChannels().size }), "application/json");
  }
  if (url.pathname === "/playlist.m3u") {
    const base = publicBase || url.origin;
    const lines = ["#EXTM3U", "# Authorized P2P-to-HLS gateway. No arbitrary inputs."];
    for (const channel of loadChannels().values()) {
      lines.push(`#EXTINF:-1 tvg-id="${channel.id}" group-title="Authorized P2P",${channel.name}`);
      lines.push(`${base}/hls/${channel.id}/index.m3u8`);
    }
    return send(response, 200, `${lines.join("\n")}\n`, "application/x-mpegURL");
  }

  const match = url.pathname.match(/^\/hls\/([a-z0-9-]{2,64})\/(index\.m3u8|segment\/([a-f0-9]{32}))$/i);
  if (!match) return send(response, 404, "not found");
  const channels = loadChannels();
  const channel = channels.get(match[1]);
  if (!channel) return send(response, 404, "unknown authorized channel");
  if (!engineBase) return send(response, 503, "P2P engine is not configured");

  try {
    const upstreamUrl = match[2] === "index.m3u8"
      ? `${engineBase}/ace/manifest.m3u8?content_id=${encodeURIComponent(channel.contentId)}`
      : consumeToken(match[3]);
    if (!upstreamUrl) return send(response, 410, "expired segment reference");
    const upstream = await fetchUpstream(upstreamUrl);
    if (match[2] === "index.m3u8") {
      const body = rewriteManifest(await upstream.text(), upstream.url, channel.id);
      return send(response, 200, body, "application/vnd.apple.mpegurl");
    }
    response.writeHead(200, {
      "content-type": upstream.headers.get("content-type") || hlsType(upstream.url),
      "cache-control": "no-store",
      "access-control-allow-origin": "*"
    });
    if (!upstream.body) return response.end();
    const reader = upstream.body.getReader();
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      response.write(value);
    }
    response.end();
  } catch (error) {
    return send(response, 502, `gateway error: ${error.message}`);
  }
});

server.listen(port, "0.0.0.0", () => {
  console.log(`authorized P2P gateway listening on ${port}`);
});
