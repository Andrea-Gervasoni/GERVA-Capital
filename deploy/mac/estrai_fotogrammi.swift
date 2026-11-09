// Estrae fotogrammi da un video, senza installare nulla (usa solo quello che il Mac ha gia').
//
// Uso:   swift deploy/mac/estrai_fotogrammi.swift "/percorso/del video.MP4" ~/Desktop/fotogrammi [secondi] [massimo]
//   secondi = ogni quanti secondi un fotogramma (predefinito 10).
//   massimo = quante immagini al massimo (predefinito 40): se il video e' lungo il passo cresce da solo per restare sotto questo numero.
//   Esempio con tanti fotogrammi:  swift estrai_fotogrammi.swift "VIDEO" ~/Desktop/fotogrammi 2 200
// Le immagini (f_001.jpg, f_002.jpg...) si trascinano nella chat. Solo lettura sul video: non lo modifica.
import AVFoundation
import AppKit

let args = CommandLine.arguments
guard args.count >= 3 else {
    print("uso: swift estrai_fotogrammi.swift \"VIDEO\" CARTELLA [secondi] [massimo]")
    exit(1)
}
let url = URL(fileURLWithPath: (args[1] as NSString).expandingTildeInPath)
let outDir = URL(fileURLWithPath: (args[2] as NSString).expandingTildeInPath)
var step = args.count > 3 ? max(Double(args[3]) ?? 10, 0.5) : 10
let maxFrames = args.count > 4 ? max(Double(args[4]) ?? 40, 1) : 40

guard FileManager.default.fileExists(atPath: url.path) else {
    print("non trovo il file: \(url.path)")
    exit(1)
}
try FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)

let asset = AVURLAsset(url: url)
let duration = CMTimeGetSeconds(asset.duration)
guard duration.isFinite, duration > 0 else {
    print("non riesco a leggere la durata del video")
    exit(1)
}
step = max(step, duration / maxFrames)     // al massimo `maxFrames` fotogrammi

let gen = AVAssetImageGenerator(asset: asset)
gen.appliesPreferredTrackTransform = true  // rispetta la rotazione (video girati in verticale)
gen.maximumSize = CGSize(width: 1280, height: 1280)

var t = 0.0
var i = 1
while t < duration {
    let time = CMTime(seconds: t, preferredTimescale: 600)
    if let cg = try? gen.copyCGImage(at: time, actualTime: nil) {
        let rep = NSBitmapImageRep(cgImage: cg)
        if let data = rep.representation(using: .jpeg, properties: [.compressionFactor: 0.8]) {
            try data.write(to: outDir.appendingPathComponent(String(format: "f_%03d.jpg", i)))
        }
    }
    i += 1
    t += step
}
print("fatto: \(i - 1) fotogrammi (uno ogni \(String(format: "%.1f", step)) secondi, video di \(Int(duration)) secondi) in \(outDir.path)")
