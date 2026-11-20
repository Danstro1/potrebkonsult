import { useState } from "react"
import AnswerCard from "./AnswerCard"
import type { Consultation } from "../types"

const example: Consultation = {
  id: "demo", question: "В магазине сказали, что без чека претензию не примут. Что делать?",
  answer: { refusal: false, text: "Укажите в претензии обстоятельства покупки. Отсутствие чека само по себе не служит основанием для отказа в требованиях по поводу недостатка товара [1].",
    sources: [{title: "Закон о защите прав потребителей · ст. 18, п. 5",
      excerpt: "Отсутствие у потребителя кассового или товарного чека либо иного документа, удостоверяющих факт и условия покупки товара, не является основанием для отказа в удовлетворении его требований."}] },
  helpful: null,
}

export default function Demo() {
  const [item, setItem] = useState(example)
  return <><h1 className="mb-5 text-3xl font-semibold">Пример консультации</h1>
    <AnswerCard item={item} busy={false} onVote={helpful => setItem({...item, helpful})}/></>
}
