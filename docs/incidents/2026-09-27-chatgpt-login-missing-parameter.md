# ChatGPT login failed with missing_required_parameter

- Date/time: 2026-09-27, Asia/Seoul
- Impact: The user could not finish a ChatGPT login from the app and saw the OAuth error page. A follow-up attempt could not start because the fixed callback port 1455 was still held by the app's own pending listener. Stored credentials and existing conversations were unaffected.

## Symptoms and evidence

- The browser showed "필수 매개변수가 누락되었습니다 … 오류 코드: missing_required_parameter" with request ID `de0bfb54-d7e5-4989-b065-345591205ad0`.
- The authorize URL the app builds contained every required parameter (response_type, client_id, redirect_uri, scope, PKCE S256 challenge, state, codex_cli_simplified_flow, originator, id_token_add_organizations). Opening the same URL in a fresh browser profile reached the ChatGPT login page without an error.
- From 11:03 to 11:05 the app process held `127.0.0.1:1455` and `[::1]:1455` in LISTENING state, and `chatgpt_login_start` failed with "포트 1455을 사용할 수 없어 …".
- The port was released at 11:07:23, five minutes after the earlier attempt had started. A new attempt at 11:07:59 completed with a real account login at 11:09:42.
- With that account, a real model conversation (11:13) and an image attachment round trip (11:20) were verified from the app.

## Confirmed cause

- The app opened the authorize URL with `cmd /C start "" <url>`. `cmd` parsed the URL itself, so everything from the first `&` was treated as a separate command: the browser reached the server with only `?response_type=code`, which the server rejects as `missing_required_parameter`.
- Reproduced on 12:56 KST against a local listener: the old command delivered only `/old?a=1`, while the Windows shell API (`ShellExecuteW`) delivered the full URL with all ten query parameters.
- A login attempt holds the fixed callback port until its timeout, so a second attempt cannot start while the first is pending.
- Not confirmed: which attempt produced the original error page. The reproduced truncation matches the symptom, but request ID `de0bfb54-…` was never matched against server-side records.

## Response and verification

- Browser hand-off fixed: `open_in_browser` now hands the whole URL to the shell API as one argument (`src-tauri/src/media.rs`), and a test pins that the UTF-16 argument keeps the query string.
- Callback connections keep a 2-second read limit, but a delayed request is no longer dropped on the first `WouldBlock`; both paths have tests (`a_silent_callback_connection_does_not_hold_the_login_port`, `a_delayed_callback_request_is_still_accepted`).
- A pending attempt now reports its deadline. The connections screen shows the remaining time next to the cancel action, and the app appends the attempt id, expiry, and the exact authorize URL to `%APPDATA%\com.modal-gui.desktop\logs\chatgpt-login.log`.
- Native app check (13:05 KST): the pending line showed `남은 시간 4:59` counting down to `4:56`, the manual link carried the full authorize URL, and cancel ended the attempt with `로그인을 취소했습니다.` The log file holds both attempts with all ten query parameters.
- The user completed a fresh login attempt. The account was stored with DPAPI encryption, and real model chat plus attachment delivery were verified from the app.
- Gates after the changes: `cargo test` 59 passed, `npm run build` OK, renderer tests 27, worker tests 29.

## Follow-up

- Match a future failure's request ID against the logged URL before changing the OAuth flow.
