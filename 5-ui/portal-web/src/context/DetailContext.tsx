import React, { createContext, useCallback, useContext, useState } from 'react'

export type DetailKind = 'service' | 'job' | 'pipeline' | 'schema' | 'agent' | 'tenant' | 'connector' | 'scraper' | 'topic' | 'generic'

export type DetailPayload = {
  title: string
  subtitle?: string
  kind: DetailKind
  data?: Record<string, unknown>
  serviceKey?: string
  logName?: string
  healthUrl?: string
}

type DetailContextValue = {
  detail: DetailPayload | null
  openDetail: (payload: DetailPayload) => void
  closeDetail: () => void
}

const DetailContext = createContext<DetailContextValue | null>(null)

export function DetailProvider({ children }: { children: React.ReactNode }) {
  const [detail, setDetail] = useState<DetailPayload | null>(null)
  const openDetail = useCallback((payload: DetailPayload) => setDetail(payload), [])
  const closeDetail = useCallback(() => setDetail(null), [])
  return (
    <DetailContext.Provider value={{ detail, openDetail, closeDetail }}>
      {children}
    </DetailContext.Provider>
  )
}

export function useDetail() {
  const ctx = useContext(DetailContext)
  if (!ctx) throw new Error('useDetail must be used within DetailProvider')
  return ctx
}
