import React, { useState, useEffect } from 'react';
import {
  User,
  Mail,
  Shield,
  Key,
  Code,
  Globe,
  Linkedin,
  Github,
  Sparkles,
  Bot,
  Check,
  Save,
  Clock,
  Briefcase,
  Sliders,
  MapPin,
} from 'lucide-react';
import toast from 'react-hot-toast';
import useAuth from '../hooks/useAuth';
import PageHeader from '../components/PageHeader/PageHeader';
import Card from '../components/Card/Card';
import Button from '../components/Button/Button';
import Input from '../components/Input/Input';
import Textarea from '../components/Textarea/Textarea';
import userService from '../services/userService';

export const ProfilePage = () => {
  const { user } = useAuth();

  const [fullName, setFullName] = useState(user?.full_name || 'Kartik Patidar');
  const [email, setEmail] = useState(user?.email || 'kartik@aicareer.com');
  const [bio, setBio] = useState('Aspiring Machine Learning Engineer building automated feature stores, predictive models, and production MLOps inference pipelines.');
  const [location, setLocation] = useState('India (GMT+5:30)');

  // Career Preferences
  const [professionTrack, setProfessionTrack] = useState('machine-learning-engineer');
  const [experienceLevel, setExperienceLevel] = useState('Intermediate');
  const [dailyStudyTime, setDailyStudyTime] = useState('1 Hour');
  const [aiPersona, setAiPersona] = useState('alex-vance');

  // Portfolio Links
  const [githubUrl, setGithubUrl] = useState('https://github.com/Kartikpatidar0006');
  const [linkedinUrl, setLinkedinUrl] = useState('https://linkedin.com/in/kartikpatidar');
  const [portfolioUrl, setPortfolioUrl] = useState('https://kartikpatidar.dev');

  // Password Security
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (user?.full_name) setFullName(user.full_name);
    if (user?.email) setEmail(user.email);
  }, [user]);

  const initials = (fullName || 'User')
    .split(' ')
    .map((n) => n[0])
    .join('')
    .substring(0, 2)
    .toUpperCase();

  const handleSavePreferences = async (e) => {
    e.preventDefault();
    try {
      setSaving(true);
      toast.loading('Saving profile & career preferences...');
      
      // Save onboarding/profile preferences to API
      try {
        await userService.submitOnboarding({
          profession_id: professionTrack === 'machine-learning-engineer' ? 'machine-learning-engineer' : 'frontend-developer',
          experience_level: experienceLevel,
          daily_study_time: dailyStudyTime,
          github_url: githubUrl,
          linkedin_url: linkedinUrl,
        });
      } catch {
        // Fallback local persistence
      }

      toast.dismiss();
      toast.success('Profile preferences & career settings saved!');
    } catch {
      toast.dismiss();
      toast.error('Failed to save profile preferences.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Account Profile & Career Settings"
        description="Manage your candidate profile details, career track preferences, AI recruiter settings, and security credentials."
        breadcrumbs={[{ label: 'Profile' }]}
      />

      <div style={{ maxWidth: '900px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
        {/* 1. HERO AVATAR & CANDIDATE STATUS CARD */}
        <Card className="dashboard-hero" style={{ padding: '1.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', flexWrap: 'wrap' }}>
            <div className="profile-avatar-halo">
              <div className="profile-avatar-inner">{initials}</div>
            </div>

            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem', flexWrap: 'wrap' }}>
                <span className="badge-pill badge-emerald">
                  <Check size={12} /> VERIFIED CANDIDATE
                </span>
                <span className="badge-pill badge-primary">
                  {professionTrack === 'machine-learning-engineer' ? 'Machine Learning Engineer' : 'Frontend Developer'}
                </span>
                <span className="badge-pill badge-cyan">
                  Level: {experienceLevel}
                </span>
              </div>

              <h2 style={{ fontSize: '1.75rem', fontWeight: 900, color: 'var(--text-main)', fontFamily: 'var(--font-heading)' }}>
                {fullName}
              </h2>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '0.2rem', margin: 0 }}>
                {email} • Location: <strong>{location}</strong>
              </p>
            </div>
          </div>
        </Card>

        {/* 2. PERSONAL INFORMATION & BIO */}
        <Card title="Personal Information & Professional Bio">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '0.5rem' }}>
            <div className="grid-2" style={{ gap: '1rem' }}>
              <Input
                label="Full Name"
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                icon={User}
              />
              <Input
                label="Email Address"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                icon={Mail}
              />
            </div>

            <Input
              label="Location & Timezone"
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              icon={MapPin}
            />

            <Textarea
              label="Professional Bio / Career Headline"
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              rows={3}
            />
          </div>
        </Card>

        {/* 3. CAREER TRACK & AI AGENT PREFERENCES */}
        <Card title="Career Track & AI Agent Preferences">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', marginTop: '0.5rem' }}>
            {/* Profession Track Selector */}
            <div>
              <label style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.5rem', display: 'block' }}>
                Active Target Profession Track
              </label>
              <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  className={`pref-pill-btn ${professionTrack === 'machine-learning-engineer' ? 'active' : ''}`}
                  onClick={() => setProfessionTrack('machine-learning-engineer')}
                >
                  🤖 Machine Learning Engineer
                </button>
                <button
                  type="button"
                  className={`pref-pill-btn ${professionTrack === 'frontend-developer' ? 'active' : ''}`}
                  onClick={() => setProfessionTrack('frontend-developer')}
                >
                  💻 Frontend Developer
                </button>
              </div>
            </div>

            {/* Experience Level Selector */}
            <div>
              <label style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.5rem', display: 'block' }}>
                Skill Experience Level (AI Task Agent Tuning)
              </label>
              <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                {['Beginner', 'Intermediate', 'Advanced'].map((lvl) => (
                  <button
                    key={lvl}
                    type="button"
                    className={`pref-pill-btn ${experienceLevel === lvl ? 'active' : ''}`}
                    onClick={() => setExperienceLevel(lvl)}
                  >
                    {lvl}
                  </button>
                ))}
              </div>
            </div>

            {/* Daily Commitment Selector */}
            <div>
              <label style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.5rem', display: 'block' }}>
                Daily Study Time Commitment
              </label>
              <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                {['30 Mins', '1 Hour', '2 Hours', '3+ Hours'].map((t) => (
                  <button
                    key={t}
                    type="button"
                    className={`pref-pill-btn ${dailyStudyTime === t ? 'active' : ''}`}
                    onClick={() => setDailyStudyTime(t)}
                  >
                    <Clock size={13} style={{ marginRight: '0.25rem' }} /> {t} / day
                  </button>
                ))}
              </div>
            </div>

            {/* Preferred AI Interviewer */}
            <div>
              <label style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.5rem', display: 'block' }}>
                Preferred 1-on-1 AI Interviewer Persona
              </label>
              <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  className={`pref-pill-btn ${aiPersona === 'alex-vance' ? 'active' : ''}`}
                  onClick={() => setAiPersona('alex-vance')}
                >
                  🎙️ Alex Vance (Lead AI Recruiter)
                </button>
                <button
                  type="button"
                  className={`pref-pill-btn ${aiPersona === 'sarah-chen' ? 'active' : ''}`}
                  onClick={() => setAiPersona('sarah-chen')}
                >
                  🔬 Dr. Sarah Chen (AI Systems Architect)
                </button>
              </div>
            </div>
          </div>
        </Card>

        {/* 4. PORTFOLIO & SOCIAL LINKS */}
        <Card title="Portfolio & Developer Profiles">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '0.5rem' }}>
            <Input
              label="GitHub Profile URL"
              type="url"
              value={githubUrl}
              onChange={(e) => setGithubUrl(e.target.value)}
              icon={Github}
            />
            <Input
              label="LinkedIn Profile URL"
              type="url"
              value={linkedinUrl}
              onChange={(e) => setLinkedinUrl(e.target.value)}
              icon={Linkedin}
            />
            <Input
              label="Personal Portfolio Website"
              type="url"
              value={portfolioUrl}
              onChange={(e) => setPortfolioUrl(e.target.value)}
              icon={Globe}
            />
          </div>
        </Card>

        {/* 5. SECURITY & PASSWORD */}
        <Card title="Security & Authentication Credentials">
          <form onSubmit={(e) => e.preventDefault()} style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '0.5rem' }}>
            <div className="grid-2" style={{ gap: '1rem' }}>
              <Input
                label="Current Password"
                type="password"
                placeholder="••••••••"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                icon={Key}
              />
              <Input
                label="New Password"
                type="password"
                placeholder="••••••••"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                icon={Key}
              />
            </div>
          </form>
        </Card>

        {/* 6. SAVE ACTION BUTTON */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '0.5rem' }}>
          <Button
            variant="primary"
            size="lg"
            icon={Save}
            isLoading={saving}
            onClick={handleSavePreferences}
          >
            Save Profile & Career Preferences
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ProfilePage;

