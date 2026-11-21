// macOS Vision OCR：对目录下 PNG 逐张识别，输出 <name>.json（行文本+归一化位置）。
// 用法: swiftc -O ocr_vision.swift -o ocr_vision && ./ocr_vision <pages_dir>
import Foundation
import Vision
import AppKit

let dir = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "."
let fm = FileManager.default
let files = (try! fm.contentsOfDirectory(atPath: dir)).filter { $0.hasSuffix(".png") }.sorted()
let files2 = CommandLine.arguments.count > 2 && CommandLine.arguments[2] == "rev" ? files.reversed() : files
var done = 0
for f in files2 {
    let out = (dir as NSString).appendingPathComponent(f.replacingOccurrences(of: ".png", with: ".json"))
    if fm.fileExists(atPath: out) { continue }
    let url = URL(fileURLWithPath: (dir as NSString).appendingPathComponent(f))
    guard let img = NSImage(contentsOf: url), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.recognitionLanguages = ["zh-Hans", "en-US"]
    req.usesLanguageCorrection = true
    let h = VNImageRequestHandler(cgImage: cg, options: [:])
    do { try h.perform([req]) } catch { fputs("fail \(f): \(error)\n", stderr); continue }
    var lines: [[String: Any]] = []
    for o in (req.results ?? []) {
        guard let c = o.topCandidates(1).first else { continue }
        let b = o.boundingBox
        lines.append(["t": c.string, "x": b.minX, "y": b.minY, "w": b.width, "h": b.height, "c": c.confidence])
    }
    let data = try! JSONSerialization.data(withJSONObject: lines, options: [])
    try! data.write(to: URL(fileURLWithPath: out))
    done += 1
    if done % 10 == 0 { print("ocr \(done)/\(files.count)"); fflush(stdout) }
}
print("done \(done)")
