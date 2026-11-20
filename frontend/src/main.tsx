import { createRoot } from "react-dom/client"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { BrowserRouter, Link, Route, Routes } from "react-router-dom"
import Workspace from "./features/consultations/components/Workspace"
import Demo from "./features/consultations/components/Demo"
import "./index.css"

const client = new QueryClient({defaultOptions: {queries: {retry: false}}})
createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={client}><BrowserRouter>
    <header className="border-b bg-white"><nav className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 p-5">
      <Link className="text-xl font-bold text-teal-900" to="/">ПотребКонсульт</Link>
      <Link className="text-teal-800 underline" to="/demo">Пример консультации</Link>
    </nav></header>
    <main className="mx-auto max-w-6xl px-4 py-8"><Routes><Route path="/" element={<Workspace/>}/>
      <Route path="/demo" element={<Demo/>}/></Routes></main>
    <footer className="mx-auto max-w-6xl px-4 pb-8 text-sm text-slate-600">Справочная информация по вопросам защиты прав потребителей.</footer>
  </BrowserRouter></QueryClientProvider>
)
