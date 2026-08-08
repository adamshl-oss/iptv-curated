#!/usr/bin/env swift

import AVFoundation
import Foundation

struct ApplePlaybackPolicy {
    let duration: Double
    let sampleInterval: Double
    let maximumStartup: Double
    let minimumAdvancingRatio: Double
    let maximumTotalStall: Double
    let maximumSingleStall: Double
    let maximumStallEvents: Int
    let processGrace: Double
}

struct PlaybackMetrics {
    let startup: Double
    let observed: Double
    let advancing: Double
    let waiting: Double
    let stallEvents: Int
    let totalStall: Double
    let longestStall: Double
    let discontinuities: Int

    var advancingRatio: Double {
        observed > 0 ? advancing / observed : 0
    }
}

func fail(_ url: String, _ reason: String) -> Never {
    fputs("FAIL|\(url)|\(reason)\n", stderr)
    exit(1)
}

func number(_ object: [String: Any], _ key: String) -> Double? {
    (object[key] as? NSNumber)?.doubleValue
}

func loadPolicy(_ path: String, url: String) -> ApplePlaybackPolicy {
    do {
        let data = try Data(contentsOf: URL(fileURLWithPath: path))
        guard
            let document = try JSONSerialization.jsonObject(with: data)
                as? [String: Any],
            let policy = document["apple_playback"] as? [String: Any],
            policy["enabled"] as? Bool == true,
            let duration = number(policy, "duration_seconds"),
            let sampleInterval = number(policy, "sample_interval_seconds"),
            let maximumStartup = number(policy, "maximum_startup_seconds"),
            let minimumAdvancingRatio = number(policy, "minimum_advancing_ratio"),
            let maximumTotalStall = number(policy, "maximum_total_stall_seconds"),
            let maximumSingleStall = number(policy, "maximum_single_stall_seconds"),
            let maximumStallEvents = number(policy, "maximum_stall_events"),
            let processGrace = number(policy, "process_grace_seconds")
        else {
            fail(url, "invalid_apple_playback_policy")
        }
        return ApplePlaybackPolicy(
            duration: duration,
            sampleInterval: sampleInterval,
            maximumStartup: maximumStartup,
            minimumAdvancingRatio: minimumAdvancingRatio,
            maximumTotalStall: maximumTotalStall,
            maximumSingleStall: maximumSingleStall,
            maximumStallEvents: Int(maximumStallEvents),
            processGrace: processGrace
        )
    } catch {
        fail(url, "policy_error:\(error.localizedDescription)")
    }
}

func summary(_ metrics: PlaybackMetrics) -> String {
    String(
        format: "startup=%.1fs; observed=%.1fs; advancing=%.1fs/%.3f; waiting=%.1fs; stalls=%d/%.1fs/max%.1fs; discontinuities=%d",
        metrics.startup,
        metrics.observed,
        metrics.advancing,
        metrics.advancingRatio,
        metrics.waiting,
        metrics.stallEvents,
        metrics.totalStall,
        metrics.longestStall,
        metrics.discontinuities
    )
}

guard CommandLine.arguments.count == 3 else {
    fputs("usage: apple_avplayer_check.swift <hls-url> <policy-json>\n", stderr)
    exit(2)
}

let urlString = CommandLine.arguments[1]
guard let url = URL(string: urlString) else {
    fail(urlString, "invalid_url")
}
let policy = loadPolicy(CommandLine.arguments[2], url: urlString)

// Concurrent command-line AVPlayer processes otherwise race while creating a
// shared on-disk URL cache. IPTVX does not need that cache for live playback.
URLCache.shared = URLCache(memoryCapacity: 0, diskCapacity: 0, diskPath: nil)

let player = AVPlayer(url: url)
player.automaticallyWaitsToMinimizeStalling = true

let processStarted = Date()
let deadline = processStarted.addingTimeInterval(
    policy.maximumStartup + policy.duration + policy.processGrace
)
var lastSample = processStarted
var lastMediaTime: Double?
var firstAdvanceAt: Date?
var observationStartedAt: Date?
var advancingSeconds = 0.0
var waitingSeconds = 0.0
var totalStallSeconds = 0.0
var longestStallSeconds = 0.0
var currentStallSeconds = 0.0
var stallEvents = 0
var discontinuities = 0
var inStall = false

