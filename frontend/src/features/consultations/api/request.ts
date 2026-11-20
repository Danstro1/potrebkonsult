export class ApiError extends Error {
  constructor(readonly status: number, message: string) { super(message) }
}

export async function request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch("/api/" + path, {
    method, credentials: "same-origin",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  }).catch(() => { throw new Error("Не удалось подключиться к серверу.") })
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new ApiError(response.status, typeof data?.detail === "string" ? data.detail :
      response.status === 422 ? "Проверьте введённые данные." : "Ошибка сервера. Повторите позже.")
  }
  return response.status === 204 ? undefined : response.json()
}
