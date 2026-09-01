import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Compass,
  ArrowRight,
  Search,
  Filter,
  Clock,
  Award,
  Layers,
  Sparkles,
  CheckCircle2,
  TrendingUp,
} from 'lucide-react';
import PageHeader from '../components/PageHeader/PageHeader';
import Card from '../components/Card/Card';
import Button from '../components/Button/Button';
import Loader from '../components/Loader/Loader';
import Input from '../components/Input/Input';
import professionService from '../services/professionService';

export const ProfessionSelectionPage = () => {
  const [professions, setProfessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');
  const navigate = useNavigate();

  useEffect(() => {
    const fetchProfessions = async () => {
      try {
        setLoading(true);
        setError(null);
        const apiData = await professionService.getProfessions({ is_active: true });
        // Normalize different API response shapes
        const apiItems = Array.isArray(apiData)
          ? apiData
          : (apiData?.data || apiData?.items || []);

        // Normalize backend field names to what the UI expects
        const normalized = apiItems.map((p) => ({
          id: p.id,
          slug: p.slug,
          title: p.name || p.title,
          name: p.name || p.title,
          category: p.category || 'Technology',
          description: p.description || '',
          skills: Array.isArray(p.required_skills) ? p.required_skills : (p.skills || []),
          estimatedDuration: p.estimated_duration || p.estimatedDuration || '12-16 Weeks',
          difficulty: p.difficulty || 'Intermediate',
          averageSalary: p.average_salary
            ? `$${Number(p.average_salary).toLocaleString()}`
            : (p.averageSalary || 'Market Rate'),
          growthRate: p.growth_rate
            ? `+${p.growth_rate}% annual growth`
            : (p.growthRate || null),
          is_active: p.is_active !== false,
        }));

        setProfessions(normalized);
      } catch (err) {
        console.error('Failed to load professions:', err);
        setError('Could not load professions. Please refresh the page or try again later.');
      } finally {
        setLoading(false);
      }
    };

    fetchProfessions();
  }, []);

  // Derive category filter options from actual backend data
  const categories = ['All', ...Array.from(new Set(professions.map((p) => p.category))).filter(Boolean)];

  const filteredProfessions = professions.filter((prof) => {
    const titleLower = (prof.title || '').toLowerCase();
    const descLower = (prof.description || '').toLowerCase();
    const termLower = searchTerm.toLowerCase();

    const matchesSearch =
      titleLower.includes(termLower) ||
      descLower.includes(termLower) ||
      (prof.skills || []).some((sk) => sk.toLowerCase().includes(termLower));

    const matchesCategory =
      selectedCategory === 'All' || prof.category === selectedCategory;

    return matchesSearch && matchesCategory;
  });

  const handleExploreProfession = (prof) => {
    // Navigate to the roadmap using the real backend profession id
    navigate(`/roadmaps?profession_id=${prof.id || prof.slug}`);
  };

  if (loading) return <Loader label="Loading career professions from server..." />;

  if (error) {
    return (
      <div style={{ padding: '3rem', textAlign: 'center' }}>
        <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>⚠️</div>
        <p style={{ color: 'var(--text-muted)' }}>{error}</p>
      </div>
    );
  }


  return (
    <div>
      <PageHeader
        title="Explore Career Professions"
        description="Select a specialized tech career path to unlock tailored learning roadmaps, skills, and mock interviews."
        breadcrumbs={[{ label: 'Professions' }]}
      />

      {/* Filter and Search Bar */}
      <div
        style={{
          display: 'flex',
          justify: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1rem',
          marginBottom: '2rem',
          padding: '1.25rem',
          background: 'var(--bg-card)',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--border-subtle)',
        }}
      >
        {/* Category Pills */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
          {categories.map((cat) => {
            const isSelected = selectedCategory === cat;
            return (
              <button
                key={cat}
                type="button"
                onClick={() => setSelectedCategory(cat)}
                style={{
                  padding: '0.45rem 0.875rem',
                  borderRadius: 'var(--radius-full)',
                  background: isSelected ? 'var(--primary)' : 'var(--bg-input)',
                  color: isSelected ? '#fff' : 'var(--text-muted)',
                  border: isSelected ? '1px solid var(--primary-hover)' : '1px solid var(--border-subtle)',
                  fontSize: '0.8125rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                {cat}
              </button>
            );
          })}
        </div>

        {/* Search Input */}
        <div style={{ width: '100%', maxWidth: '280px' }}>
          <Input
            type="text"
            placeholder="Search titles or skills..."
            icon={Search}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </div>

      {/* Career Cards Grid (14+ Cards) */}
      <div className="grid-3">
        {filteredProfessions.map((prof) => (
          <Card
            key={prof.id || prof.slug}
            interactive
            style={{
              display: 'flex',
              flexDirection: 'column',
              justify: 'space-between',
              height: '100%',
            }}
          >
            <div>
              {/* Category & Difficulty Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                <span
                  style={{
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    padding: '0.15rem 0.5rem',
                    borderRadius: 'var(--radius-sm)',
                    background: 'var(--primary-light)',
                    color: 'var(--primary)',
                  }}
                >
                  {prof.category}
                </span>

                <span
                  style={{
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    color:
                      prof.difficulty === 'Beginner'
                        ? 'var(--accent-emerald)'
                        : prof.difficulty === 'Intermediate'
                        ? 'var(--accent-amber)'
                        : 'var(--accent-rose)',
                  }}
                >
                  {prof.difficulty}
                </span>
              </div>

              {/* Title & Description */}
              <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-main)', marginBottom: '0.5rem' }}>
                {prof.title || prof.name}
              </h3>

              <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', lineHeight: 1.5, marginBottom: '1.25rem' }}>
                {prof.description}
              </p>

              {/* Estimated Duration & Growth */}
              <div
                style={{
                  display: 'flex',
                  gap: '1rem',
                  padding: '0.625rem 0.875rem',
                  background: 'var(--bg-input)',
                  borderRadius: 'var(--radius-md)',
                  marginBottom: '1.25rem',
                  fontSize: '0.8125rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', color: 'var(--text-muted)' }}>
                  <Clock size={15} style={{ color: 'var(--primary)' }} />
                  <span>{prof.estimatedDuration}</span>
                </div>
                {prof.growthRate && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', color: 'var(--accent-emerald)', fontWeight: 600 }}>
                    <TrendingUp size={15} />
                    <span>{prof.growthRate}</span>
                  </div>
                )}
              </div>

              {/* Skills Tags */}
              <div style={{ marginBottom: '1.5rem' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-dim)', display: 'block', marginBottom: '0.375rem' }}>
                  REQUIRED SKILLS:
                </span>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem' }}>
                  {prof.skills.map((skill) => (
                    <span
                      key={skill}
                      style={{
                        fontSize: '0.75rem',
                        padding: '0.15rem 0.5rem',
                        borderRadius: 'var(--radius-sm)',
                        background: 'rgba(255, 255, 255, 0.05)',
                        border: '1px solid var(--border-subtle)',
                        color: 'var(--text-main)',
                        fontWeight: 500,
                      }}
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Explore Button */}
            <Button
              variant="primary"
              icon={ArrowRight}
              onClick={() => handleExploreProfession(prof)}
              style={{ width: '100%' }}
            >
              Explore Career Roadmap
            </Button>
          </Card>
        ))}
      </div>
    </div>
  );
};

export default ProfessionSelectionPage;
