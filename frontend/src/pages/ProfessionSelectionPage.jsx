import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Compass, ArrowRight } from 'lucide-react';
import PageHeader from '../components/PageHeader/PageHeader';
import Card from '../components/Card/Card';
import Button from '../components/Button/Button';
import Loader from '../components/Loader/Loader';
import EmptyState from '../components/EmptyState/EmptyState';
import professionService from '../services/professionService';

export const ProfessionSelectionPage = () => {
  const [professions, setProfessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchProfessions = async () => {
      try {
        setLoading(true);
        const data = await professionService.getProfessions();
        setProfessions(Array.isArray(data) ? data : data.items || []);
      } catch (err) {
        setProfessions([]);
      } finally {
        setLoading(false);
      }
    };
    fetchProfessions();
  }, []);

  if (loading) return <Loader label="Loading career professions..." />;

  return (
    <div>
      <PageHeader
        title="Career Professions"
        description="Select a specialized tech career path to unlock tailored learning roadmaps, skills, and mock interviews."
        breadcrumbs={[{ label: 'Professions' }]}
      />

      {professions.length === 0 ? (
        <EmptyState
          title="No Professions Available"
          message="Career professions are currently being populated. Check back shortly!"
        />
      ) : (
        <div className="grid-3">
          {professions.map((prof) => (
            <Card
              key={prof.id}
              interactive
              title={prof.name || prof.title}
              subtitle={prof.category || 'Tech Specialization'}
              footer={
                <Button variant="primary" icon={ArrowRight} onClick={() => navigate(`/roadmaps?profession_id=${prof.id}`)}>
                  Explore Roadmaps
                </Button>
              }
            >
              <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                {prof.description || 'Master industry skills and hands-on projects for this specialization.'}
              </p>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default ProfessionSelectionPage;
