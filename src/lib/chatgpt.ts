// ChatGPT OAuth 계정 관리 래퍼. 토큰은 백엔드 밖으로 나오지 않는다.

import { call, isTauri } from './tauri'

export type ChatGptAccount = {
  id: string
  provider: string
  accountId: string | null
  displayName: string | null
  email: string | null
  expiresAt: number | null
  status: string
  lastError: string | null
  credentialRef: string | null
  credentialVersion: number
  createdAt: string
  updatedAt: string
}

export type LoginAttemptState =
  | { state: 'pending' }
  | { state: 'completed'; account: ChatGptAccount }
  | { state: 'failed'; error: string }
  | { state: 'cancelled' }

export type LoginStart = {
  attemptId: string
  authUrl: string
  redirectUri: string
  /** Unix seconds when the attempt stops waiting for the browser callback. */
  expiresAt: number
}

type StoredAccount = {
  id: string
  provider: string
  account_id: string | null
  display_name: string | null
  email: string | null
  expires_at: number | null
  status: string
  last_error: string | null
  credential_ref: string | null
  credential_version: number
  created_at: string
  updated_at: string
}

function mapAccount(row: StoredAccount): ChatGptAccount {
  return {
    id: row.id,
    provider: row.provider,
    accountId: row.account_id,
    displayName: row.display_name,
    email: row.email,
    expiresAt: row.expires_at,
    status: row.status,
    lastError: row.last_error,
    credentialRef: row.credential_ref,
    credentialVersion: row.credential_version,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  }
}

function mapState(value: Record<string, unknown>): LoginAttemptState {
  const state = String(value.state ?? 'pending')
  if (state === 'completed') {
    return { state: 'completed', account: mapAccount(value.account as StoredAccount) }
  }
  if (state === 'failed') return { state: 'failed', error: String(value.error ?? '로그인 실패') }
  if (state === 'cancelled') return { state: 'cancelled' }
  return { state: 'pending' }
}

export async function startChatGptLogin(timeoutMs?: number): Promise<LoginStart> {
  const row = await call<{
    attempt_id: string
    auth_url: string
    redirect_uri: string
    expires_at: number
  }>('chatgpt_login_start', { timeoutMs: timeoutMs ?? null })
  return {
    attemptId: row.attempt_id,
    authUrl: row.auth_url,
    redirectUri: row.redirect_uri,
    expiresAt: row.expires_at,
  }
}

export async function loginStatus(attemptId: string): Promise<LoginAttemptState> {
  const row = await call<{ state: Record<string, unknown> }>('chatgpt_login_status', { attemptId })
  return mapState(row.state)
}

export async function cancelLogin(attemptId: string): Promise<void> {
  await call('chatgpt_login_cancel', { attemptId })
}

export async function listChatGptAccounts(): Promise<ChatGptAccount[]> {
  if (!isTauri) return []
  const rows = await call<StoredAccount[]>('chatgpt_accounts')
  return rows.map(mapAccount)
}

export async function logoutChatGpt(accountId: string): Promise<void> {
  await call('chatgpt_logout', { accountId })
}

export async function ensureFresh(accountId: string): Promise<ChatGptAccount> {
  const row = await call<StoredAccount>('chatgpt_ensure_fresh', { accountId })
  return mapAccount(row)
}