player.play()

while Date() < deadline {
    RunLoop.current.run(
        until: Date().addingTimeInterval(policy.sampleInterval)
    )
    let now = Date()
    let wallDelta = max(0, now.timeIntervalSince(lastSample))
    lastSample = now

    if let error = player.currentItem?.error {
        fail(urlString, "player_error:\(error.localizedDescription)")
    }
    if player.currentItem?.status == .failed {
        let detail = player.currentItem?.error?.localizedDescription
            ?? "item_failed"
        fail(urlString, detail)
    }

    let mediaTime = player.currentTime().seconds
    var normalAdvance = false
    if mediaTime.isFinite, let prior = lastMediaTime {
        let mediaDelta = mediaTime - prior
        let maximumNormalAdvance = max(2.0, wallDelta * 4.0)
        if mediaDelta >= 0.04, mediaDelta <= maximumNormalAdvance {
            normalAdvance = true
        } else if mediaDelta > maximumNormalAdvance || mediaDelta < -0.25 {
            // A live-window seek or discontinuity cannot be counted as smooth
            // playback. Ignore the jump and require subsequent real advance.
            discontinuities += 1
        }
    }
    if mediaTime.isFinite {
        lastMediaTime = mediaTime
    }

    if normalAdvance, firstAdvanceAt == nil {
        firstAdvanceAt = now
        observationStartedAt = now.addingTimeInterval(-wallDelta)
    }

    guard let observationStartedAt else {
        if now.timeIntervalSince(processStarted) > policy.maximumStartup {
            let reason = player.reasonForWaitingToPlay?.rawValue
                ?? "no_media_advance"
            fail(
                urlString,
                String(format: "startup_timeout_%.1fs:%@", policy.maximumStartup, reason)
            )
        }
        continue
    }

    if player.timeControlStatus == .waitingToPlayAtSpecifiedRate {
        waitingSeconds += wallDelta
    }

    if normalAdvance, player.timeControlStatus == .playing {
        advancingSeconds += wallDelta
        if inStall {
            longestStallSeconds = max(longestStallSeconds, currentStallSeconds)
            currentStallSeconds = 0
            inStall = false
        }
    } else {
        if !inStall {
            stallEvents += 1
            inStall = true
        }
        currentStallSeconds += wallDelta
        totalStallSeconds += wallDelta
    }

    let observed = now.timeIntervalSince(observationStartedAt)
    if observed < policy.duration {
        continue
    }

    if inStall {
        longestStallSeconds = max(longestStallSeconds, currentStallSeconds)
    }
    let metrics = PlaybackMetrics(
        startup: (firstAdvanceAt ?? now).timeIntervalSince(processStarted),
        observed: observed,
        advancing: advancingSeconds,
        waiting: waitingSeconds,
        stallEvents: stallEvents,
        totalStall: totalStallSeconds,
        longestStall: longestStallSeconds,
        discontinuities: discontinuities
    )
    let metricsSummary = summary(metrics)
    var failures: [String] = []
    if metrics.startup > policy.maximumStartup {
        failures.append(String(format: "startup_%.1fs", metrics.startup))
    }
    if metrics.advancingRatio < policy.minimumAdvancingRatio {
        failures.append(String(format: "advance_ratio_%.3f", metrics.advancingRatio))
    }
    if metrics.totalStall > policy.maximumTotalStall {
        failures.append(String(format: "total_stall_%.1fs", metrics.totalStall))
    }
    if metrics.longestStall > policy.maximumSingleStall {
        failures.append(String(format: "long_stall_%.1fs", metrics.longestStall))
    }
    if metrics.stallEvents > policy.maximumStallEvents {
        failures.append("stall_events_\(metrics.stallEvents)")
    }
    if failures.isEmpty {
        print("PASS|\(urlString)|apple_ok; \(metricsSummary)")
        exit(0)
    }
    fail(urlString, "\(failures.joined(separator: ",")); \(metricsSummary)")
}

let reason = player.reasonForWaitingToPlay?.rawValue ?? "deadline"
fail(urlString, "process_timeout:\(reason)")
