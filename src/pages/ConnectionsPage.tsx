// 연결 관리 화면: MCP 서버 등록, 연결 테스트, 도구 목록 확인.
import React from 'react'
import { Boxes, Cable, Play, Plus, RefreshCw, Trash2 } from 'lucide-react'
import { isTauri } from '../lib/tauri'
import { browserCapability, confirmProtectedAction } from '../ux/stageOne'
import {
  cancelLogin,
  ensureFresh,
  listChatGptAccounts,
  loginStatus,
  logoutChatGpt,
  startChatGptLogin,
  type ChatGptAccount,
  type LoginAttemptState,
} from '../lib/chatgpt'
import {
  CONNECTION_KIND_LABELS,
  CONNECTION_STATUS_LABELS,
  deleteConnection,
  listConnectionTools,
  listConnections,
  saveConnection,
  setConnectionEnabled,
  setConnectionToolEnabled,
  callConnectionTool,
  testConnection,
  type ConnectionRow,
  type ConnectionToolRow,
} from '../lib/connections'
import {
  WORKFLOW_STATUS_LABELS,
  deleteWorkflow,
  listWorkflows,
  saveWorkflow,
  type WorkflowRow,
} from '../lib/workflows'

const WORKFLOW_TOOL_OPTIONS = [
  { value: 'modal-h3', label: 'Modal H3 영상' },
  { value: 'yue2-music', label: 'YuE2 음악' },
]

