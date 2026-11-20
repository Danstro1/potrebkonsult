import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { request } from "../api/request"

export default function AuthForm() {
  const [register, setRegister] = useState(false)
  const cache = useQueryClient()
  const auth = useMutation({
    mutationFn: (values: {username: string; password: string}) =>
      request<{username: string}>("auth/" + (register ? "register" : "login"), "POST", values),
    onSuccess: identity => cache.setQueryData(["me"], identity),
  })
  return <form className="mx-auto max-w-md space-y-4 rounded-xl border bg-white p-7" onSubmit={e => {
    e.preventDefault()
    const data = new FormData(e.currentTarget)
    auth.mutate({ username: String(data.get("username")), password: String(data.get("password")) })
  }}>
    <h1 className="text-2xl font-semibold">{register ? "Регистрация" : "Вход в личный кабинет"}</h1>
    <label className="block">Имя пользователя<input name="username" required pattern="[A-Za-z0-9_\-]{3,64}" autoComplete="username"/></label>
    <p className="text-sm">От 3 до 64 латинских букв, цифр, дефисов или подчёркиваний.</p>
    <label className="block">Пароль<input name="password" type="password" required minLength={10} maxLength={128} autoComplete={register ? "new-password" : "current-password"}/></label>
    {register && <p className="text-sm">Минимум 10 символов.</p>}
    {auth.error && <p role="alert">{auth.error.message}</p>}
    <button disabled={auth.isPending} className="bg-teal-800 text-white">{register ? "Зарегистрироваться" : "Войти"}</button>
    <button disabled={auth.isPending} type="button" onClick={() => {auth.reset(); setRegister(!register)}}>{register ? "Уже есть аккаунт" : "Создать аккаунт"}</button>
  </form>
}
