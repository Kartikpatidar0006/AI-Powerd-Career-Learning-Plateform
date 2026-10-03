/**
 * InterviewRoomPage — Interactive mock interview session room with voice & text modes.
 *
 * Route: /interview/:taskId/room
 *
 * Supports:
 * - Direct start or resume on mount (with automatic resume fallback on 409)
 * - Browser-native Web Speech API voice capabilities:
 *   - Text-to-Speech (speechSynthesis) with lang='en-IN' & silent default voice fallback
 *   - Speech-to-Text (SpeechRecognition) with real-time interim transcript into textarea
 *   - Replay question button, per-session mute toggle, and clean microphone capture
 * - Textarea manual input with Ctrl+Enter submission shortcut (additive with voice)
 * - Graceful fallback to text-only mode for unsupported browsers (e.g. Firefox)
 * - "Interviewer is thinking..." dynamic state
 * - Automatic transition to closing remark upon completion
 * - 409/503 error handling with answer preservation
 *
 * NOTE: Voice capability is powered by browser-native Web Speech API (free prototype-grade),
 * which works best on Google Chrome and Microsoft Edge desktop.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import AppNavbar from '../components/AppNavbar';
import {
  startSession,
  resumeSession,
  submitAnswer,
  InterviewApiError,
} from '../services/interview';
import type {
  InterviewSessionResponse,
  InterviewTurnResponse,
  OverallPerformanceSummary,
} from '../types/interview';

// Web Speech API browser compatibility interfaces (SpeechRecognition & speechSynthesis)
interface IWindowSpeech extends Window {
  SpeechRecognition?: {
    new (): SpeechRecognitionInstance;
  };
  webkitSpeechRecognition?: {
    new (): SpeechRecognitionInstance;
  };
}

interface SpeechRecognitionInstance extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onstart: ((this: SpeechRecognitionInstance, ev: Event) => void) | null;
  onresult: ((this: SpeechRecognitionInstance, ev: SpeechRecognitionResultEvent) => void) | null;
  onerror: ((this: SpeechRecognitionInstance, ev: SpeechRecognitionErrorEvent) => void) | null;
  onend: ((this: SpeechRecognitionInstance, ev: Event) => void) | null;
}

interface SpeechRecognitionResultEvent extends Event {
  resultIndex: number;
  results: {
    length: number;
    [index: number]: {
      isFinal: boolean;
      length: number;
      [index: number]: {
        transcript: string;
        confidence: number;
      };
    };
  };
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string;
  message?: string;
}

function formatTimer(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

export default function InterviewRoomPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const mode = searchParams.get('mode'); // 'start' | 'resume'

  // Session state
  const [session, setSession] = useState<InterviewSessionResponse | null>(null);
  const [currentTurn, setCurrentTurn] = useState<InterviewTurnResponse | null>(null);
  const [turnHistory, setTurnHistory] = useState<InterviewTurnResponse[]>([]);
  const [isCompleted, setIsCompleted] = useState(false);
  const [closingMessage, setClosingMessage] = useState<string | null>(null);
  const [performanceSummary, setPerformanceSummary] = useState<OverallPerformanceSummary | null>(null);

  // User interaction state
  const [answerText, setAnswerText] = useState('');
  const [loading, setLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isConflictError, setIsConflictError] = useState(false);
  const [isServiceUnavailable, setIsServiceUnavailable] = useState(false);

  // Voice state (Web Speech API) — detected on mount with browser capability checks
  const [voiceSupported] = useState(() => {
    if (typeof window === 'undefined') return false;
    const win = window as unknown as IWindowSpeech;
    const hasSTT = Boolean(win.SpeechRecognition || win.webkitSpeechRecognition);
    const hasTTS = Boolean(window.speechSynthesis && window.SpeechSynthesisUtterance);
    return hasSTT && hasTTS;
  });
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [interimTranscript, setInterimTranscript] = useState('');
  const [micError, setMicError] = useState<string | null>(null);

  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const selectedVoiceRef = useRef<SpeechSynthesisVoice | null>(null);
  const baseTextRef = useRef<string>('');
  const lastSpokenTurnIdRef = useRef<string | null>(null);

  // Question duration timer
  const [secondsElapsed, setSecondsElapsed] = useState(0);
  const questionStartTimeRef = useRef<number>(0);
  const timerIntervalRef = useRef<number | null>(null);

  const startTimer = useCallback(() => {
    questionStartTimeRef.current = Date.now();
    setSecondsElapsed(0);
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
    }
    timerIntervalRef.current = window.setInterval(() => {
      setSecondsElapsed(Math.floor((Date.now() - questionStartTimeRef.current) / 1000));
    }, 1000);
  }, []);

  const stopTimer = useCallback(() => {
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }
  }, []);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      stopTimer();
    };
  }, [stopTimer]);

  // 1. Cache voices prioritizing en-IN; if unavailable, silently falls back to browser default voice
  useEffect(() => {
    if (typeof window === 'undefined' || !window.speechSynthesis) return;

    const updateVoices = () => {
      const voices = window.speechSynthesis.getVoices();
      // Look for en-IN voice; if none found on the device, silently fall back to default
      const indianVoice = voices.find((v) =>
        v.lang.toLowerCase().replace('_', '-').includes('en-in')
      );
      selectedVoiceRef.current = indianVoice || null;
    };

    updateVoices();
    if (window.speechSynthesis.onvoiceschanged !== undefined) {
      window.speechSynthesis.onvoiceschanged = updateVoices;
    }
  }, []);

  // 3. TTS Question Player
  const stopSpeaking = useCallback(() => {
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    setIsSpeaking(false);
  }, []);

  const speakQuestion = useCallback((text: string, force = false) => {
    if (typeof window === 'undefined' || !window.speechSynthesis) return;
    if (isMuted && !force) return;

    // Cancel any in-progress utterance before starting a new one, avoiding overlapping audio
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-IN';
    if (selectedVoiceRef.current) {
      utterance.voice = selectedVoiceRef.current;
    }

    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);

    try {
      window.speechSynthesis.speak(utterance);
    } catch {
      setIsSpeaking(false);
    }
  }, [isMuted]);

  const handleReplayQuestion = () => {
    if (currentTurn?.question_text) {
      // Replaying forces utterance audio even if session was muted
      speakQuestion(currentTurn.question_text, true);
    }
  };

  const toggleMute = () => {
    setIsMuted((prev) => {
      const next = !prev;
      if (next) {
        stopSpeaking();
      }
      return next;
    });
  };

  // 4. Auto-speak new question when currentTurn updates (if voice supported and unmuted)
  useEffect(() => {
    if (!currentTurn || isCompleted || !voiceSupported) return;
    if (currentTurn.id && currentTurn.id !== lastSpokenTurnIdRef.current) {
      lastSpokenTurnIdRef.current = currentTurn.id;
      speakQuestion(currentTurn.question_text);
    }
  }, [currentTurn, isCompleted, voiceSupported, speakQuestion]);

  // 5. STT Speech-to-Text Listener
  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // no-op
      }
    }
    setIsListening(false);
    setInterimTranscript('');
  }, []);

  const startListening = async () => {
    setMicError(null);
    stopSpeaking(); // Cancel AI speech so it doesn't talk over the user

    // Request microphone permission cleanly via getUserMedia before starting recognition
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        // Stop stream immediately; SpeechRecognition manages its own capture
        stream.getTracks().forEach((track) => track.stop());
      } catch (err: unknown) {
        const isDenied =
          err instanceof DOMException &&
          (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError');
        setMicError(
          isDenied
            ? 'Microphone permission was denied. You can continue by typing your answer in the box below.'
            : 'Could not access microphone. Please type your answer instead.'
        );
        setIsListening(false);
        return;
      }
    }

    const win = window as unknown as IWindowSpeech;
    const SpeechRecognitionConstructor = win.SpeechRecognition || win.webkitSpeechRecognition;
    if (!SpeechRecognitionConstructor) {
      setMicError('Speech recognition is not supported in this browser.');
      return;
    }

    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort();
      } catch {
        // no-op
      }
    }

    // Preserve existing textarea content as the baseline for seamless typing + voice composition
    baseTextRef.current = answerText;
    setInterimTranscript('');

    const recognition = new SpeechRecognitionConstructor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-IN';

    recognition.onstart = () => {
      setIsListening(true);
    };

    recognition.onresult = (event: SpeechRecognitionResultEvent) => {
      let sessionTranscript = '';
      let currentInterim = '';

      for (let i = 0; i < event.results.length; i++) {
        const resultItem = event.results[i];
        const transcriptText = resultItem[0]?.transcript || '';
        sessionTranscript += transcriptText;
        if (!resultItem.isFinal) {
          currentInterim += transcriptText;
        }
      }

      setInterimTranscript(currentInterim);

      const base = baseTextRef.current.trim();
      const combined = base
        ? `${base} ${sessionTranscript.trim()}`
        : sessionTranscript.trim();

      setAnswerText(combined);
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      // Ignore 'no-speech' pauses gracefully
      if (event.error === 'no-speech') {
        return;
      }

      if (event.error === 'not-allowed') {
        setMicError('Microphone permission denied. You can continue by typing your answer.');
      } else if (event.error === 'audio-capture') {
        setMicError('No audio input detected. Please verify your microphone or type your answer.');
      } else if (event.error !== 'aborted') {
        setMicError(`Voice recognition issue (${event.error}). You can continue by typing.`);
      }

      setIsListening(false);
      setInterimTranscript('');
    };

    recognition.onend = () => {
      setIsListening(false);
      setInterimTranscript('');
    };

    try {
      recognition.start();
      recognitionRef.current = recognition;
    } catch {
      setMicError('Failed to start speech recognition. Please type your answer.');
      setIsListening(false);
    }
  };

  // 6. Cleanup voice resources on unmount or navigation away
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          // no-op
        }
      }
      if (typeof window !== 'undefined' && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  // Initial Load: Start or Resume session
  useEffect(() => {
    if (!taskId) return;

    let mounted = true;

    const initializeSession = async () => {
      try {
        setLoading(true);
        setError(null);
        setIsConflictError(false);
        setIsServiceUnavailable(false);

        if (mode === 'resume') {
          const resumeData = await resumeSession(taskId);
          if (!mounted) return;

          setSession(resumeData.session);
          setTurnHistory(resumeData.turns);

          // Find the latest unanswered turn, or the last turn if finished
          const unanswered = resumeData.turns.find((t) => t.answer_text === null);
          if (unanswered) {
            setCurrentTurn(unanswered);
            startTimer();
          } else if (resumeData.turns.length > 0) {
            // All answered — check if completed
            const lastTurn = resumeData.turns[resumeData.turns.length - 1];
            setCurrentTurn(lastTurn);
            if (resumeData.session.status === 'COMPLETED') {
              setIsCompleted(true);
              setClosingMessage(lastTurn.question_text);
              setPerformanceSummary(resumeData.session.overall_performance_summary);
            }
          }
        } else {
          // Attempt start; if 409 because already started, gracefully resume
          try {
            const startData = await startSession(taskId);
            if (!mounted) return;

            setSession(startData.session);
            setCurrentTurn(startData.first_question);
            setTurnHistory([startData.first_question]);
            startTimer();
          } catch (startErr: unknown) {
            if (startErr instanceof InterviewApiError && startErr.isConflict()) {
              // Already IN_PROGRESS -> resume automatically
              const resumeData = await resumeSession(taskId);
              if (!mounted) return;

              setSession(resumeData.session);
              setTurnHistory(resumeData.turns);
              const unanswered = resumeData.turns.find((t) => t.answer_text === null);
              if (unanswered) {
                setCurrentTurn(unanswered);
                startTimer();
              } else if (resumeData.turns.length > 0) {
                setCurrentTurn(resumeData.turns[resumeData.turns.length - 1]);
              }
            } else {
              throw startErr;
            }
          }
        }
      } catch (err: unknown) {
        if (!mounted) return;
        if (err instanceof InterviewApiError) {
          if (err.isConflict()) {
            setIsConflictError(true);
            setError(err.detail);
          } else if (err.isUnavailable()) {
            setIsServiceUnavailable(true);
            setError(err.detail);
          } else {
            setError(err.detail);
          }
        } else {
          setError(err instanceof Error ? err.message : 'Failed to connect to interview session');
        }
      } finally {
        if (mounted) setLoading(false);
      }
    };

    initializeSession();

    return () => {
      mounted = false;
    };
  }, [taskId, mode, startTimer]);

  // Answer Submission Handler
  const handleSubmitAnswer = async () => {
    if (!taskId || !currentTurn || !answerText.trim() || isSubmitting) return;

    // Automatically stop any active recognition session or TTS speech
    stopListening();
    stopSpeaking();

    try {
      setIsSubmitting(true);
      setError(null);
      setIsServiceUnavailable(false);

      const durationSeconds = Math.max(
        1.0,
        (Date.now() - questionStartTimeRef.current) / 1000
      );

      const result = await submitAnswer(taskId, answerText.trim(), durationSeconds);

      // Answer was successfully committed
      setAnswerText('');

      // Check if closing turn or interview completed
      if (result.is_closing || result.status === 'COMPLETED') {
        stopTimer();
        setIsCompleted(true);
        setClosingMessage(result.next_turn.question_text);
        setPerformanceSummary(result.overall_performance_summary);
        setCurrentTurn(result.next_turn);
        setTurnHistory((prev) => [...prev, result.answered_turn, result.next_turn]);
      } else {
        // Proceed to next question turn
        setCurrentTurn(result.next_turn);
        setTurnHistory((prev) => [...prev, result.answered_turn]);
        startTimer();
      }
    } catch (err: unknown) {
      if (err instanceof InterviewApiError) {
        if (err.isConflict()) {
          setIsConflictError(true);
          setError(err.detail);
        } else if (err.isUnavailable()) {
          // Answer was safely saved; let user retry question generation
          setIsServiceUnavailable(true);
          setError(err.detail);
        } else {
          setError(err.detail);
        }
      } else {
        setError(err instanceof Error ? err.message : 'Error submitting answer');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  // Keyboard shortcut: Ctrl+Enter to submit
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSubmitAnswer();
    }
  };

  return (
    <div className="min-h-screen bg-surface-950 text-surface-100 flex flex-col">
      <AppNavbar />

      <main className="flex-1 max-w-4xl w-full mx-auto px-4 py-6 flex flex-col justify-between">
        {/* Top Session Progress Bar */}
        <div className="flex items-center justify-between pb-4 border-b border-surface-800/80 mb-6">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate(`/interview/${taskId}`)}
              className="text-xs text-surface-400 hover:text-surface-200 transition-colors"
            >
              ← Overview
            </button>
            <span className="text-surface-600">|</span>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-xs font-semibold text-surface-200">Live AI Mock Interview</span>
            </div>
          </div>

          <div className="flex items-center gap-4 text-xs font-mono">
            {/* Active Turn Indicator */}
            {currentTurn && !isCompleted && (
              <div className="px-2.5 py-1 rounded-lg bg-surface-800 text-surface-300 border border-surface-700">
                Question {currentTurn.turn_number} of ~6
              </div>
            )}

            {/* Session Violation Count Warning */}
            {session && session.violation_count > 0 && (
              <div className="px-2.5 py-1 rounded-lg bg-red-500/10 text-red-300 border border-red-500/20 text-xs">
                ⚠️ Warnings: {session.violation_count}/3
              </div>
            )}

            {/* Answer Duration Timer */}
            {!isCompleted && !loading && (
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-primary-500/10 text-primary-300 border border-primary-500/20">
                <span>⏱️</span>
                <span>{formatTimer(secondsElapsed)}</span>
              </div>
            )}
          </div>
        </div>

        {/* Loading Spinner */}
        {loading && (
          <div className="my-auto p-12 text-center space-y-4 rounded-2xl bg-surface-900/40 border border-surface-800">
            <div className="w-10 h-10 mx-auto rounded-full border-2 border-primary-500 border-t-transparent animate-spin" />
            <p className="text-surface-300 text-sm font-medium">Connecting to AI Interviewer...</p>
            <p className="text-xs text-surface-400">Loading your evaluation findings and preparing dynamic questions.</p>
          </div>
        )}

        {/* Conflict Error (Session no longer in progress) */}
        {!loading && isConflictError && (
          <div className="my-auto p-8 rounded-2xl bg-amber-500/10 border border-amber-500/20 space-y-4 text-center max-w-lg mx-auto">
            <div className="text-3xl">⚠️</div>
            <h2 className="text-lg font-bold text-surface-50">Session Status Changed</h2>
            <p className="text-sm text-surface-300">{error}</p>
            <div className="pt-2">
              <button
                onClick={() => navigate(`/interview/${taskId}`)}
                className="px-6 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-surface-950 font-semibold text-sm transition-all shadow-lg shadow-amber-500/20"
              >
                Return to Interview Overview
              </button>
            </div>
          </div>
        )}

        {/* General Error Banner */}
        {!loading && error && !isConflictError && (
          <div className="mb-4 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-sm flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span>⚠️</span>
              <span>{error}</span>
            </div>
            {isServiceUnavailable && (
              <button
                onClick={handleSubmitAnswer}
                disabled={isSubmitting}
                className="px-3 py-1 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-xs font-semibold text-red-200 transition-colors"
              >
                Retry
              </button>
            )}
          </div>
        )}

        {/* Main Interview Stage */}
        {!loading && !isConflictError && (
          <div className="space-y-6 my-auto">
            {/* Voice Unsupported Graceful Fallback Banner */}
            {!isCompleted && !voiceSupported && (
              <div className="p-3.5 rounded-xl bg-surface-900/60 border border-surface-800 text-surface-400 text-xs flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span>ℹ️</span>
                  <span>
                    Voice mode isn't supported in this browser — you can type your answers instead. For voice, try Chrome or Edge on desktop.
                  </span>
                </div>
                <span className="text-[11px] text-surface-500 whitespace-nowrap hidden sm:inline">Text Mode Active</span>
              </div>
            )}

            {/* COMPLETED STATE BANNER */}
            {isCompleted ? (
              <div className="p-8 sm:p-10 rounded-2xl bg-surface-900/80 border border-emerald-500/30 backdrop-blur-xl text-center space-y-6">
                <div className="w-16 h-16 mx-auto rounded-full bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-3xl">
                  🎓
                </div>

                <div className="space-y-2 max-w-xl mx-auto">
                  <h2 className="text-2xl font-bold text-surface-50 tracking-tight">
                    Interview Concluded
                  </h2>
                  <p className="text-sm text-surface-300 leading-relaxed italic">
                    "{closingMessage || currentTurn?.question_text || 'Thank you for your technical defense.'}"
                  </p>
                </div>

                {performanceSummary && (
                  <div className="p-5 rounded-xl bg-surface-950/60 border border-surface-800 text-left max-w-xl mx-auto space-y-4">
                    <div className="flex items-center justify-between border-b border-surface-800/80 pb-2">
                      <span className="text-xs font-bold text-surface-400 uppercase tracking-wider">
                        Interview Defense Signals (Agent 4)
                      </span>
                      <span className="text-[10px] text-surface-400 italic">
                        Qualitative indicators (not a unified score)
                      </span>
                    </div>

                    {/* 3 Qualitative Indicators */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <div className="p-3 rounded-lg bg-surface-900/80 border border-surface-800 space-y-2">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-surface-300 font-medium flex items-center gap-1.5">
                            <span>💬</span> Clarity
                          </span>
                          <span className="font-mono font-bold text-cyan-400">
                            {performanceSummary.communication_clarity}/100
                          </span>
                        </div>
                        <div className="w-full bg-surface-800 rounded-full h-1.5 overflow-hidden">
                          <div
                            className="h-1.5 rounded-full bg-cyan-400 transition-all duration-500"
                            style={{
                              width: `${Math.min(100, Math.max(0, performanceSummary.communication_clarity))}%`,
                            }}
                          />
                        </div>
                        <p className="text-[10px] text-surface-400">Clarity & articulation</p>
                      </div>

                      <div className="p-3 rounded-lg bg-surface-900/80 border border-surface-800 space-y-2">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-surface-300 font-medium flex items-center gap-1.5">
                            <span>⚙️</span> Depth
                          </span>
                          <span className="font-mono font-bold text-emerald-400">
                            {performanceSummary.technical_depth}/100
                          </span>
                        </div>
                        <div className="w-full bg-surface-800 rounded-full h-1.5 overflow-hidden">
                          <div
                            className="h-1.5 rounded-full bg-emerald-400 transition-all duration-500"
                            style={{
                              width: `${Math.min(100, Math.max(0, performanceSummary.technical_depth))}%`,
                            }}
                          />
                        </div>
                        <p className="text-[10px] text-surface-400">Technical reasoning</p>
                      </div>

                      <div className="p-3 rounded-lg bg-surface-900/80 border border-surface-800 space-y-2">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-surface-300 font-medium flex items-center gap-1.5">
                            <span>🎯</span> Confidence
                          </span>
                          <span className="font-mono font-bold text-violet-400">
                            {performanceSummary.confidence_signals}/100
                          </span>
                        </div>
                        <div className="w-full bg-surface-800 rounded-full h-1.5 overflow-hidden">
                          <div
                            className="h-1.5 rounded-full bg-violet-400 transition-all duration-500"
                            style={{
                              width: `${Math.min(100, Math.max(0, performanceSummary.confidence_signals))}%`,
                            }}
                          />
                        </div>
                        <p className="text-[10px] text-surface-400">Defense composure</p>
                      </div>
                    </div>

                    {performanceSummary.summary && (
                      <p className="text-xs text-surface-300 leading-relaxed pt-2 border-t border-surface-800/60">
                        {performanceSummary.summary}
                      </p>
                    )}

                    {performanceSummary.key_strengths && performanceSummary.key_strengths.length > 0 && (
                      <div className="pt-2 border-t border-surface-800/60 space-y-1.5">
                        <span className="text-[11px] font-bold text-emerald-400 uppercase tracking-wider block">
                          Key Strengths Observed
                        </span>
                        <ul className="text-xs text-surface-300 space-y-1 list-disc list-inside">
                          {performanceSummary.key_strengths.map((str, idx) => (
                            <li key={idx}>{str}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {performanceSummary.areas_for_improvement && performanceSummary.areas_for_improvement.length > 0 && (
                      <div className="pt-2 border-t border-surface-800/60 space-y-1.5">
                        <span className="text-[11px] font-bold text-amber-400 uppercase tracking-wider block">
                          Areas for Growth
                        </span>
                        <ul className="text-xs text-surface-300 space-y-1 list-disc list-inside">
                          {performanceSummary.areas_for_improvement.map((area, idx) => (
                            <li key={idx}>{area}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                {/* Agent 5 notice */}
                <div className="p-4 rounded-xl bg-gradient-to-r from-primary-950/40 via-surface-900 to-surface-950 border border-primary-500/30 text-left max-w-xl mx-auto flex items-start gap-3">
                  <span className="text-xl mt-0.5">⏳</span>
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <h3 className="text-xs font-bold text-primary-300 uppercase tracking-wider">
                        Final Combined Feedback Coming Soon
                      </h3>
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-primary-500/20 text-primary-300 border border-primary-500/30">
                        Agent 5
                      </span>
                    </div>
                    <p className="text-xs text-surface-300 leading-relaxed">
                      Agent 5 will synthesize your code submission (Agent 3) and your technical defense interview (Agent 4) into a unified final assessment.
                    </p>
                  </div>
                </div>

                <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
                  <button
                    onClick={() => navigate(`/interview/${taskId}`)}
                    className="w-full sm:w-auto px-6 py-3 rounded-xl bg-surface-800 hover:bg-surface-700 text-surface-200 text-sm font-semibold transition-colors"
                  >
                    View Interview Summary
                  </button>
                  <button
                    onClick={() => navigate('/tasks')}
                    className="w-full sm:w-auto px-8 py-3 rounded-xl bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-400 hover:to-emerald-500 text-white text-sm font-semibold transition-all shadow-lg shadow-emerald-500/20"
                  >
                    Return to Daily Tasks →
                  </button>
                </div>
              </div>
            ) : (
              /* ACTIVE QUESTION & ANSWER INTERFACE */
              <div className="space-y-6">
                {/* Question Card */}
                {currentTurn && (
                  <div className="p-6 sm:p-8 rounded-2xl bg-surface-900/70 border border-surface-800 backdrop-blur-xl space-y-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-lg bg-primary-500/15 border border-primary-500/25 flex items-center justify-center text-sm">
                          🤖
                        </div>
                        <span className="text-xs font-bold uppercase tracking-wider text-primary-400">
                          Interviewer
                        </span>
                        {isSpeaking && (
                          <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-primary-500/20 text-primary-300 border border-primary-500/30 text-[11px] font-semibold animate-pulse">
                            <span className="w-1.5 h-1.5 rounded-full bg-primary-400 animate-ping" />
                            Speaking...
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-2">
                        {/* Targeted skill/topic badge */}
                        {currentTurn.question_context &&
                          typeof currentTurn.question_context === 'object' &&
                          (currentTurn.question_context as { targeted_finding?: string; skill?: string }).targeted_finding && (
                            <span className="px-2.5 py-0.5 rounded-full text-xs bg-surface-800 text-surface-300 border border-surface-700">
                              Context: {(currentTurn.question_context as { targeted_finding?: string }).targeted_finding}
                            </span>
                          )}

                        {/* Voice Actions: Replay & Mute */}
                        {voiceSupported && (
                          <div className="flex items-center gap-1.5">
                            <button
                              type="button"
                              id="replay-question-btn"
                              onClick={handleReplayQuestion}
                              title="Replay Question Audio"
                              className="px-2.5 py-1 rounded-lg bg-surface-800 hover:bg-surface-700 text-surface-200 text-xs font-medium transition-colors flex items-center gap-1 border border-surface-700"
                            >
                              <span>🔊</span>
                              <span className="hidden sm:inline">Replay</span>
                            </button>
                            <button
                              type="button"
                              id="mute-toggle-btn"
                              onClick={toggleMute}
                              title={isMuted ? 'Unmute AI Voice' : 'Mute AI Voice'}
                              className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors flex items-center gap-1 border ${
                                isMuted
                                  ? 'bg-amber-500/15 text-amber-300 border-amber-500/30 hover:bg-amber-500/25'
                                  : 'bg-surface-800 text-surface-300 border-surface-700 hover:bg-surface-700'
                              }`}
                            >
                              <span>{isMuted ? '🔇' : '🔉'}</span>
                              <span className="hidden sm:inline">{isMuted ? 'Muted' : 'Sound On'}</span>
                            </button>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="pt-1">
                      <h2 className="text-lg sm:text-xl font-medium text-surface-50 leading-relaxed">
                        {currentTurn.question_text}
                      </h2>
                    </div>
                  </div>
                )}

                {/* Answer Composition Box */}
                <div className="p-5 sm:p-6 rounded-2xl bg-surface-900/50 border border-surface-800 space-y-4">
                  <div className="flex items-center justify-between text-xs text-surface-400">
                    <div className="flex items-center gap-2">
                      <label htmlFor="interview-answer-input" className="font-semibold text-surface-300">
                        Your Technical Defense Answer:
                      </label>
                      {voiceSupported && (
                        <span className="text-[11px] text-surface-500 hidden sm:inline">
                          (Voice powered by browser — works best on Chrome/Edge desktop)
                        </span>
                      )}
                    </div>
                    <span className="hidden sm:inline text-surface-500">
                      Press <kbd className="px-1.5 py-0.5 rounded bg-surface-800 text-surface-300 font-mono text-xs">Ctrl+Enter</kbd> to submit
                    </span>
                  </div>

                  {/* Voice Controls & Mic Status (Voice Mode) */}
                  {voiceSupported && (
                    <div className="flex flex-wrap items-center justify-between gap-2 p-2.5 rounded-xl bg-surface-950/60 border border-surface-800/80">
                      <div className="flex items-center gap-2">
                        {isListening ? (
                          <button
                            type="button"
                            id="stop-speaking-btn"
                            onClick={stopListening}
                            className="px-4 py-2 rounded-xl bg-red-500 hover:bg-red-600 text-white text-xs font-semibold flex items-center gap-2 shadow-lg shadow-red-500/20 animate-pulse transition-all"
                          >
                            <span className="w-2 h-2 rounded-full bg-white animate-ping" />
                            <span>⏹ Stop Listening</span>
                          </button>
                        ) : (
                          <button
                            type="button"
                            id="start-speaking-btn"
                            onClick={startListening}
                            disabled={isSubmitting}
                            className="px-4 py-2 rounded-xl bg-surface-800 hover:bg-surface-700 disabled:opacity-50 text-surface-200 text-xs font-semibold flex items-center gap-2 border border-surface-700 transition-all"
                          >
                            <span>🎤</span>
                            <span>Start Speaking</span>
                          </button>
                        )}

                        {isListening && (
                          <span className="text-xs text-red-300 font-medium flex items-center gap-1.5">
                            <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />
                            Listening... (speak clearly in en-IN)
                          </span>
                        )}
                      </div>

                      <span className="text-[11px] text-surface-500">
                        {isListening ? 'Speech populates textarea in real time' : 'Click to speak or type directly below'}
                      </span>
                    </div>
                  )}

                  {/* Live Interim Transcript Caption */}
                  {isListening && interimTranscript && (
                    <div className="p-2.5 rounded-lg bg-surface-950/80 border border-primary-500/30 text-xs text-primary-200 flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-primary-400 animate-ping" />
                      <span className="text-surface-400">Heard:</span>
                      <span className="italic font-medium">"{interimTranscript}"</span>
                    </div>
                  )}

                  {/* Microphone Permission / Recognition Error Alert */}
                  {micError && (
                    <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300 flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span>⚠️</span>
                        <span>{micError}</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setMicError(null)}
                        className="text-amber-400 hover:text-amber-300 text-xs font-semibold px-2 py-0.5 rounded hover:bg-amber-500/20"
                      >
                        Dismiss
                      </button>
                    </div>
                  )}

                  <textarea
                    id="interview-answer-input"
                    value={answerText}
                    onChange={(e) => setAnswerText(e.target.value)}
                    onKeyDown={handleKeyDown}
                    disabled={isSubmitting}
                    rows={6}
                    placeholder="Type or speak your explanation here. Be specific about your architecture, design trade-offs, and how you approached edge cases..."
                    className="w-full px-4 py-3 rounded-xl bg-surface-950/80 border border-surface-800 text-surface-100 placeholder:text-surface-600 focus:outline-none focus:ring-2 focus:ring-primary-500/50 text-sm leading-relaxed resize-y transition-all disabled:opacity-50"
                  />

                  <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-1">
                    <div className="text-xs text-surface-500 flex items-center gap-2">
                      <span>{answerText.trim().split(/\s+/).filter(Boolean).length} words</span>
                      <span>•</span>
                      <span>{answerText.length} characters</span>
                    </div>

                    <button
                      id="submit-answer-btn"
                      onClick={handleSubmitAnswer}
                      disabled={isSubmitting || !answerText.trim()}
                      className="w-full sm:w-auto px-8 py-3 rounded-xl bg-primary-600 hover:bg-primary-500 disabled:bg-surface-800 disabled:text-surface-500 disabled:cursor-not-allowed text-white font-semibold text-sm transition-all shadow-lg shadow-primary-500/20 flex items-center justify-center gap-2"
                    >
                      {isSubmitting ? (
                        <>
                          <div className="w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
                          <span>Interviewer is thinking...</span>
                        </>
                      ) : (
                        <>
                          <span>Submit Answer</span>
                          <span>→</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {/* Submitting Animation Notice */}
                {isSubmitting && (
                  <div className="p-4 rounded-xl bg-primary-500/10 border border-primary-500/20 text-center animate-pulse">
                    <p className="text-xs text-primary-300 font-medium">
                      The AI interviewer is evaluating your answer and formulating a targeted follow-up question...
                    </p>
                  </div>
                )}

                {/* Collapsible Turn History Transcript */}
                {turnHistory.some((t) => t.answer_text) && (
                  <details className="p-4 rounded-xl bg-surface-900/40 border border-surface-800/80 text-xs transition-all">
                    <summary className="font-semibold text-surface-400 cursor-pointer hover:text-surface-200">
                      View Previous Answers ({turnHistory.filter((t) => t.answer_text).length})
                    </summary>
                    <div className="space-y-3 pt-3">
                      {turnHistory
                        .filter((t) => t.answer_text)
                        .map((t) => (
                          <div
                            key={t.id}
                            className="p-3.5 rounded-lg bg-surface-950/70 border border-surface-800 space-y-1.5"
                          >
                            <p className="font-semibold text-primary-300">
                              Q{t.turn_number}: {t.question_text}
                            </p>
                            <p className="text-surface-200 whitespace-pre-wrap">{t.answer_text}</p>
                          </div>
                        ))}
                    </div>
                  </details>
                )}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
