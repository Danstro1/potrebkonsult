import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ApiError, request } from "../api/request"
import { historyKey, useHistory } from "../hooks/useHistory"
import AnswerCard from "./AnswerCard"
import AuthForm from "./AuthForm"

export default function Workspace() {
  const [question, setQuestion] = useState("")
  const cache = useQueryClient()
  const me = useQuery({ queryKey: ["me"], queryFn: () => request<{username: string}>("auth/me"), retry: false })
  const history = useHistory(me.data?.username)
  const edit = useMutation({
    mutationFn: (op: {path: string; method: string; body?: unknown}) => request(op.path, op.method, op.body),
    onSuccess: async (_, op) => {
      if (op.path === "auth/logout") { setQuestion(""); cache.clear(); return }
      if (op.method === "POST") setQuestion("")
      await cache.invalidateQueries({ queryKey: historyKey(me.data?.username) })
    },
    onError: error => { if (error instanceof ApiError && error.status === 401) cache.clear() },
  })
  if (me.isPending) return <p role="status">Проверяем сессию…</p>
  if (me.error instanceof ApiError && me.error.status === 401) return <AuthForm/>
  if (me.error) return <p role="alert">{me.error.message} <button onClick={() => me.refetch()}>Повторить</button></p>
  return <div className="space-y-5">
    <header className="flex flex-wrap items-center justify-between gap-2"><h1 className="text-3xl font-semibold">Мои консультации</h1>
      <button disabled={edit.isPending} onClick={() => edit.mutate({path:"auth/logout", method:"POST"})}>Выйти · {me.data?.username}</button></header>
    <form className="space-y-3 rounded-xl border bg-white p-5" onSubmit={e => {
      e.preventDefault(); edit.mutate({path:"consultations", method:"POST", body:{question: question.trim()}})
    }}>
      <label className="block font-medium">Опишите вашу ситуацию<textarea className="mt-2" rows={3} value={question}
        onChange={e => setQuestion(e.target.value)} maxLength={2000} disabled={edit.isPending}
        placeholder="Что произошло и чего вы хотите добиться?"/></label>
      <button className="bg-teal-800 text-white" disabled={edit.isPending || question.trim().length < 10}>Получить консультацию</button>
      {edit.isPending && <span role="status" className="ml-3">Обрабатываем запрос…</span>}
    </form>
    {edit.error && <p role="alert">{edit.error.message}</p>}
    {history.isPending && <p>Загружаем историю…</p>}
    {history.error && <p role="alert">{history.error.message} <button onClick={() => history.refetch()}>Повторить</button></p>}
    {history.data?.length === 0 && <p>Здесь появится ваша первая консультация.</p>}
    {history.data?.map(item => <AnswerCard key={item.id} item={item} busy={edit.isPending}
      onVote={helpful => edit.mutate({path:"consultations/"+item.id, method:"PATCH", body:{helpful}})}
      onDelete={() => edit.mutate({path:"consultations/"+item.id, method:"DELETE"})}/>)}
  </div>
}
