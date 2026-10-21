import Vision
import Cocoa

guard CommandLine.arguments.count > 1 else {
    fputs("Usage: ocr <image-path>\n", stderr)
    exit(1)
}

let path = CommandLine.arguments[1]
let imgURL = URL(fileURLWithPath: path)
guard let img = NSImage(contentsOf: imgURL),
      let tiff = img.tiffRepresentation,
      let ci = CIImage(data: tiff) else {
    fputs("Failed to load image: \(path)\n", stderr)
    exit(1)
}

let req = VNRecognizeTextRequest { req, err in
    let observations = req.results as? [VNRecognizedTextObservation] ?? []
    for obs in observations {
        if let top = obs.topCandidates(1).first {
            print(top.string)
        }
    }
}
req.recognitionLevel = .accurate
let handler = VNImageRequestHandler(ciImage: ci, options: [:])
try? handler.perform([req])
