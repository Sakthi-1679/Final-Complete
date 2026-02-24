import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { buildApiUrl } from '../constants';
import './Subscription.css';

interface Plan {
  name: string;
  price: number;
  features: string[];
  video_limit: number;
}

interface SubscriptionPlans {
  [key: string]: Plan;
}

export const Subscription: React.FC = () => {
  const navigate = useNavigate();
  const [plans, setPlans] = useState<SubscriptionPlans | null>(null);
  const [currentPlan, setCurrentPlan] = useState<string>('free');
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState<string | null>(null);

  const token = localStorage.getItem('authToken');
  const user = localStorage.getItem('user')
    ? JSON.parse(localStorage.getItem('user') || '{}')
    : null;

  useEffect(() => {
    if (!token) {
      navigate('/login');
      return;
    }

    fetchPlans();
    if (user?.subscription) {
      setCurrentPlan(user.subscription);
    }
  }, [token, user]);

  const fetchPlans = async () => {
    try {
      const response = await fetch(buildApiUrl('/auth/subscription-plans'));
      const data: SubscriptionPlans = await response.json();
      setPlans(data);
    } catch (error) {
      console.error('Error fetching subscription plans:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleUpgrade = async (planKey: string) => {
    if (planKey === currentPlan) {
      alert('You are already on this plan!');
      return;
    }

    setUpgrading(planKey);

    try {
      const response = await fetch(buildApiUrl('/auth/upgrade'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ plan: planKey })
      });

      const data = await response.json();

      if (data.success) {
        // Update user data
        const updatedUser = { ...user, subscription: planKey };
        localStorage.setItem('user', JSON.stringify(updatedUser));
        setCurrentPlan(planKey);
        alert(data.message);
      } else {
        alert(data.error || 'Upgrade failed');
      }
    } catch (error) {
      console.error('Error upgrading subscription:', error);
      alert('Failed to upgrade subscription');
    } finally {
      setUpgrading(null);
    }
  };

  return (
    <div className="subscription-container">
      <div className="subscription-header">
        <h1>🎬 Choose Your Plan</h1>
        <p>Get access to premium movie recommendations powered by AI</p>
      </div>

      {loading ? (
        <div className="loading">Loading subscription plans...</div>
      ) : plans ? (
        <div className="plans-grid">
          {Object.entries(plans as SubscriptionPlans).map(([planKey, plan]: [string, Plan]) => (
              <div
                key={planKey}
                className={`plan-card ${planKey} ${
                  planKey === currentPlan ? 'active' : ''
                }`}
              >
                {planKey === 'enterprise' && (
                  <div className="popular-badge">Most Popular</div>
                )}

                <h2>{plan.name}</h2>

                <div className="price">
                  <span className="currency">₹</span>
                  <span className="amount">{plan.price}</span>
                  <span className="period">/month</span>
                </div>

                <div className="description">
                  Watch up to <strong>{plan.video_limit}</strong> videos/month
                </div>

                <button
                  className={`upgrade-button ${
                    planKey === currentPlan ? 'current' : ''
                  }`}
                  onClick={() => handleUpgrade(planKey)}
                  disabled={upgrading === planKey}
                >
                  {upgrading === planKey
                    ? 'Upgrading...'
                    : planKey === currentPlan
                    ? 'Current Plan'
                    : 'Select Plan'}
                </button>

                <div className="features">
                  <h4>Features included:</h4>
                  <ul>
                    {(plan.features || []).map((feature, idx) => (
                      <li key={idx}>
                        <span className="checkmark">✓</span>
                        {feature
                          .split('_')
                          .map(
                            (word) =>
                              word.charAt(0).toUpperCase() + word.slice(1)
                          )
                          .join(' ')}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            ))}
        </div>
      ) : (
        <div className="error">Failed to load subscription plans. Please refresh.</div>
      )}

      <div className="faq-section">
        <h3>Frequently Asked Questions</h3>
        <div className="faq-items">
          <div className="faq-item">
            <h4>Can I change my plan anytime?</h4>
            <p>Yes! You can upgrade or downgrade your plan at any time.</p>
          </div>
          <div className="faq-item">
            <h4>What happens if I exceed video limits?</h4>
            <p>
              Premium users get unlimited recommendations. Free users see a
              notice after 10 videos per month.
            </p>
          </div>
          <div className="faq-item">
            <h4>Do you offer refunds?</h4>
            <p>
              We offer a 7-day money-back guarantee for all premium plans.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Subscription;
