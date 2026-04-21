export interface OCRWord {
  text: string
  bounding_box: [[number, number], [number, number], [number, number], [number, number]]
  confidence: number
}

export interface OCRResult {
  full_text: string
  words: OCRWord[]
  page_count: number
}
