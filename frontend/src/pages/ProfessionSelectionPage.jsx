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
import { PROFESSION_CATALOG } from '../constants/professionCatalog';
import onboardingService from '../services/onboardingService';

export const ProfessionSelectionPage = () => {
  const [professions, setProfessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');
  const navigate = useNavigate();

  useEffect(() => {
    const fetchProfessions = async () => {
      try {
        setLoading(true);
        const apiData = await professionService.getProfessions();
        const apiItems = Array.isArray(apiData) ? apiData : apiData.items || [];

        // Merge API data with full catalog of 14+ professions to guarantee at least 14-15 career cards
        const mergedMap = new Map();

        // 1. Populate catalog items first
        PROFESSION_CATALOG.forEach((item) => {
          mergedMap.set(item.slug, item);
        });

        // 2. Override/enrich with API items if available
        apiItems.forEach((apiItem) => {
          const key = apiItem.slug || apiItem.name?.toLowerCase().replace(/\s+/g, '-');
          if (mergedMap.has(key)) {
            mergedMap.set(key, { ...mergedMap.get(key), ...apiItem });
          } else {
            mergedMap.set(key, {
              id: apiItem.id,
              slug: key,
              title: apiItem.name || apiItem.title,
              name: apiItem.name || apiItem.title,
              category: apiItem.category || 'Tech Specialization',
              description: apiItem.description || 'Master key skills and hands-on projects for this specialization.',
              skills: apiItem.required_skills || ['Python', 'SQL', 'Git'],
              estimatedDuration: '14 Weeks',
              difficulty: 'Intermediate',
            });
          }
        });

        setProfessions(Array.from(mergedMap.values()));
      } catch (err) {
        setProfessions(PROFESSION_CATALOG);
      } finally {
        setLoading(false);
      }
    };

    fetchProfessions();
  }, []);

  // Filter logic
  const categories = ['All', 'AI & Machine Learning', 'Software Engineering', 'Data & Analytics', 'Cloud & Infrastructure', 'Security & Systems'];

  const filteredProfessions = professions.filter((prof) => {
    const matchesSearch =
      prof.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      prof.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      prof.skills.some((sk) => sk.toLowerCase().includes(searchTerm.toLowerCase()));

    const matchesCategory =
      selectedCategory === 'All' || prof.category === selectedCategory;

    return matchesSearch && matchesCategory;
  });

  const handleExploreProfession = (prof) => {
    // Set as selected profession in onboarding profile storage
    const currentOnboarding = onboardingService.getProfile() || {};
    const roadmap = onboardingService.generateRoadmap(prof, currentOnboarding);
    
    onboardingService.saveProfile({
      selectedProfession: prof,
      activeRoadmap: roadmap,
    });

    navigate(`/roadmaps?profession_id=${prof.id || prof.slug}`);
  };

  if (loading) return <Loader label="Loading 14+ career professions..." />;

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
