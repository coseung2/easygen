// 대화(프로젝트/노드)와 Codex app-server 채팅 래퍼.
import { call, isTauri } from './tauri'

export type ConversationRow = {
  id: string
  projectId: string
  nodeId: string | null
  title: string | null
  createdAt: string
  updatedAt: string
}

export type MessageRow = {
  id: string
  conversationId: string
  role: string
  content: string
  meta: Record<string, unknown>
  createdAt: string
}

export type ChatSessionInfo = { accountId: string; threadId: string; binary: string }
/** What actually reached the model for one attachment. */
export type ChatAttachmentDelivery = {
  /** Asset path, so two attachments with the same name stay distinguishable. */
  path: string
  name: string
  delivered: boolean
  note: string | null
}
export type ChatTurnInfo = {
  threadId: string
  turnId: string | null
  attachments: ChatAttachmentDelivery[]
}

type StoredConversation = {
  id: string
  project_id: string
  node_id: string | null
  title: string | null
  created_at: string
  updated_at: string
}

type StoredMessage = {
  id: string
  conversation_id: string
  role: string
  content: string
  meta: Record<string, unknown> | null
  created_at: string
}

function mapConversation(row: StoredConversation): ConversationRow {
  return {
    id: row.id,
    projectId: row.project_id,
    nodeId: row.node_id,
    title: row.title,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  }
}

function mapMessage(row: StoredMessage): MessageRow {
  return {
    id: row.id,
    conversationId: row.conversation_id,
    role: row.role,
    content: row.content,
    meta: row.meta ?? {},
    createdAt: row.created_at,
  }
}

export async function ensureConversation(projectId: string, nodeId?: string | null): Promise<ConversationRow> {
  const row = await call<StoredConversation>('conversation_ensure', { projectId, nodeId: nodeId ?? null })
  return mapConversation(row)
}

export async function listConversations(projectId: string): Promise<ConversationRow[]> {
  if (!isTauri) return []
  const rows = await call<StoredConversation[]>('conversation_list', { projectId })
  return rows.map(mapConversation)
}

export async function listMessages(conversationId: string, limit = 200): Promise<MessageRow[]> {
  if (!isTauri) return []
  const rows = await call<StoredMessage[]>('message_list', { conversationId, limit })
  return rows.map(mapMessage)
}

export async function appendMessage(
  conversationId: string,
  role: 'user' | 'assistant' | 'system' | 'tool',
  content: string,
  meta?: Record<string, unknown>,
): Promise<MessageRow> {
  const row = await call<StoredMessage>('message_append', { conversationId, role, content, meta: meta ?? null })
  return mapMessage(row)
}

/** 대화(프로젝트·노드)마다 별도 모델 스레드를 연다. */
export async function ensureChatSession(accountId: string, conversationId?: string | null): Promise<ChatSessionInfo> {
  const row = await call<{ account_id: string; thread_id: string; binary: string }>('ai_chat_ensure_session', {
    accountId,
    conversationId: conversationId ?? null,
  })
  return { accountId: row.account_id, threadId: row.thread_id, binary: row.binary }
}

export async function sendChatMessage(
  accountId: string,
  message: string,
  conversationId?: string | null,
  attachments?: Array<{ path: string; name: string; kind?: string | null }>,
): Promise<ChatTurnInfo> {
  const row = await call<{
    thread_id: string
    turn_id: string | null
    attachments: Array<{ path: string; name: string; delivered: boolean; note: string | null }>
  }>('ai_chat_send', {
    accountId,
    message,
    conversationId: conversationId ?? null,
    attachments: attachments ?? null,
  })
  return { threadId: row.thread_id, turnId: row.turn_id, attachments: row.attachments ?? [] }
}

export async function interruptChat(accountId: string, threadId: string, turnId: string): Promise<void> {
  await call('ai_chat_interrupt', { accountId, threadId, turnId })
}

export type AiChatEvent = {
  method?: string
  params?: Record<string, unknown>
}

/** 어시스턴트 답변에서 노드 반영 블록을 찾는다. 사용자가 확인해야 적용된다. */
export function extractApplyBlock(content: string): { patch: Record<string, unknown>; raw: string } | null {
  const match = content.match(/```(?:json)?\s*([\s\S]*?)```/)
  if (!match) return null
  try {
    const parsed = JSON.parse(match[1]) as { apply?: Record<string, unknown> }
    if (parsed && typeof parsed === 'object' && parsed.apply) {
      return { patch: parsed.apply, raw: match[0] }
    }
  } catch {
    return null
  }
  return null
}
