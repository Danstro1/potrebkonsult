import { useState } from "react"
import type { Consultation } from "../types"

interface Props {
  item: Consultation
  busy: boolean
  onVote: (helpful: boolean) => void
  onDelete?: () => void
}

export default function AnswerCard({ item, busy, onVote, onDelete }: Props) {
  const [draft, setDraft] = useState(false)
  const [confirm, setConfirm] = useState(false)
  const [copied, setCopied] = useState("")
  const template = ["Кому: __________________", "От: __________________", "ПРЕТЕНЗИЯ",
    item.question, "Моё требование: __________________", "Приложения: __________________",
    "Дата и подпись: __________________"].join("\n\n")
  return <article className="rounded-xl border bg-white p-5 shadow-sm md:p-7">
    <h2 className="break-words text-xl font-semibold">{item.question}</h2>
    <div className="mt-5 grid gap-6 lg:grid-cols-[3fr_2fr]">
      <section><h3 className="font-semibold text-teal-800">{item.answer.refusal ? "Недостаточно оснований" : "Ответ ассистента"}</h3>
        <p className="mt-2 whitespace-pre-wrap break-words">{item.answer.text.split(/(\[\d+\])/g).map((part, index) => {
          const number = Number(part.slice(1, -1))
          if (!/^\[\d+\]$/.test(part) || !item.answer.sources[number - 1]) return part
          const id = `source-${item.id}-${number}`
          return <a key={index} href={`#${id}`} className="font-medium text-teal-800 underline"
            aria-label={`Открыть источник ${number}`} onClick={() => {
              const target = document.getElementById(id)
              if (target instanceof HTMLDetailsElement) target.open = true
            }}>{part}</a>
        })}</p></section>
      {item.answer.sources.length > 0 && <aside className="rounded-lg bg-teal-50 p-4">
        <h3 className="font-semibold">Источники</h3>
        {item.answer.sources.map((s, i) => <details key={i} id={`source-${item.id}-${i + 1}`} className="mt-3">
          <summary className="cursor-pointer text-teal-900">[{i + 1}] {s.title}</summary>
          <p className="mt-2 whitespace-pre-wrap text-sm">{s.excerpt}</p></details>)}</aside>}
    </div>
    <div className="mt-6 flex flex-wrap gap-2 border-t pt-3 text-sm">
      {!item.answer.refusal && <button onClick={() => setDraft(!draft)} aria-expanded={draft}>Черновик претензии</button>}
      {[true, false].map(value => <button key={String(value)} disabled={busy}
        className={item.helpful === value ? "bg-teal-100" : "bg-stone-100"}
        aria-pressed={item.helpful === value} onClick={() => onVote(value)}>
        {value ? "Полезно" : "Не помогло"}</button>)}
      {onDelete && <button disabled={busy} onClick={() => confirm ? onDelete() : setConfirm(true)}>
        {confirm ? "Подтвердить удаление" : "Удалить"}</button>}
      {confirm && <button onClick={() => setConfirm(false)}>Отмена</button>}
    </div>
    {draft && <section className="mt-4"><label>Текст для заполнения<textarea rows={9} readOnly value={template}/></label>
      <button onClick={async () => {
        try { await navigator.clipboard.writeText(template); setCopied("Скопировано") }
        catch { setCopied("Выделите текст и скопируйте вручную") }
      }}>Скопировать</button><span role="status">{copied}</span></section>}
  </article>
}
