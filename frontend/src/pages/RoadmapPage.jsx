import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import {
  MapPin,
  CheckCircle2,
  ArrowRight,
  Clock,
  Sparkles,
  Cpu,
  Layout,
  Check,
  Circle,
  Play,
  Award,
  TrendingUp,
  Layers,
  Briefcase,
  Code2,
  Star,
  Target,
  BookOpen,
  ShieldCheck,
} from 'lucide-react';
import PageHeader from '../components/PageHeader/PageHeader';
import Card from '../components/Card/Card';
import Button from '../components/Button/Button';
import Loader from '../components/Loader/Loader';
import EmptyState from '../components/EmptyState/EmptyState';
import roadmapService from '../services/roadmapService';
import onboardingService from '../services/onboardingService';
import dashboardService from '../services/dashboardService';

// Built-in rich milestone tracks for Machine Learning Engineer & Frontend Developer
const TRACK_DATA = {
  'machine-learning-engineer': {
    slug: 'machine-learning-engineer',
    title: 'Machine Learning Engineer',
    category: 'AI & Machine Learning',
    estimatedDuration: '16 Weeks',
    dailyCommitment: '1–2 Hours/day',
    averageSalary: '$130,000 - $175,000',
    targetLevel: 'Production MLOps Engineer',
    milestones: [
      {
        id: 'ml-m1',
        phase: 'Phase 1',
        title: 'Feature Engineering & Data Pipeline Optimization',
        duration: 'Weeks 1–4',
        status: 'In Progress',
        progressPercent: 0,
        skills: ['Python 3.11', 'Pandas', 'NumPy', 'SQL Analytics', 'Feature Scaling'],
        description: 'Transform raw data into high-performance ML feature tables. Clean missing values, encode categorical variables, and write automated ETL pipelines.',
        topics: [
          'Pandas Vectorized Data Transformations & Cleaning',
          'Feature Encoding (One-Hot, Target & Ordinal Encoding)',
          'Outlier Detection & IQR / Z-Score Filtering',
          'Automated Feature Store & ETL Pipeline Construction',
        ],
      },
      {
        id: 'ml-m2',
        phase: 'Phase 2',
        title: 'Predictive Modeling & Scikit-Learn Pipeline Tuning',
        duration: 'Weeks 5–8',
        status: 'Upcoming',
        progressPercent: 0,
        skills: ['Scikit-Learn', 'XGBoost', 'Cross-Validation', 'Hyper-Parameter Tuning'],
        description: 'Train supervised classification & regression models. Optimize hyper-parameters using GridSearchCV, evaluation metrics, and ROC-AUC curves.',
        topics: [
          'Supervised Classification (Logistic, Random Forest, XGBoost)',
          'Model Evaluation (Confusion Matrix, Precision, Recall, F1)',
          'Handling Class Imbalance with SMOTE & Class Weights',
          'ONNX Export & Model Artifact Serialization',
        ],
      },
      {
        id: 'ml-m3',
        phase: 'Phase 3',
        title: 'Deep Learning & Neural Network Architectures',
        duration: 'Weeks 9–12',
        status: 'Upcoming',
        progressPercent: 0,
        skills: ['PyTorch', 'TensorFlow', 'Deep Learning', 'Convolutional Networks'],
        description: 'Build neural networks from scratch in PyTorch. Implement custom loss functions, automatic differentiation, and image/text embeddings.',
        topics: [
          'PyTorch Tensors, Autograd & Custom Training Loops',
          'Multi-Layer Perceptrons & Backpropagation Math',
          'CNNs & Computer Vision Feature Extraction',
          'Transfer Learning with Pre-trained ResNet models',
        ],
      },
      {
        id: 'ml-m4',
        phase: 'Phase 4',
        title: 'Production MLOps, Model Registry & AI Mock Interviews',
        duration: 'Weeks 13–16',
        status: 'Upcoming',
        progressPercent: 0,
        skills: ['MLflow', 'FastAPI Serving', 'Docker', 'System Design', 'AI Mock Room'],
        description: 'Deploy trained ML models to production APIs via FastAPI, track experiments with MLflow, containerize with Docker, and ace AI mock interviews.',
        topics: [
          'MLflow Model Registry & Experiment Tracking',
          'FastAPI Asynchronous Inference API Endpoints',
          'Docker Containerization & Render/AWS Deployment',
          'Real-Time Voice AI Technical Mock Interview Practice',
        ],
      },
    ],
  },
  'frontend-developer': {
    slug: 'frontend-developer',
    title: 'Frontend Developer',
    category: 'Software Engineering',
    estimatedDuration: '12 Weeks',
    dailyCommitment: '1 Hour/day',
    averageSalary: '$100,000 - $140,000',
    targetLevel: 'Production Frontend Engineer',
    milestones: [
      {
        id: 'fe-m1',
        phase: 'Phase 1',
        title: 'Modern JavaScript ES6+ & DOM Architecture',
        duration: 'Weeks 1–3',
        status: 'In Progress',
        progressPercent: 0,
        skills: ['JavaScript ES6+', 'DOM API', 'Async/Await', 'HTML5', 'CSS Flexbox/Grid'],
        description: 'Master core JavaScript language concepts, asynchronous promises, DOM manipulation, and responsive CSS layout design.',
        topics: [
          'ES6+ Features (Destructuring, Arrow Functions, Modules)',
          'Async/Await, Fetch API & HTTP Protocol Fundamentals',
          'Responsive CSS Layouts with Flexbox & Grid',
          'DOM Event Delegation & Event Loop Mechanics',
        ],
      },
      {
        id: 'fe-m2',
        phase: 'Phase 2',
        title: 'React 18 & Component-Driven Architecture',
        duration: 'Weeks 4–7',
        status: 'Upcoming',
        progressPercent: 0,
        skills: ['React 18', 'JSX', 'State Hooks', 'Custom Hooks', 'Component Styling'],
        description: 'Build modular, reusable React component systems with state hooks, prop validation, side effects, and clean code principles.',
        topics: [
          'React Component Tree & JSX Rendering Rules',
          'State Management with useState & useEffect Hooks',
          'Custom Hooks Creation for Reusable UI Logic',
          'Form Control & React Hook Form Integration',
        ],
      },
      {
        id: 'fe-m3',
        phase: 'Phase 3',
        title: 'State Management, REST APIs & Routing',
        duration: 'Weeks 8–10',
        status: 'Upcoming',
        progressPercent: 0,
        skills: ['React Router v7', 'Context API', 'Axios', 'REST APIs', 'Error Boundaries'],
        description: 'Integrate production REST APIs using Axios, single-page app routing with React Router, Context API state management, and global toast alerts.',
        topics: [
          'React Router v7 Protected & Public Route Pipelines',
          'Context API for Global Auth & Theme State Management',
          'Axios Interceptors & JWT Auth Token Management',
          'Optimistic UI Updates & Error State Handling',
        ],
      },
      {
        id: 'fe-m4',
        phase: 'Phase 4',
        title: 'Vite Build Optimization & AI Technical Interviews',
        duration: 'Weeks 11–12',
        status: 'Upcoming',
        progressPercent: 0,
        skills: ['Vite Optimization', 'Performance', 'System Design', 'AI Mock Room'],
        description: 'Optimize bundle size, implement code splitting, audit accessibility (a11y), and complete real-time AI technical mock interviews.',
        topics: [
          'Vite Bundle Optimization & Lazy Loading Code Splitting',
          'Web Performance Core Web Vitals Optimization',
          'Frontend System Design & Component Mockups',
          'AI Mock Interview Room Voice Simulation',
        ],
      },
    ],
  },
};

