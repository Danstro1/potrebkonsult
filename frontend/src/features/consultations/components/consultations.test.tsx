import { afterEach, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import AnswerCard from "./AnswerCard"
import AuthForm from "./AuthForm"
import Demo from "./Demo"

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it("показывает раскрываемый источник и черновик", () => {
  render(<Demo/>)
  fireEvent.click(screen.getByRole("link", {name: "Открыть источник 1"}))
  expect(screen.getByText(/Отсутствие у потребителя/).closest("details")?.open).toBe(true)
  fireEvent.click(screen.getByText("Черновик претензии"))
  expect(screen.getByRole("textbox")).toHaveProperty("value", expect.stringContaining("ПРЕТЕНЗИЯ"))
})

it("отображает выбранную оценку", () => {
  render(<Demo/>)
  fireEvent.click(screen.getByText("Полезно"))
  expect(screen.getByText("Полезно").getAttribute("aria-pressed")).toBe("true")
})

it("при отказе показывает причину", () => {
  render(<AnswerCard item={{id:"1",question:"Можно уточнить?",helpful:null,
    answer:{refusal:true,text:"Нет контекста",sources:[]}}} busy={false} onVote={() => {}}/>)
  expect(screen.getByText("Нет контекста")).toBeTruthy()
  expect(screen.queryByText("Черновик претензии")).toBeNull()
})

it("показывает ошибку входа от API", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:"Неверное имя или пароль"}), {status:401})))
  render(<QueryClientProvider client={new QueryClient()}><AuthForm/></QueryClientProvider>)
  fireEvent.submit(screen.getByText("Войти").closest("form")!)
  expect((await screen.findByRole("alert")).textContent).toBe("Неверное имя или пароль")
})
