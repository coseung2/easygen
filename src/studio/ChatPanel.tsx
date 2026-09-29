// 우측 패널 대화 탭: 프로젝트/노드 대화를 저장하고 ChatGPT 계정으로 이어간다.
import React from 'react'
import { Send, Sparkles, Square } from 'lucide-react'
import { isTauri } from '../lib/tauri'
import {
  appendMessage,
  ensureChatSession,
  ensureConversation,
  extractApplyBlock,
  interruptChat,
  listMessages,
  sendChatMessage,
  type ConversationRow,
  type MessageRow,
} from '../lib/chat'
import { listChatGptAccounts, type ChatGptAccount } from '../lib/chatgpt'
import { findDelivery, shouldBindConversation, shouldStartStream } from './chatDelivery'
import { useStudioStore } from './store'

export function ChatPanel({ onNotice }: { onNotice: (message: string) => void }) {
  const projectId = useStudioStore((state) => state.projectId)
  const selection = useStudioStore((state) => state.selection)
  const selectedNode = useStudioStore((state) => (
    state.selection?.type === 'node'
      ? state.doc.nodes.find((node) => node.id === state.selection!.id)
      : undefined
  ))
  const chatStream = useStudioStore((state) => state.chatStream)
  const [accounts, setAccounts] = React.useState<ChatGptAccount[]>([])
  const [accountId, setAccountId] = React.useState('')
  const [conversation, setConversation] = React.useState<ConversationRow | null>(null)
  const [messages, setMessages] = React.useState<MessageRow[]>([])
  const [draft, setDraft] = React.useState('')
  const [attached, setAttached] = React.useState<Array<{ id: string; name: string; kind: string; path: string }>>([])
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState('')
  const assets = useStudioStore((state) => state.doc.assets)
  const nodeId = selection?.type === 'node' ? selection.id : null

  React.useEffect(() => {
    if (!isTauri) return
    void listChatGptAccounts()
      .then((rows) => {
        setAccounts(rows)
        setAccountId((current) => current || rows[0]?.id || '')
      })
      .catch(() => undefined)
  }, [])

  // 대상(프로젝트 또는 노드)이 바뀌면 그 대화를 연다.
  React.useEffect(() => {
    if (!projectId || !isTauri) return
    let cancelled = false
    void ensureConversation(projectId, nodeId)
      .then((row) => {
        if (cancelled) return null
        setConversation(row)
        return listMessages(row.id)
      })
      .then((rows) => {
        if (!cancelled && rows) setMessages(rows)
      })
      .catch((loadError) => {
        if (!cancelled) setError(String(loadError))
      })
    return () => { cancelled = true }
  }, [projectId, nodeId])

  // 턴이 끝나면 어시스턴트 메시지를 저장하고 스트림을 비운다.
  const streamedText = chatStream.text
  const streamStatus = chatStream.status
  React.useEffect(() => {
    // 스트림이 끝났으면(완료·중단) 받은 텍스트를 대화에 남긴다.
    if (streamStatus === 'streaming' || streamStatus === 'idle') return
    // 응답이 도착한 대화에 남긴다. 그 사이 다른 노드를 골라도 섞이지 않는다.
    const targetId = chatStream.conversationId || conversation?.id || ''
    if (!targetId) return
    const content = streamedText.trim()
    useStudioStore.getState().setChatStream({ threadId: '', turnId: '', text: '', status: 'idle' })
    if (!content) return
    void appendMessage(targetId, 'assistant', content, {
      threadId: chatStream.threadId,
      turnId: chatStream.turnId,
    })
      .then((row) => setMessages((current) => (
        conversation?.id === targetId && !current.some((item) => item.id === row.id)
          ? [...current, row]
          : current
      )))
      .catch(() => undefined)
  }, [streamStatus, streamedText, conversation, chatStream.conversationId, chatStream.threadId, chatStream.turnId])

  const send = async () => {
    const content = draft.trim()
    if (!content || !conversation) return
    // 첨부는 이미 프로젝트 소재다. 대화는 그 소재를 참조만 하고 새로 복사하지 않는다.
    const attachments = attached.filter((item) => item.path)
    setBusy(true)
    setError('')
    const conversationId = conversation.id
    // 전송 전에 대화 귀속을 잡아 둔다. 응답 델타가 전송보다 먼저 도착해도
    // 그 답변이 이 대화에 남는다. 아직 반영하지 않은 완료 응답은 건드리지 않는다.
    {
      const store = useStudioStore.getState()
      if (shouldBindConversation(store.chatStream.status)) {
        store.setChatStream({
          conversationId,
          threadId: '',
          turnId: '',
          text: '',
          status: 'idle',
        })
      }
    }
    // 전송을 먼저 시도해 어떤 첨부가 실제로 전달됐는지 받는다. 화면에는
    // 실제로 전달된 것과 이름만 전달된 것을 구분해서 남긴다.
    let turn: Awaited<ReturnType<typeof sendChatMessage>> | null = null
    let sendError = ''
    try {
      if (!accountId) throw new Error('ChatGPT 계정을 연결 관리 화면에서 먼저 로그인하세요.')
      await ensureChatSession(accountId, conversationId)
      turn = await sendChatMessage(
        accountId,
        content,
        conversationId,
        attachments.map((item) => ({ path: item.path, name: item.name, kind: item.kind })),
      )
    } catch (error) {
      sendError = String(error)
    }
    const delivery = turn
      ? turn.attachments
      : attachments.map((item) => ({
        path: item.path,
        name: item.name,
        delivered: false,
        note: sendError ? '전송 실패' : '전달되지 않음',
      }))
    try {
      const stored = await appendMessage(conversationId, 'user', content, {
        attachments: attachments.map((item) => ({
          assetId: item.id,
          path: item.path,
          name: item.name,
          kind: item.kind,
        })),
        delivery,
      })
      setMessages((current) => [...current, stored])
      setDraft('')
      setAttached([])
    } catch (storeError) {
      setError(String(storeError))
      setBusy(false)
      return
    }
    if (turn) {
      const store = useStudioStore.getState()
      // 전송이 끝나기 전에 델타나 완료가 먼저 도착했을 수 있다. 그때는 화면이
      // 이미 그 턴을 따라갔거나 이미 끝난 턴이므로 빈 텍스트·streaming으로
      // 되돌리지 않는다.
      if (shouldStartStream(store.chatStream.turnId, store.lastFinishedTurnId, turn.turnId)) {
        store.setChatStream({
          conversationId,
          threadId: turn.threadId,
          turnId: turn.turnId ?? '',
          text: '',
          status: 'streaming',
        })
      }
    } else {
      setError(sendError)
    }
    setBusy(false)
  }

  const stop = async () => {
    if (!chatStream.turnId) return
    try {
      await interruptChat(accountId, chatStream.threadId, chatStream.turnId)
      useStudioStore.getState().finishChatTurn(chatStream.threadId, chatStream.turnId, 'interrupted')
    } catch (stopError) {
      setError(String(stopError))
    }
  }

  const applyPatch = (raw: string) => {
    const block = extractApplyBlock(raw)
    if (!block) return
    if (!selectedNode) {
      onNotice('노드를 선택한 뒤 반영하세요.')
      return
    }
    const patch = block.patch
    const update: { title?: string; config?: Record<string, unknown> } = {}
    if (typeof patch.title === 'string') update.title = patch.title
    if (patch.config && typeof patch.config === 'object') update.config = patch.config as Record<string, unknown>
    if (Object.keys(update).length === 0) {
      onNotice('반영할 필드가 없습니다.')
      return
    }
    useStudioStore.getState().updateNode(selectedNode.id, update as never)
    onNotice(`${selectedNode.title} 노드에 반영했습니다. 되돌리기로 취소할 수 있습니다.`)
  }

  const target = selectedNode ? `노드 · ${selectedNode.title}` : '프로젝트 전체'

  return (
    <div className="chat-panel">
      <div className="chat-head">
        <span className="section-kicker"><Sparkles size={12} /> 대화</span>
        <small>{target}</small>
      </div>
      <label className="field-label chat-account">
        ChatGPT 계정
        <select value={accountId} onChange={(event) => setAccountId(event.target.value)}>
          <option value="">{accounts.length === 0 ? '연결된 계정 없음 (연결 관리)' : '계정 선택…'}</option>
          {accounts.map((account) => (
            <option key={account.id} value={account.id}>
              {account.email ?? account.id}{account.status === 'ok' ? '' : ' (재로그인 필요)'}
            </option>
          ))}
        </select>
      </label>

      <div className="chat-log">
        {messages.length === 0 && !chatStream.text && (
          <p className="dim">대화 없음</p>
        )}
        {messages.map((message) => (
          <div className={`chat-bubble ${message.role}`} key={message.id}>
            <span className="chat-role">{message.role === 'user' ? '나' : message.role === 'assistant' ? 'AI' : message.role}</span>
            <p>{message.content}</p>
            {Array.isArray(message.meta.attachments) && (message.meta.attachments as Array<{ name?: string }>).length > 0 && (
              <div className="chat-attachments">
                {(message.meta.attachments as Array<{ name?: string; path?: string }>).map((item, index) => {
                  // 실제 전달 여부를 구분한다. 이름만 전달된 소재를 이미지·오디오를
                  // 보낸 것처럼 표시하지 않는다. 같은 이름의 소재가 둘 이상이면
                  // 경로로 각각의 결과를 맞춘다.
                  const entries = Array.isArray(message.meta.delivery)
                    ? (message.meta.delivery as Array<{
                      path?: string
                      name?: string
                      delivered?: boolean
                      note?: string | null
                    }>)
                    : []
                  const matched = findDelivery(entries, item)
                  const note = matched && matched.delivered === false ? (matched.note || '전달되지 않음') : ''
                  return (
                    <span
                      className={note ? 'chat-attachment undelivered' : 'chat-attachment'}
                      key={`${message.id}-${index}`}
                      title={note || undefined}
                    >
                      {item.name ?? '소재'}{note ? ` · ${note}` : ''}
                    </span>
                  )
                })}
              </div>
            )}
            {message.role === 'assistant' && extractApplyBlock(message.content) && selectedNode && (
              <button className="secondary-action small" onClick={() => applyPatch(message.content)}>노드에 반영</button>
            )}
          </div>
        ))}
        {chatStream.text && (
          <div className="chat-bubble assistant streaming">
            <span className="chat-role">AI</span>
            <p>{chatStream.text}</p>
            {chatStream.status !== 'streaming' && extractApplyBlock(chatStream.text) && selectedNode && (
              <button className="secondary-action small" onClick={() => applyPatch(chatStream.text)}>노드에 반영</button>
            )}
          </div>
        )}
      </div>

      {error && <p className="inline-warn">{error}</p>}
      <div className="chat-compose">
        <div className="chat-attach-row">
          <select
            className="chat-attach-pick"
            value=""
            aria-label="소재 첨부"
            onChange={(event) => {
              const asset = assets.find((item) => item.id === event.target.value)
              if (!asset) return
              setAttached((current) => (
                current.some((item) => item.id === asset.id)
                  ? current
                  : [...current, { id: asset.id, name: asset.name, kind: asset.kind, path: asset.storedPath }]
              ))
            }}
          >
            <option value="">소재 첨부…</option>
            {assets.map((asset) => (
              <option key={asset.id} value={asset.id}>
                {asset.kind === 'image' ? '이미지' : asset.kind === 'video' ? '영상' : asset.kind === 'audio' ? '오디오' : '파일'} · {asset.name}
              </option>
            ))}
          </select>
          {attached.map((item) => (
            <span className="chat-attachment" key={item.id}>
              {item.name}
              <button
                aria-label={`${item.name} 첨부 해제`}
                onClick={() => setAttached((current) => current.filter((entry) => entry.id !== item.id))}
              >
                ×
              </button>
            </span>
          ))}
        </div>
        <textarea
          rows={3}
          value={draft}
          placeholder={selectedNode ? '이 노드에 대한 요청을 적으세요.' : '프로젝트 전체 요청을 적으세요.'}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              void send()
            }
          }}
        />
        <div className="chat-actions">
          {!isTauri && <span className="inline-warn">Tauri 앱 필요</span>}
          {chatStream.status === 'streaming' ? (
            <button className="secondary-action small" onClick={() => void stop()}>
              <Square size={12} />
              중단
            </button>
          ) : (
            <button className="primary-action small" disabled={busy || !draft.trim() || !isTauri} onClick={() => void send()}>
              <Send size={13} />
              전송
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
