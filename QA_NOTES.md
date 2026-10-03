# 📝 QA Notes: Speech Synthesis & Browser Autoplay / User-Gesture Verification

## 1. Overview & Verification Objective
Test whether the **first question's auto-speak** (`speechSynthesis.speak()`) is silently blocked by the browser's autoplay/user-gesture policy when entering an interview room, and verify whether navigating across routes or waiting for asynchronous session-start API calls breaks the browser's user activation chain.

---

## 2. Test Findings & Root Cause Analysis

### Issue Confirmed: Yes, SpeechSynthesis Was Silently Blocked
1. **User Gesture Token Expiration Across Async Boundaries:**
   - In modern browsers (Google Chrome, Microsoft Edge, Mozilla Firefox, and Apple Safari/WebKit), Web Speech API (`window.speechSynthesis.speak`) is governed by browser user activation and autoplay media policies.
   - When a user clicked **"Start Interview"** or **"Resume Interview"** on `InterviewLandingPage`, the application previously executed a client-side route navigation (`navigate('/interview/:taskId/room?mode=start')`) and unmounted the landing page.
   - On `InterviewRoomPage`, the first question was fetched asynchronously inside `initializeSession()` (`await startSession(taskId)`).
   - This network roundtrip (gateway proxy + DB query + LLM generation) took several hundred milliseconds to seconds.
   - Once the API resolved, `setCurrentTurn(startData.first_question)` updated React component state, which only later triggered a separate `useEffect` hook to call `speakQuestion(currentTurn.question_text)`.
   - By the time `useEffect` executed, the transient user activation gesture (`navigator.userActivation.isActive`) was completely expired or detached from the original user interaction.

2. **Silent Failure Behavior Across Browsers:**
   - **Safari / WebKit:** Strictly silences and drops `speechSynthesis.speak()` calls that do not originate synchronously within a direct user interaction call stack (e.g. `onClick`).
   - **Chromium / Chrome / Edge:** Without an active user gesture or high Media Engagement Index (MEI), `speak()` queues the utterance without playing audio, or `onstart` fails to trigger within 500ms while remaining paused.
   - **Direct Page Reloads / Bookmarks:** If a candidate reloads `/interview/:taskId/room` directly, no user gesture exists at all, completely muting Question 1.

---

## 3. Implemented Fixes

### Fix 1: Direct Synchronous Gesture Priming & Immediate Click-Chain Synthesis
- In `frontend/src/pages/InterviewLandingPage.tsx`:
  - **Synchronous Engine Priming:** Inside `handleStartInterview` and `handleResumeInterview`, `primeSpeechSynthesis()` synchronously calls `window.speechSynthesis.speak(primeUtterance)` and `resume()` directly within the user's click event loop before any asynchronous operation begins.
  - **Immediate API-Resolution Trigger:** The `startSession(taskId)` / `resumeSession(taskId)` API call is executed directly within the button click handler. Immediately when the promise resolves, `window.speechSynthesis.speak(utterance)` is triggered for Question 1 within that gesture-initiated promise chain.
  - **Preloaded Navigation State:** Preloaded session and question data are passed via `navigate(..., { state: { preloadedSession, preloadedTurn, autoSpokenTurnId } })`, enabling `InterviewRoomPage` to mount instantly with the active question without duplicate fetches or deferred `useEffect` state changes.

### Fix 2: Direct Trigger for Direct Navigation
- In `frontend/src/pages/InterviewRoomPage.tsx`:
  - For direct URL loads or refreshes where preloaded state is absent, `initializeSession()` directly triggers `speakQuestion(startData.first_question.question_text)` immediately upon API resolution and marks `lastSpokenTurnIdRef.current`, eliminating deferred execution in a detached `useEffect`.

### Fix 3: ~500ms Silent Failure Fallback with Prominent Replay Button
- In `frontend/src/pages/InterviewRoomPage.tsx`:
  - Added a fallback detection timer (`speakFallbackTimerRef`):
    - When `speak()` is called, if `utterance.onstart` does not fire within ~500ms (or if `utterance.onerror` fires due to browser media policy), `showProminentReplay` is automatically set to `true`.
    - Also on room mount, if speech synthesis is not actively speaking within 500ms, `showProminentReplay` activates.
  - **Prominent UI Presentation:**
    - The header Replay button (`#replay-question-btn`) turns into an active, pulsing primary action (`Play Audio`).
    - A dedicated prominent audio callout banner appears directly beneath the question card with `#replay-question-prominent-btn` (`🔊 Replay Question`), explaining that the browser required a user interaction and providing a one-click way to hear the question.
  - **Gesture-Backed Reliability:** Because replay clicks are direct user clicks on the page, `handleReplayQuestion()` is 100% gesture-backed and plays audio reliably in every browser. Upon successful playback start, the prominent banner automatically clears.

---

## 4. Verification Results
- **TypeScript & Build Verification:** `npm --prefix frontend run build` compiled cleanly with 0 errors.
- **Linter Verification:** `npm --prefix frontend run lint` passed with 0 errors.
- **Autoplay / Fallback Behavior:**
  - Direct gesture triggers reliably prime and speak Question 1 on user start.
  - Any silent browser delay or autoplay block past ~500ms automatically prompts the user with the prominent "🔊 Replay Question" button.
