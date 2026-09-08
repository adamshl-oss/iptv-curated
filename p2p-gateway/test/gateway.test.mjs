import assert from "node:assert/strict";
import { mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawn } from "node:child_process";
import test from "node:test";

const root = new URL("..", import.meta.url);

async function start(config) {
  const directory = await mkdtemp(join(tmpdir(), "iptvx-p2p-test-"));
  const configPath = join(directory, "channels.json");
  await writeFile(configPath, JSON.stringify(config));
  const port = 19000 + Math.floor(Math.random() * 1000);
  const child = spawn("node", ["src/server.mjs"], {
    cwd: root,
    env: {
      ...process.env,
      PORT: String(port),
      ACE_ENGINE_BASE_URL: "https://engine.example.test",
      PUBLIC_BASE_URL: "https://gateway.example.test",
      CHANNELS_FILE: configPath
    },
    stdio: "ignore"
  });
  const base = `http://127.0.0.1:${port}`;
  for (let attempt = 0; attempt < 30; attempt += 1) {
    try {
      if ((await fetch(`${base}/healthz`)).ok) return { base, child };
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  child.kill();
  throw new Error("gateway did not start");
}

test("empty configuration publishes no P2P inputs", async () => {
  const gateway = await start({ channels: [] });
  try {
    const health = await (await fetch(`${gateway.base}/healthz`)).json();
    assert.equal(health.channels, 0);
    const playlist = await (await fetch(`${gateway.base}/playlist.m3u`)).text();
    assert.match(playlist, /^#EXTM3U/m);
    assert.doesNotMatch(playlist, /#EXTINF/);
    assert.equal((await fetch(`${gateway.base}/hls/unknown/index.m3u8`)).status, 404);
  } finally {
    gateway.child.kill();
  }
});

test("only attested configured channels appear in the playlist", async () => {
  const gateway = await start({
    channels: [
      {
        id: "licensed-demo",
        name: "Licensed Demo",
        content_id: "operator-owned-content-id",
        rights_attestation: "Test distribution authorization"
      },
      { id: "unapproved", content_id: "ignored" }
    ]
  });
  try {
    const playlist = await (await fetch(`${gateway.base}/playlist.m3u`)).text();
    assert.match(playlist, /Licensed Demo/);
    assert.match(playlist, /https:\/\/gateway\.example\.test\/hls\/licensed-demo\/index\.m3u8/);
    assert.doesNotMatch(playlist, /unapproved/);
  } finally {
    gateway.child.kill();
  }
});