export const RoadmapPage = () => {
  const [searchParams] = useSearchParams();
  const professionParam = searchParams.get('profession_id') || searchParams.get('profession') || 'machine-learning-engineer';

  const [activeTrack, setActiveTrack] = useState('machine-learning-engineer');
  const [userProgressData, setUserProgressData] = useState(null);

  useEffect(() => {
    if (professionParam.includes('front') || professionParam === 'frontend-developer') {
      setActiveTrack('frontend-developer');
    } else {
      setActiveTrack('machine-learning-engineer');
    }
  }, [professionParam]);

  useEffect(() => {
    const fetchUserProgress = async () => {
      try {
        const data = await dashboardService.getStudentDashboard();
        setUserProgressData(data?.progress || null);
      } catch {
        setUserProgressData(null);
      }
    };
    fetchUserProgress();
  }, []);

  const currentTrackData = TRACK_DATA[activeTrack] || TRACK_DATA['machine-learning-engineer'];
  const rawMilestones = currentTrackData.milestones;

  // Real completed tasks count from DB (0 if new learner)
  const completedTasks = userProgressData?.completed_tasks || 0;
  const dbOverallProgress = userProgressData?.overall_progress_percentage || 0;

  // Dynamically update milestone statuses based on real completed tasks
  const milestones = rawMilestones.map((m, idx) => {
    if (completedTasks === 0) {
      if (idx === 0) return { ...m, status: 'In Progress', progressPercent: 0 };
      return { ...m, status: 'Upcoming', progressPercent: 0 };
    }

    if (completedTasks >= (idx + 1) * 2) {
      return { ...m, status: 'Completed', progressPercent: 100 };
    } else if (completedTasks > idx * 2) {
      return { ...m, status: 'In Progress', progressPercent: 50 };
    } else {
      return { ...m, status: 'Upcoming', progressPercent: 0 };
    }
  });

  // Calculate real overall track progress percentage
  const completedCount = milestones.filter((m) => m.status === 'Completed').length;
  const inProgressMilestone = milestones.find((m) => m.status === 'In Progress');
  const inProgressPct = inProgressMilestone ? inProgressMilestone.progressPercent : 0;

  const overallTrackProgress =
    completedTasks === 0
      ? 0
      : Math.round(((completedCount * 100 + inProgressPct) / (milestones.length * 100)) * 100);

  return (
    <div>
      <PageHeader
        title="Career Learning Roadmap"
        description="Interactive step-by-step pathway engineered to take you from foundational concepts to production career mastery."
        breadcrumbs={[{ label: 'Roadmap' }]}
      />

      {/* 1. CAREER TRACK SWITCHER TABS */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.5rem' }}>
        <div className="track-tab-bar">
          <button
            className={`track-tab-item ${activeTrack === 'machine-learning-engineer' ? 'active' : ''}`}
            onClick={() => setActiveTrack('machine-learning-engineer')}
          >
            <Cpu size={18} /> Machine Learning Engineer
          </button>
          <button
            className={`track-tab-item ${activeTrack === 'frontend-developer' ? 'active' : ''}`}
            onClick={() => setActiveTrack('frontend-developer')}
          >
            <Layout size={18} /> Frontend Developer
          </button>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span className="badge-pill badge-primary">
            <Sparkles size={12} /> {currentTrackData.category}
          </span>
        </div>
      </div>

      {/* 2. CAREER OUTCOME OVERVIEW BANNER */}
      <Card className="dashboard-hero" style={{ padding: '1.75rem', marginBottom: '2rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1.5rem' }}>
          <div>
            <span className="badge-pill badge-emerald" style={{ marginBottom: '0.5rem' }}>
              <CheckCircle2 size={12} /> ACTIVE CAREER PATHWAY
            </span>
            <h2 style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--text-main)', fontFamily: 'var(--font-heading)' }}>
              {currentTrackData.title} Roadmap
            </h2>
            <p style={{ fontSize: '0.9375rem', color: 'var(--text-muted)', marginTop: '0.25rem', maxWidth: '650px' }}>
              Target Role: <strong>{currentTrackData.targetLevel}</strong> • Industry Salary Range: <strong>{currentTrackData.averageSalary}</strong>
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', flexWrap: 'wrap' }}>
            <div style={{ textAlign: 'right' }}>
              <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Overall Track Progress</span>
              <h3 style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--accent-emerald)', fontFamily: 'var(--font-heading)' }}>
                {overallTrackProgress}%
              </h3>
            </div>

            <Button variant="primary" icon={Play} onClick={() => navigate('/tasks')}>
              Start Active Tasks
            </Button>
          </div>
        </div>
      </Card>

      {/* 3. NODE-CONNECTED INTERACTIVE TIMELINE */}
      <div style={{ marginBottom: '2.5rem' }}>
        <h3 style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--text-main)', fontFamily: 'var(--font-heading)', marginBottom: '0.5rem' }}>
          Milestone Phases & Learning Pathway
        </h3>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1.5rem' }}>
          Complete each phase's practical tasks and code exercises to advance to the next milestone.
        </p>

        <div className="roadmap-timeline">
          {milestones.map((m, idx) => {
            const statusClass =
              m.status === 'Completed'
                ? 'status-completed'
                : m.status === 'In Progress'
                ? 'status-in-progress'
                : 'status-upcoming';

            return (
              <div key={m.id} className={`timeline-item ${statusClass}`}>
                {/* Node Circle */}
                <div className="timeline-node-circle">
                  {m.status === 'Completed' ? <Check size={18} /> : idx + 1}
                </div>

                {/* Glass Milestone Card */}
                <Card
                  style={{
                    borderLeft: `4px solid ${
                      m.status === 'Completed'
                        ? 'var(--accent-emerald)'
                        : m.status === 'In Progress'
                        ? 'var(--primary)'
                        : 'var(--border-light)'
                    }`,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem', marginBottom: '0.75rem' }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
                        <span className="badge-pill badge-primary">{m.phase}</span>
                        <span className="badge-pill badge-cyan">
                          <Clock size={12} /> {m.duration}
                        </span>
                        <span className={`badge-pill ${m.status === 'Completed' ? 'badge-emerald' : m.status === 'In Progress' ? 'badge-amber' : 'badge-primary'}`}>
                          {m.status}
                        </span>
                      </div>

                      <h4 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-main)', fontFamily: 'var(--font-heading)' }}>
                        {m.title}
                      </h4>
                    </div>

                    {m.status === 'In Progress' && (
                      <span className="badge-pill badge-emerald" style={{ fontSize: '0.85rem' }}>
                        <TrendingUp size={14} /> Active Phase ({m.progressPercent}%)
                      </span>
                    )}
                  </div>

                  <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', lineHeight: 1.6, marginBottom: '1rem' }}>
                    {m.description}
                  </p>

                  {/* Target Skills Pills */}
                  <div style={{ marginBottom: '1.25rem' }}>
                    <p style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-dim)', marginBottom: '0.4rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      Target Skills Acquired
                    </p>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                      {m.skills.map((sk, sIdx) => (
                        <span key={sIdx} className="skill-tag">
                          <Code2 size={13} style={{ color: 'var(--primary)' }} /> {sk}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Itemized Key Topics Checklist */}
                  <div style={{ paddingTop: '1rem', borderTop: '1px solid var(--border-subtle)' }}>
                    <p style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      <BookOpen size={14} style={{ color: 'var(--accent-cyan)' }} /> Key Modules & Topic Coverage
                    </p>
                    <div className="topic-check-grid">
                      {m.topics.map((t, tIdx) => (
                        <div key={tIdx} className="topic-check-item">
                          <CheckCircle2 size={14} style={{ color: m.status === 'Completed' ? 'var(--accent-emerald)' : 'var(--primary)', flexShrink: 0 }} />
                          <span>{t}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Action Button */}
                  <div style={{ marginTop: '1.25rem', display: 'flex', justifyContent: 'flex-end' }}>
                    <Button
                      variant={m.status === 'In Progress' ? 'primary' : 'secondary'}
                      size="sm"
                      icon={ArrowRight}
                      onClick={() => navigate('/tasks')}
                    >
                      {m.status === 'Completed' ? 'Review Phase Exercises' : 'Start Phase Tasks'}
                    </Button>
                  </div>
                </Card>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default RoadmapPage;

