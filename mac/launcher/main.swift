// koe mac launcher: the compiled shim that owns koe's TCC identity.
//
// macOS attributes permission grants to the "responsible process". A bare
// python spawned by a hotkey binder would pin the microphone grant to the
// binder (AeroSpace, skhd, a terminal, whatever) — coupling koe's permissions
// to whoever happens to invoke it. This signed bundle is the stable identity
// instead: it spawns the python pipeline as a child, and children inherit the
// bundle's grants (verified by probe on 2026-08-01: bundle -> uv -> python
// captured live audio with zero prompts, and a direct exec of the bundle
// binary still resolved to the bundle's TCC identity).
//
// Modes:
//   koe-launcher              spawn the koe pipeline, wait, propagate exit code
//   koe-launcher --register   one-shot: request microphone + post-event (paste)
//                             permission under koe's identity, report, exit
//
// Rebinding the hotkey to a different binder never re-prompts: the grants
// live on this bundle, not on the binder.

import AVFoundation
import CoreGraphics
import Foundation

let koeBinary = FileManager.default.homeDirectoryForCurrentUser.path
    + "/Code/s2bomb/koe/.venv/bin/koe"

func log(_ message: String) {
    FileHandle.standardError.write(("koe-launcher: " + message + "\n").data(using: .utf8)!)
}

if CommandLine.arguments.contains("--register") {
    let semaphore = DispatchSemaphore(value: 0)
    var microphoneGranted = false
    AVCaptureDevice.requestAccess(for: .audio) { granted in
        microphoneGranted = granted
        semaphore.signal()
    }
    semaphore.wait()
    let postEventGranted = CGRequestPostEventAccess()

    print("microphone:  " + (microphoneGranted ? "granted" : "DENIED"))
    print("paste (post-event): " + (postEventGranted
        ? "granted"
        : "not yet granted — System Settings → Privacy & Security → Accessibility → enable koe"))
    exit(microphoneGranted ? 0 : 1)
}

let child = Process()
child.executableURL = URL(fileURLWithPath: koeBinary)
do {
    try child.run()
} catch {
    log("cannot spawn \(koeBinary): \(error)")
    exit(2)
}
child.waitUntilExit()
exit(child.terminationStatus)
