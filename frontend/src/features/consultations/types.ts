export interface Consultation {
  id: string
  question: string
  answer: { text: string; refusal: boolean; sources: { title: string; excerpt: string }[] }
  helpful: boolean | null
}
