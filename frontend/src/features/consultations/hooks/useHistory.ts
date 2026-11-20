import { useQuery } from "@tanstack/react-query"
import { request } from "../api/request"
import type { Consultation } from "../types"

export const historyKey = (username?: string) => ["consultations", username] as const

export function useHistory(username?: string) {
  return useQuery({
    queryKey: historyKey(username),
    queryFn: () => request<Consultation[]>("consultations"),
    enabled: Boolean(username),
  })
}
