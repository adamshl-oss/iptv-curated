# Authorized P2P gateway

This is a narrow HLS gateway for IPTVX. It is deliberately not a P2P search
engine, an open proxy, or a place to paste arbitrary magnet links.

An operator deploys an authorized Ace Stream Engine separately, sets
`ACE_ENGINE_BASE_URL` and the public HTTPS `PUBLIC_BASE_URL`, and adds only
channels for which they have distribution authority to
`config/authorized-channels.json`:

```json
{
  "channels": [
    {
      "id": "example-authorized-channel",
      "name": "Example Authorized Channel",
      "content_id": "operator-provided-content-id",
      "rights_attestation": "Written authorization on file"
    }
  ]
}
```

The service publishes `/playlist.m3u`, then rewrites the engine's HLS manifest
and segments behind short-lived gateway references. It does not accept arbitrary
input from IPTVX clients. A persistent VM/container platform is required; an
edge worker and GitHub Actions cannot host the long-lived P2P engine.
