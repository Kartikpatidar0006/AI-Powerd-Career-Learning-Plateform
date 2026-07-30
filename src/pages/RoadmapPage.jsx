import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { MapPin, CheckCircle, ArrowRight } from 'lucide-react';
import PageHeader from '../components/PageHeader/PageHeader';
import Card from '../components/Card/Card';
import Button from '../components/Button/Button';
import Loader from '../components/Loader/Loader';
import EmptyState from '../components/EmptyState/EmptyState';
import roadmapService from '../services/roadmapService';

export const RoadmapPage = () => {
  const { roadmapId } = useParams();
  const [roadmaps, setRoadmaps] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchRoadmaps = async () => {
      try {
        setLoading(true);
        if (roadmapId) {
          const single = await roadmapService.getRoadmapById(roadmapId);
          setRoadmaps([single]);
        } else {
          const list = await roadmapService.getCareerRoadmaps();
          setRoadmaps(Array.isArray(list) ? list : list.items || []);
        }
      } catch (err) {
        setRoadmaps([]);
      } finally {
        setLoading(false);
      }
    };
    fetchRoadmaps();
  }, [roadmapId]);

  if (loading) return <Loader label="Loading career roadmaps..." />;

  return (
    <div>
      <PageHeader
        title="Career Learning Roadmaps"
        description="Structured step-by-step guidance designed to take you from foundational concepts to production mastery."
        breadcrumbs={[{ label: 'Roadmaps' }]}
      />

      {roadmaps.length === 0 ? (
        <EmptyState title="No Roadmaps Found" message="No active career roadmaps found. Check back soon!" />
      ) : (
        <div className="grid-2">
          {roadmaps.map((rm) => (
            <Card
              key={rm.id}
              interactive
              title={rm.title}
              subtitle={`Difficulty: ${rm.difficulty || 'Medium'} • Est. Months: ${rm.estimated_months || 6}`}
              footer={
                <Button variant="primary" icon={ArrowRight} onClick={() => navigate(`/tasks?roadmap_id=${rm.id}`)}>
                  View Roadmap Tasks
                </Button>
              }
            >
              <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', lineHeight: 1.5, marginBottom: '1rem' }}>
                {rm.description || 'Step-by-step career progression roadmap.'}
              </p>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default RoadmapPage;
