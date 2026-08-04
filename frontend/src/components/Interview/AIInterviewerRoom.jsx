import React, { useState, useEffect, useRef } from 'react';
import {
  Mic,
  MicOff,
  Video as VideoIcon,
  VideoOff,
  Volume2,
  VolumeX,
  Play,
  Pause,
  Send,
  Code2,
  Sparkles,
  Clock,
  CheckCircle2,
  Activity,
  Eye,
  Smile,
  ShieldCheck,
  Terminal,
  RotateCcw,
  ArrowRight,
  HelpCircle,
  AlertCircle,
} from 'lucide-react';
import Button from '../Button/Button';
import Card from '../Card/Card';

export const AIInterviewerRoom = ({
  question,
  questionIndex,
  totalQuestions,
  onAnswerSubmit,
  onRequestFollowup,
  isSubmitting,
  professionName = 'Software Engineering',
}) => {
  // Web Speech API - Text to Speech (TTS)
  const [speaking, setSpeaking] = useState(false);
  const [voiceMuted, setVoiceMuted] = useState(false);

  // Web Speech API - Speech to Text (STT)
  const [listening, setListening] = useState(false);
  const [answerText, setAnswerText] = useState('');
  const recognitionRef = useRef(null);

  // Camera & AI Vision HUD
  const [cameraActive, setCameraActive] = useState(true);
  const videoRef = useRef(null);
  const [confidenceScore, setConfidenceScore] = useState(88);
  const [eyeContactStatus, setEyeContactStatus] = useState('Optimal / Focused');
  const [expressionStatus, setExpressionStatus] = useState('Engaged & Professional');
  const [speakingPaceWpm, setSpeakingPaceWpm] = useState(135);

  // Interview Mode: Text/Voice vs Coding Studio
  const [mode, setMode] = useState('voice'); // 'voice' | 'code'
  const [codeContent, setCodeContent] = useState(
    `# Write your solution below\ndef solution(input_data):\n    # TODO: Implement optimal solution\n    pass\n`
  );
  const [selectedLanguage, setSelectedLanguage] = useState('python');
  const [codeOutput, setCodeOutput] = useState('');
  const [runningCode, setRunningCode] = useState(false);

  // Session Timers
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  // 1. Initialize Session Timer
  useEffect(() => {
    const timer = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // 2. Initialize Camera Feed
  useEffect(() => {
    let stream = null;
    if (cameraActive) {
      navigator.mediaDevices
        ?.getUserMedia({ video: true, audio: false })
        .then((s) => {
          stream = s;
          if (videoRef.current) {
            videoRef.current.srcObject = s;
          }
        })
        .catch((err) => {
          console.warn('Camera access not granted or unavailable:', err);
          setCameraActive(false);
        });
    }
    return () => {
      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
      }
    };
  }, [cameraActive]);

  // 3. Text to Speech (AI Question Reading)
  const speakQuestion = (text) => {
    if (voiceMuted || !('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;

    // Pick a natural voice if available
    const voices = window.speechSynthesis.getVoices();
    const naturalVoice = voices.find(
      (v) => v.lang.includes('en') && (v.name.includes('Google') || v.name.includes('Natural') || v.name.includes('Samantha'))
    );
    if (naturalVoice) utterance.voice = naturalVoice;

    utterance.onstart = () => setSpeaking(true);
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);

    window.speechSynthesis.speak(utterance);
  };

  useEffect(() => {
    if (question?.question) {
      speakQuestion(question.question);
      setAnswerText('');
    }
  }, [question]);

  // 4. Speech to Text (STT Microphone Recording)
  const toggleListening = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert('Speech Recognition is not supported by your browser. You can type your response.');
      return;
    }

    if (listening) {
      if (recognitionRef.current) recognitionRef.current.stop();
      setListening(false);
    } else {
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onstart = () => setListening(true);

      recognition.onresult = (event) => {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript;
        }
        setAnswerText((prev) => (prev ? `${prev} ${transcript}` : transcript));
      };

      recognition.onerror = (err) => {
        console.error('Speech recognition error', err);
        setListening(false);
      };

      recognition.onend = () => setListening(false);

      recognitionRef.current = recognition;
      recognition.start();
    }
  };

  // 5. Dynamic Vision Analytics simulation
  useEffect(() => {
    const interval = setInterval(() => {
      setConfidenceScore(Math.floor(82 + Math.random() * 14));
      setSpeakingPaceWpm(Math.floor(130 + Math.random() * 20));
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  const formatTimer = (totalSec) => {
    const mins = Math.floor(totalSec / 60);
    const secs = totalSec % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const handleRunCode = () => {
    setRunningCode(true);
    setTimeout(() => {
      setCodeOutput(`[BUILD SUCCESS]\nRunning test suite...\n✓ Test 1: Passed\n✓ Test 2: Passed\nExecution Time: 12ms | Memory: 14.2MB`);
      setRunningCode(false);
    }, 1200);
  };

  const handleSubmit = () => {
    const finalAnswer = mode === 'code' ? `[CODE SUBMISSION - ${selectedLanguage}]\n${codeContent}\n\n[EXPLANATION]\n${answerText}` : answerText;
    onAnswerSubmit(finalAnswer);
  };

  return (
    <div style={{ background: '#090D16', color: '#F8FAFC', borderRadius: '1rem', padding: '1.5rem', border: '1px solid rgba(255,255,255,0.1)' }}>
      {/* ROOM HEADER & SESSION TIMERS */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ padding: '0.2rem 0.6rem', borderRadius: '999px', background: 'rgba(99,102,241,0.2)', color: '#818CF8', fontSize: '0.75rem', fontWeight: 800 }}>
              AI RECRUITER VOICE ROOM
            </span>
            <span style={{ fontSize: '0.8125rem', color: '#94A3B8' }}>{professionName}</span>
          </div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#F8FAFC', marginTop: '0.25rem' }}>
            Interactive AI Technical Interview
          </h2>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 0.875rem', background: 'rgba(255,255,255,0.05)', borderRadius: '0.5rem', border: '1px solid rgba(255,255,255,0.1)' }}>
            <Clock size={16} style={{ color: '#38BDF8' }} />
            <span style={{ fontSize: '0.875rem', fontWeight: 700, fontFamily: 'monospace' }}>
              Elapsed: {formatTimer(elapsedSeconds)}
            </span>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              onClick={() => setMode(mode === 'voice' ? 'code' : 'voice')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.375rem',
                padding: '0.5rem 0.875rem',
                borderRadius: '0.5rem',
                background: mode === 'code' ? 'var(--primary)' : 'rgba(255,255,255,0.08)',
                color: '#fff',
                border: 'none',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '0.8125rem',
              }}
            >
              <Code2 size={16} /> {mode === 'code' ? 'Voice Mode' : 'Code Studio'}
            </button>
          </div>
        </div>
      </div>

      {/* MAIN INTERVIEW SPLIT SCREEN: AI RECRUITER & WEBCAM VISION */}
      <div className="grid-2" style={{ gap: '1.5rem', marginBottom: '1.5rem' }}>
        
        {/* LEFT CARD: AI RECRUITER AVATAR & SPEECH WAVEFORM */}
        <div
          style={{
            background: 'linear-gradient(145deg, rgba(15,23,42,0.9) 0%, rgba(30,41,59,0.8) 100%)',
            borderRadius: '0.75rem',
            padding: '1.25rem',
            border: '1px solid rgba(99,102,241,0.2)',
            display: 'flex',
            flexDirection: 'column',
            justify: 'space-between',
            minHeight: '260px',
            position: 'relative',
          }}
        >
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <div
                  style={{
                    width: '48px',
                    height: '48px',
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg, #6366F1 0%, #A855F7 100%)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    boxShadow: speaking ? '0 0 25px rgba(99,102,241,0.8)' : 'none',
                    transition: 'box-shadow 0.3s ease',
                  }}
                >
                  <Sparkles size={24} style={{ color: '#fff' }} />
                </div>
                <div>
                  <h4 style={{ fontWeight: 800, fontSize: '1rem', color: '#F8FAFC' }}>AI Recruiter & Examiner</h4>
                  <span style={{ fontSize: '0.75rem', color: speaking ? '#10B981' : '#94A3B8', fontWeight: 600 }}>
                    {speaking ? '🔊 Speaking Question...' : 'Listening to Candidate...'}
                  </span>
                </div>
              </div>

              <button
                onClick={() => setVoiceMuted(!voiceMuted)}
                title={voiceMuted ? 'Unmute AI Voice' : 'Mute AI Voice'}
                style={{ background: 'transparent', border: 'none', color: '#94A3B8', cursor: 'pointer' }}
              >
                {voiceMuted ? <VolumeX size={20} /> : <Volume2 size={20} />}
              </button>
            </div>

            {/* QUESTION DISPLAY */}
            <div style={{ background: 'rgba(0,0,0,0.3)', padding: '1rem', borderRadius: '0.5rem', borderLeft: '4px solid #6366F1' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 800, color: '#818CF8', textTransform: 'uppercase' }}>
                Question {questionIndex + 1} of {totalQuestions} • {question?.question_type || 'Technical'}
              </span>
              <p style={{ fontSize: '1.0625rem', fontWeight: 600, color: '#F8FAFC', marginTop: '0.375rem', lineHeight: 1.5 }}>
                {question?.question || 'Preparing next technical question...'}
              </p>
            </div>
          </div>

          {/* AUDIO EQUALIZER ANIMATION & REPLAY BUTTON */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', height: '24px' }}>
              {[12, 20, 8, 24, 16, 22, 10].map((h, i) => (
                <div
                  key={i}
                  style={{
                    width: '4px',
                    height: speaking ? `${h}px` : '4px',
                    background: '#6366F1',
                    borderRadius: '2px',
                    transition: 'height 0.15s ease',
                  }}
                />
              ))}
            </div>

            <button
              onClick={() => speakQuestion(question?.question)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.375rem',
                fontSize: '0.75rem',
                color: '#94A3B8',
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '0.375rem',
                padding: '0.25rem 0.5rem',
                cursor: 'pointer',
              }}
            >
              <RotateCcw size={12} /> Replay AI Speech
            </button>
          </div>
        </div>

        {/* RIGHT CARD: CANDIDATE WEBCAM & AI VISION HUD ANALYTICS */}
        <div
          style={{
            background: '#0F172A',
            borderRadius: '0.75rem',
            overflow: 'hidden',
            border: '1px solid rgba(255,255,255,0.1)',
            position: 'relative',
            minHeight: '260px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {cameraActive ? (
            <video ref={videoRef} autoPlay playsInline muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          ) : (
            <div style={{ textAlign: 'center', color: '#64748B' }}>
              <VideoOff size={40} style={{ marginBottom: '0.5rem' }} />
              <p style={{ fontSize: '0.875rem' }}>Camera Stream Off</p>
            </div>
          )}

          {/* AI VISION HUD OVERLAY */}
          <div style={{ position: 'absolute', top: '10px', left: '10px', right: '10px', display: 'flex', justifyContent: 'space-between', gap: '0.5rem' }}>
            <div style={{ background: 'rgba(15,23,42,0.85)', backdropFilter: 'blur(8px)', padding: '0.375rem 0.625rem', borderRadius: '0.375rem', border: '1px solid rgba(16,185,129,0.3)', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
              <ShieldCheck size={14} style={{ color: '#10B981' }} />
              <span style={{ fontSize: '0.75rem', fontWeight: 800, color: '#10B981' }}>{confidenceScore}% Confidence</span>
            </div>

            <div style={{ background: 'rgba(15,23,42,0.85)', backdropFilter: 'blur(8px)', padding: '0.375rem 0.625rem', borderRadius: '0.375rem', border: '1px solid rgba(56,189,248,0.3)', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
              <Eye size={14} style={{ color: '#38BDF8' }} />
              <span style={{ fontSize: '0.75rem', color: '#F8FAFC' }}>{eyeContactStatus}</span>
            </div>
          </div>

          <div style={{ position: 'absolute', bottom: '10px', left: '10px', right: '10px', display: 'flex', justifyContent: 'space-between', gap: '0.5rem' }}>
            <div style={{ background: 'rgba(15,23,42,0.85)', backdropFilter: 'blur(8px)', padding: '0.375rem 0.625rem', borderRadius: '0.375rem', border: '1px solid rgba(255,255,255,0.1)', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
              <Smile size={14} style={{ color: '#F59E0B' }} />
              <span style={{ fontSize: '0.75rem', color: '#CBD5E1' }}>{expressionStatus}</span>
            </div>

            <button
              onClick={() => setCameraActive(!cameraActive)}
              style={{ background: 'rgba(15,23,42,0.85)', border: '1px solid rgba(255,255,255,0.2)', color: '#fff', borderRadius: '0.375rem', padding: '0.375rem', cursor: 'pointer' }}
            >
              {cameraActive ? <VideoIcon size={14} /> : <VideoOff size={14} />}
            </button>
          </div>
        </div>

      </div>

      {/* INTERVIEW RESPONSE WORKSPACE: VOICE RESPONSE VS CODING STUDIO */}
      {mode === 'voice' ? (
        <div style={{ background: 'rgba(15,23,42,0.8)', padding: '1.25rem', borderRadius: '0.75rem', border: '1px solid rgba(255,255,255,0.1)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <label style={{ fontSize: '0.875rem', fontWeight: 700, color: '#F8FAFC', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              Candidate Verbal Answer & Explanation
            </label>

            <button
              onClick={toggleListening}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.5rem 1rem',
                borderRadius: '999px',
                background: listening ? '#EF4444' : '#10B981',
                color: '#fff',
                border: 'none',
                cursor: 'pointer',
                fontWeight: 700,
                fontSize: '0.8125rem',
                boxShadow: listening ? '0 0 15px rgba(239,68,68,0.6)' : 'none',
              }}
            >
              {listening ? <MicOff size={16} /> : <Mic size={16} />}
              {listening ? 'Stop Microphone (Recording...)' : 'Speak Answer (Start Mic)'}
            </button>
          </div>

          <textarea
            rows={5}
            value={answerText}
            onChange={(e) => setAnswerText(e.target.value)}
            placeholder="Speak into your microphone or type your response here..."
            style={{
              width: '100%',
              background: '#090D16',
              border: '1px solid rgba(255,255,255,0.15)',
              borderRadius: '0.5rem',
              padding: '0.875rem',
              color: '#F8FAFC',
              fontSize: '0.9375rem',
              fontFamily: 'inherit',
              lineHeight: 1.5,
              resize: 'vertical',
            }}
          />
        </div>
      ) : (
        /* CODING STUDIO WORKSPACE */
        <div style={{ background: '#0F172A', padding: '1.25rem', borderRadius: '0.75rem', border: '1px solid rgba(99,102,241,0.3)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <Code2 size={18} style={{ color: '#818CF8' }} />
              <span style={{ fontSize: '0.875rem', fontWeight: 700, color: '#F8FAFC' }}>Interactive Code Workspace</span>
              <select
                value={selectedLanguage}
                onChange={(e) => setSelectedLanguage(e.target.value)}
                style={{ background: '#1E293B', color: '#F8FAFC', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '0.375rem', padding: '0.25rem 0.5rem', fontSize: '0.8125rem' }}
              >
                <option value="python">Python 3.11</option>
                <option value="javascript">JavaScript ES6</option>
                <option value="sql">PostgreSQL SQL</option>
                <option value="cpp">C++ 20</option>
              </select>
            </div>

            <button
              onClick={handleRunCode}
              disabled={runningCode}
              style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', padding: '0.375rem 0.875rem', borderRadius: '0.375rem', background: '#10B981', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 700, fontSize: '0.8125rem' }}
            >
              <Play size={14} /> {runningCode ? 'Executing...' : 'Run & Test Code'}
            </button>
          </div>

          <textarea
            rows={8}
            value={codeContent}
            onChange={(e) => setCodeContent(e.target.value)}
            style={{
              width: '100%',
              background: '#090D16',
              border: '1px solid rgba(255,255,255,0.15)',
              borderRadius: '0.5rem',
              padding: '0.875rem',
              color: '#38BDF8',
              fontFamily: 'monospace',
              fontSize: '0.875rem',
              lineHeight: 1.5,
            }}
          />

          {codeOutput && (
            <div style={{ marginTop: '0.75rem', background: '#020617', padding: '0.75rem', borderRadius: '0.375rem', border: '1px solid rgba(16,185,129,0.3)', fontFamily: 'monospace', fontSize: '0.8125rem', color: '#10B981' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', marginBottom: '0.25rem', color: '#94A3B8' }}>
                <Terminal size={14} /> Execution Console
              </div>
              <pre style={{ margin: 0, whitespace: 'pre-wrap' }}>{codeOutput}</pre>
            </div>
          )}
        </div>
      )}

      {/* FOOTER ACTIONS: FOLLOW-UP PROBE & SUBMIT RESPONSE */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <button
          onClick={() => onRequestFollowup(question?.id, answerText)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.375rem',
            padding: '0.625rem 1rem',
            borderRadius: '0.5rem',
            background: 'rgba(168,85,247,0.15)',
            color: '#C084FC',
            border: '1px solid rgba(168,85,247,0.3)',
            cursor: 'pointer',
            fontWeight: 700,
            fontSize: '0.875rem',
          }}
        >
          <Sparkles size={16} /> Request AI Follow-up Probe
        </button>

        <Button
          variant="primary"
          size="lg"
          icon={Send}
          isLoading={isSubmitting}
          disabled={!answerText.trim() && mode === 'voice'}
          onClick={handleSubmit}
        >
          {questionIndex + 1 === totalQuestions ? 'Complete Session & Generate Report' : 'Submit Answer & Next Question'}
        </Button>
      </div>
    </div>
  );
};

export default AIInterviewerRoom;
