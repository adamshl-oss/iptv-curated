#!/usr/bin/env swift

import AVFoundation
import Foundation

guard CommandLine.arguments.count >= 2,
      let url = URL(string: CommandLine.arguments[1]) else {
    fputs("usage: apple_avplayer_check.swift <hls-url> [seconds]\n", stderr)
    exit(2)
}

let requiredAdvance = CommandLine.arguments.count >= 3
    ? Double(CommandLine.arguments[2]) ?? 15
    : 15
let deadline = Date().addingTimeInterval(max(40, requiredAdvance + 25))
let player = AVPlayer(url: url)
var firstTime: Double?
var lastTime: Double?
var playingSamples = 0

player.play()
while Date() < deadline {
    RunLoop.current.run(until: Date().addingTimeInterval(1))
    if let error = player.currentItem?.error {
        fputs("FAIL|\(url)|\(error.localizedDescription)\n", stderr)
        exit(1)
    }
    let seconds = player.currentTime().seconds
    if seconds.isFinite {
        firstTime = firstTime ?? seconds
        lastTime = seconds
    }
    if player.timeControlStatus == .playing {
        playingSamples += 1
    }
    if let firstTime, let lastTime,
       lastTime - firstTime >= requiredAdvance,
       playingSamples >= Int(requiredAdvance) {
        print(
            "PASS|\(url)|advanced=\(String(format: "%.1f", lastTime - firstTime))s"
        )
        exit(0)
    }
}

let advance = (lastTime ?? 0) - (firstTime ?? 0)
let reason = player.reasonForWaitingToPlay?.rawValue ?? "no sustained playback"
fputs(
    "FAIL|\(url)|advanced=\(String(format: "%.1f", advance))s|\(reason)\n",
    stderr
)
exit(1)