export function ConnectionsPage() {
  const [connections, setConnections] = React.useState<ConnectionRow[]>([])
  const [tools, setTools] = React.useState<Record<string, ConnectionToolRow[]>>({})
  const [name, setName] = React.useState('')
  const [kind, setKind] = React.useState('mcp-stdio')
  const [command, setCommand] = React.useState('')
  const [argsText, setArgsText] = React.useState('')
  const [url, setUrl] = React.useState('')
  const [cwd, setCwd] = React.useState('')
  const [envText, setEnvText] = React.useState('')
  const [busy, setBusy] = React.useState('')
  const [error, setError] = React.useState('')
  const [notice, setNotice] = React.useState('')
  const [accounts, setAccounts] = React.useState<ChatGptAccount[]>([])
  const [attempt, setAttempt] = React.useState<{ id: string; authUrl: string; expiresAt: number } | null>(
    null,
  )
  const [attemptState, setAttemptState] = React.useState<LoginAttemptState | null>(null)
  const [clock, setClock] = React.useState(() => Date.now())
  const [workflows, setWorkflows] = React.useState<WorkflowRow[]>([])
  const [workflowName, setWorkflowName] = React.useState('')
  const [workflowTool, setWorkflowTool] = React.useState('modal-h3')
  const [workflowLocation, setWorkflowLocation] = React.useState('')
  const [workflowNotes, setWorkflowNotes] = React.useState('')
  const [section, setSection] = React.useState<'connections' | 'accounts' | 'workflows'>('connections')

  const refresh = React.useCallback(async () => {
    if (!isTauri) {
      setError('연결 관리는 Tauri 앱에서 동작합니다. 브라우저 미리보기에서는 표시만 확인할 수 있습니다.')
      return
    }
    try {
      setConnections(await listConnections())
    } catch (loadError) {
      setError(String(loadError))
    }
  }, [])

  React.useEffect(() => {
    void refresh()
  }, [refresh])

  const refreshWorkflows = React.useCallback(async () => {
    if (!isTauri) return
    try {
      setWorkflows(await listWorkflows())
    } catch (loadError) {
      setError(String(loadError))
    }
  }, [])

  React.useEffect(() => {
    void refreshWorkflows()
  }, [refreshWorkflows])

  const createWorkflow = async () => {
    if (!isTauri) return setError(browserCapability('callExternalService').reason)
    setError('')
    setNotice('')
    try {
      await saveWorkflow({
        name: workflowName.trim() || '새 워크플로',
        tool: workflowTool,
        location: workflowLocation.trim() || null,
        notes: workflowNotes.trim() || null,
      })
      setWorkflowName('')
      setWorkflowLocation('')
      setWorkflowNotes('')
      setNotice('워크플로를 등록했습니다. 등록만으로 실행 검증됨이 되지는 않습니다.')
      await refreshWorkflows()
    } catch (saveError) {
      setError(String(saveError))
    }
  }

  const removeWorkflow = async (workflow: WorkflowRow) => {
    if (!isTauri) return setError(browserCapability('persistProject').reason)
    if (!confirmProtectedAction(`“${workflow.name}” 워크플로 등록을 삭제합니다. 프로젝트의 실행 기록은 남지만 이 워크플로를 다시 선택하려면 등록해야 합니다.`)) return
    try {
      await deleteWorkflow(workflow.id)
      await refreshWorkflows()
    } catch (removeError) {
      setError(String(removeError))
    }
  }

  const refreshAccounts = React.useCallback(async () => {
    if (!isTauri) return
    try {
      setAccounts(await listChatGptAccounts())
    } catch (accountError) {
      setError(String(accountError))
    }
  }, [])

  React.useEffect(() => {
    void refreshAccounts()
  }, [refreshAccounts])

  // 진행 중인 로그인 시도는 완료·실패·취소까지 상태를 따라간다.
  React.useEffect(() => {
    if (!attempt) return
    let cancelled = false
    const timer = window.setInterval(() => {
      void loginStatus(attempt.id)
        .then((value) => {
          if (cancelled) return
          setAttemptState(value)
          if (value.state === 'completed') {
            setNotice(`ChatGPT 로그인 완료: ${value.account.email ?? value.account.id}`)
            setAttempt(null)
            void refreshAccounts()
          } else if (value.state === 'failed') {
            setError(value.error)
            setAttempt(null)
          } else if (value.state === 'cancelled') {
            setNotice('로그인을 취소했습니다.')
            setAttempt(null)
          }
        })
        .catch((statusError) => {
          if (!cancelled) setError(String(statusError))
        })
    }, 900)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [attempt, refreshAccounts])

  const startLogin = async () => {
    if (!isTauri) return setError(browserCapability('callExternalService').reason)
    setError('')
    setNotice('')
    try {
      const started = await startChatGptLogin()
      setAttempt({ id: started.attemptId, authUrl: started.authUrl, expiresAt: started.expiresAt })
      setAttemptState({ state: 'pending' })
      setNotice('브라우저에서 ChatGPT 로그인을 마치면 이 화면이 자동으로 갱신됩니다.')
    } catch (loginError) {
      setError(String(loginError))
    }
  }

  // 남은 시간을 보여 준다. 대기 중인 시도가 고정 콜백 포트를 계속 잡고 있으므로
  // 언제 끝나는지 확인할 수 있어야 한다.
  React.useEffect(() => {
    if (!attempt) return
    const timer = window.setInterval(() => setClock(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [attempt])
  const remainingSeconds = attempt
    ? Math.max(0, Math.ceil(attempt.expiresAt - clock / 1000))
    : 0
  const remainingLabel = `${Math.floor(remainingSeconds / 60)}:${String(remainingSeconds % 60).padStart(2, '0')}`

  const cancelAttempt = async () => {
    if (!attempt) return
    try {
      await cancelLogin(attempt.id)
    } catch (cancelError) {
      setError(String(cancelError))
    }
  }

  const refreshAccount = async (account: ChatGptAccount) => {
    if (!isTauri) return setError(browserCapability('callExternalService').reason)
    setError('')
    try {
      const updated = await ensureFresh(account.id)
      setNotice(`토큰을 확인했습니다: ${updated.displayName ?? updated.id} · 버전 ${updated.credentialVersion}`)
      await refreshAccounts()
    } catch (refreshError) {
      setError(String(refreshError))
      await refreshAccounts()
    }
  }

  const removeAccount = async (account: ChatGptAccount) => {
    if (!isTauri) return setError(browserCapability('persistProject').reason)
    if (!confirmProtectedAction(`${account.email ?? account.displayName ?? account.id} 계정 연결과 저장된 토큰을 삭제합니다.`)) return
    try {
      await logoutChatGpt(account.id)
      setNotice('계정 연결을 해제했습니다. 보관하던 토큰도 삭제했습니다.')
      await refreshAccounts()
    } catch (logoutError) {
      setError(String(logoutError))
    }
  }

  const create = async () => {
    if (!isTauri) return setError(browserCapability('callExternalService').reason)
    setError('')
    setNotice('')
    const config: Record<string, unknown> = kind === 'mcp-http'
      ? { url: url.trim() }
      : kind === 'mcp-stdio'
        ? {
          command: command.trim(),
          args: argsText.split(/\r?\n/).map((value) => value.trim()).filter(Boolean),
          cwd: cwd.trim(),
          env: envText.split(',').map((value) => value.trim()).filter(Boolean).map((envName) => ({ name: envName })),
        }
        : {}
    try {
      await saveConnection({ name: name.trim() || '새 연결', kind, config })
      setName('')
      setCommand('')
      setArgsText('')
      setUrl('')
      setCwd('')
      setEnvText('')
      setNotice('연결을 저장했습니다. 연결 테스트로 도구 목록을 읽으세요.')
      await refresh()
    } catch (saveError) {
      setError(String(saveError))
    }
  }

  const runTest = async (connection: ConnectionRow) => {
    if (!isTauri) return setError(browserCapability('callExternalService').reason)
    setBusy(connection.id)
    setError('')
    setNotice('')
    try {
      const result = await testConnection(connection.id)
      setTools((current) => ({ ...current, [connection.id]: result.tools }))
      const serverName = typeof result.serverInfo?.name === 'string' ? ` (${result.serverInfo.name})` : ''
      setNotice(result.message ?? `${result.tools.length}개 도구를 확인했습니다${serverName}.`)
      await refresh()
    } catch (testError) {
      setError(String(testError))
      await refresh()
    } finally {
      setBusy('')
    }
  }

  const openTools = async (connection: ConnectionRow) => {
    setBusy(connection.id)
    try {
      const rows = await listConnectionTools(connection.id)
      setTools((current) => ({ ...current, [connection.id]: rows }))
    } catch (toolError) {
      setError(String(toolError))
    } finally {
      setBusy('')
    }
  }
  const verifyTool = async (connection: ConnectionRow) => {
    try {
      const cached = tools[connection.id] ?? []
      const available = cached.length > 0 ? cached : await listConnectionTools(connection.id)
      if (cached.length === 0) setTools((current) => ({ ...current, [connection.id]: available }))
      const tool = available.find((item) => item.enabled)
      if (!tool) return setError('실행 검증할 사용 중인 도구가 없습니다. 도구를 먼저 확인하세요.')
      await callConnectionTool(connection.id, tool.name, {})
      setNotice(`${tool.name} 실제 호출을 검증했습니다.`)
      await refresh()
    } catch (verifyError) {
      setError(String(verifyError))
    }
  }

  const toggleTool = async (connection: ConnectionRow, tool: ConnectionToolRow) => {
    if (!isTauri) return setError(browserCapability('persistProject').reason)
    try {
      await setConnectionToolEnabled(connection.id, tool.name, !tool.enabled)
      setTools((current) => ({
        ...current,
        [connection.id]: (current[connection.id] ?? []).map((item) => (item.name === tool.name ? { ...item, enabled: !item.enabled } : item)),
      }))
    } catch (toolError) {
      setError(String(toolError))
    }
  }

  const toggleEnabled = async (connection: ConnectionRow) => {
    if (!isTauri) return setError(browserCapability('persistProject').reason)
    try {
      await setConnectionEnabled(connection.id, !connection.enabled)
      await refresh()
    } catch (toggleError) {
      setError(String(toggleError))
    }
  }

  const remove = async (connection: ConnectionRow) => {
    if (!isTauri) return setError(browserCapability('persistProject').reason)
    if (!confirmProtectedAction(`“${connection.name}” 연결과 저장된 도구 ${connection.toolCount}개를 삭제합니다. 프로젝트 문서와 실행 기록은 남습니다.`)) return
    try {
      await deleteConnection(connection.id)
      setTools((current) => {
        const next = { ...current }
        delete next[connection.id]
        return next
      })
      await refresh()
    } catch (removeError) {
      setError(String(removeError))
    }
  }

  return (
    <div className="page-stack">
      <div className="seg" role="tablist" aria-label="연결 운영">
        <button className={section === 'connections' ? 'active' : ''} onClick={() => setSection('connections')}>MCP 연결</button>
        <button className={section === 'accounts' ? 'active' : ''} onClick={() => setSection('accounts')}>ChatGPT 계정</button>
        <button className={section === 'workflows' ? 'active' : ''} onClick={() => setSection('workflows')}>Modal 워크플로</button>
      </div>
      {error && <p className="inline-warn">{error}</p>}
      {notice && <p className="usage-notice"><Play size={13} />{notice}<button onClick={() => setNotice('')} aria-label="알림 닫기">×</button></p>}
      {section === 'connections' && <>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="section-kicker"><Cable size={12} /> 연결 관리</span>
            <h2>MCP 서버와 계정 연결</h2>
            <p>로컬 stdio 서버는 실행 파일과 인수 배열로 등록합니다. 비밀값은 저장하지 않고 환경변수 이름만 남깁니다.</p>
          </div>
          <button className="secondary-action small" onClick={() => void refresh()}>
            <RefreshCw size={13} />
            새로고침
          </button>
        </div>

        <div className="conn-form">
          <label className="field-label">이름
            <input value={name} onChange={(event) => setName(event.target.value)} placeholder="예: Higgsfield MCP" />
          </label>
          <label className="field-label">종류
            <select value={kind} onChange={(event) => setKind(event.target.value)}>
              {Object.entries(CONNECTION_KIND_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          {kind === 'mcp-stdio' && (
            <>
              <label className="field-label">실행 파일
                <input value={command} onChange={(event) => setCommand(event.target.value)} placeholder="예: python" />
              </label>
              <label className="field-label">인수 (한 줄에 하나)
                <textarea rows={2} value={argsText} onChange={(event) => setArgsText(event.target.value)} placeholder="예: tools/test_mcp_server.py" />
              </label>
              <label className="field-label">작업 폴더
                <input value={cwd} onChange={(event) => setCwd(event.target.value)} placeholder="예: C:\\Users\\me\\project" />
              </label>
              <label className="field-label">환경변수 이름 (쉼표)
                <input value={envText} onChange={(event) => setEnvText(event.target.value)} placeholder="예: HIGGSFIELD_TOKEN" />
              </label>
            </>
          )}
          {kind === 'mcp-http' && (
            <label className="field-label">서버 URL
              <input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="예: https://example.com/mcp" />
            </label>
          )}
          <div className="conn-form-actions">
            <button className="primary-action small" disabled={!isTauri} title={isTauri ? undefined : browserCapability('callExternalService').nextAction} onClick={() => void create()}>
              <Plus size={13} />
              연결 추가
            </button>
            <span className="target-note">
              {kind === 'mcp-stdio' || kind === 'mcp-http'
                ? '연결 테스트는 서버를 실행해 도구 목록만 읽습니다. 유료 생성은 실행하지 않습니다.'
                : '이 종류는 설정만 저장하고 자동 점검은 아직 없습니다.'}
            </span>
          </div>
        </div>

        <div className="table-scroll">
          <table className="dense-table">
            <thead>
              <tr>
                <th>이름</th>
                <th>종류</th>
                <th>상태</th>
                <th className="num">도구</th>
                <th>마지막 확인</th>
                <th className="actions">동작</th>
              </tr>
            </thead>
            <tbody>
              {connections.length === 0 && (
                <tr><td colSpan={6}><p className="table-empty">아직 등록된 연결이 없습니다.</p></td></tr>
              )}
              {connections.map((connection) => (
                <React.Fragment key={connection.id}>
                  <tr className={connection.enabled ? undefined : 'off'}>
                    <td>
                      <strong>{connection.name}</strong>
                      <small>{connection.kind === 'mcp-stdio'
                        ? String((connection.config as { command?: unknown }).command ?? '')
                        : String((connection.config as { url?: unknown }).url ?? '')}</small>
                      {connection.lastError && <small className="bad" title={connection.lastError}>{connection.lastError}</small>}
                    </td>
                    <td>{CONNECTION_KIND_LABELS[connection.kind] ?? connection.kind}</td>
                    <td>
                      <span className={`state-chip ${connection.status === 'error' ? 'off' : 'on'}`}>
                        {CONNECTION_STATUS_LABELS[connection.status] ?? connection.status}
                      </span>
                    </td>
                    <td className="num">{connection.toolCount}</td>
                    <td>{connection.lastCheckedAt ? connection.lastCheckedAt.slice(5, 16).replace('T', ' ') : '-'}</td>
                    <td className="actions">
                      <button className="row-action" disabled={busy === connection.id} onClick={() => connection.status === 'tools-ready' ? void verifyTool(connection) : connection.status === 'verified' ? void openTools(connection) : void runTest(connection)}>{connection.status === 'tools-ready' ? '실제 호출 검증' : connection.status === 'verified' ? '도구 확인' : '다음: 연결 테스트'}</button>
                      <button className="row-action" onClick={() => void toggleEnabled(connection)}>{connection.enabled ? '먼저 사용 중지' : '다시 사용'}</button>
                      {!connection.enabled && <button className="row-action danger" onClick={() => void remove(connection)}>사용 중지 후 삭제</button>}
                    </td>
                  </tr>
                  {(tools[connection.id] ?? []).length > 0 && (
                    <tr>
                      <td colSpan={6}>
                        <div className="conn-tools">
                          {tools[connection.id].map((tool) => (
                            <label key={tool.name} className="conn-tool">
                              <input type="checkbox" checked={tool.enabled} onChange={() => void toggleTool(connection, tool)} />
                              <span>
                                <strong>{tool.name}</strong>
                                <small>{tool.description ?? '설명 없음'}</small>
                              </span>
                            </label>
                          ))}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>

        <p className="usage-note">비밀값은 저장하지 않고 환경변수 이름만 남깁니다. 저장됨은 테스트, 도구 확인됨은 실제 호출 검증이 다음 행동입니다.</p>
      </section>
      </>}

      {section === 'accounts' &&
      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="section-kicker"><Cable size={12} /> ChatGPT 계정</span>
            <h2>구독 계정 연결</h2>
            <p>
              브라우저에서 로그인하면 앱이 콜백을 받아 토큰을 운영체제 저장소(DPAPI)에 보관합니다.
              토큰은 화면으로 전달되지 않고, 요청 직전에 만료를 확인해 계정당 한 번만 갱신합니다.
            </p>
          </div>
          <button className="primary-action small" disabled={!isTauri || Boolean(attempt)} title={isTauri ? undefined : browserCapability('callExternalService').nextAction} onClick={() => void startLogin()}>
            <Play size={13} />
            ChatGPT로 로그인
          </button>
        </div>

        {attempt && (
          <p className="usage-notice">
            <RefreshCw size={13} />
            로그인 대기 중입니다{attemptState?.state === 'pending' ? '' : ` (${attemptState?.state})`}.
            남은 시간 {remainingLabel}.
            브라우저가 열리지 않으면 <a href={attempt.authUrl} target="_blank" rel="noreferrer">인증 주소</a>를 직접 여세요.
            <button onClick={() => void cancelAttempt()}>취소</button>
          </p>
        )}

        <div className="table-scroll">
          <table className="dense-table">
            <thead>
              <tr>
                <th>계정</th>
                <th>상태</th>
                <th>토큰 만료</th>
                <th className="num">버전</th>
                <th className="actions">동작</th>
              </tr>
            </thead>
            <tbody>
              {accounts.length === 0 && (
                <tr><td colSpan={5}><p className="table-empty">아직 연결된 ChatGPT 계정이 없습니다.</p></td></tr>
              )}
              {accounts.map((account) => (
                <tr key={account.id} className={account.status === 'relogin' ? 'off' : undefined}>
                  <td>
                    <strong>{account.email ?? account.displayName ?? account.id}</strong>
                    <small>{account.accountId ?? account.id}</small>
                    {account.lastError && <small className="bad" title={account.lastError}>{account.lastError}</small>}
                  </td>
                  <td>
                    <span className={`state-chip ${account.status === 'ok' ? 'on' : 'off'}`}>
                      {account.status === 'ok' ? '사용 가능' : '재로그인 필요'}
                    </span>
                  </td>
                  <td>
                    {account.expiresAt
                      ? new Date(account.expiresAt * 1000).toISOString().slice(5, 16).replace('T', ' ')
                      : '-'}
                  </td>
                  <td className="num">{account.credentialVersion}</td>
                  <td className="actions">
                    <button className="row-action" onClick={() => void refreshAccount(account)}>토큰 갱신 확인</button>
                    <button className="row-action danger" onClick={() => void removeAccount(account)}>연결 해제</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      }

      {section === 'workflows' && <>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="section-kicker"><Boxes size={12} /> 워크플로</span>
            <h2>등록된 생성 워크플로</h2>
            <p>
              Modal에 배포한 워크플로를 캔버스의 Comfy 워크플로 노드에서 선택합니다.
              입출력 형식이 다른 워크플로를 함께 등록해 같은 캔버스에서 쓸 수 있습니다.
            </p>
          </div>
          <button className="secondary-action small" onClick={() => void refreshWorkflows()}>
            <RefreshCw size={13} />
            새로고침
          </button>
        </div>

        <div className="conn-form">
          <label className="field-label">이름
            <input value={workflowName} onChange={(event) => setWorkflowName(event.target.value)} placeholder="예: 제품 컷 변환" />
          </label>
          <label className="field-label">도구
            <select value={workflowTool} onChange={(event) => setWorkflowTool(event.target.value)}>
              {WORKFLOW_TOOL_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>
          <label className="field-label">실행 위치
            <input value={workflowLocation} onChange={(event) => setWorkflowLocation(event.target.value)} placeholder="예: modal:minimax-h3-latest-workflows" />
          </label>
          <label className="field-label">메모
            <input value={workflowNotes} onChange={(event) => setWorkflowNotes(event.target.value)} placeholder="입출력·모델·검증 범위" />
          </label>
          <div className="conn-form-actions">
            <button className="primary-action small" disabled={!isTauri} title={isTauri ? undefined : browserCapability('callExternalService').nextAction} onClick={() => void createWorkflow()}>
              <Plus size={13} />
              워크플로 등록
            </button>
            <span className="target-note">등록과 실행 검증은 다릅니다. 실제 실행이 확인된 워크플로만 `실행 검증됨`으로 표시됩니다.</span>
          </div>
        </div>

        <div className="table-scroll">
          <table className="dense-table">
            <thead>
              <tr>
                <th>이름</th>
                <th>도구</th>
                <th>상태</th>
                <th>실행 위치</th>
                <th>메모</th>
                <th className="actions">동작</th>
              </tr>
            </thead>
            <tbody>
              {workflows.length === 0 && (
                <tr><td colSpan={6}><p className="table-empty">아직 등록된 워크플로가 없습니다.</p></td></tr>
              )}
              {workflows.map((workflow) => (
                <tr key={workflow.id}>
                  <td><strong>{workflow.name}</strong><small>{workflow.id}</small></td>
                  <td>{workflow.tool}</td>
                  <td>
                    <span className={`state-chip ${workflow.status === 'verified' ? 'on' : 'off'}`}>
                      {WORKFLOW_STATUS_LABELS[workflow.status] ?? workflow.status}
                    </span>
                  </td>
                  <td>{workflow.location ?? '-'}</td>
                  <td><small>{workflow.notes ?? '-'}</small></td>
                  <td className="actions">
                    <button className="row-action danger" onClick={() => void removeWorkflow(workflow)}>삭제</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <p className="dim">등록됨과 실행 검증됨은 다른 상태입니다. 실제 실행 전에는 실행 검증됨으로 표시하지 않습니다.</p>
      </>}

      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="section-kicker"><Trash2 size={12} /> 정리</span>
            <h2>등록된 연결 정리</h2>
            <p>연결을 삭제하면 저장된 설정과 도구 목록이 함께 사라집니다. 프로젝트 문서와 실행 기록은 남습니다.</p>
          </div>
        </div>
      </section>
    </div>
  )
}
