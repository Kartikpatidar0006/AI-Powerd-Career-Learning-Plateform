import React from 'react';
import { useForm } from 'react-hook-form';
import { Link, useNavigate } from 'react-router-dom';
import { Mail, Lock, LogIn } from 'lucide-react';
import useAuth from '../hooks/useAuth';
import Input from '../components/Input/Input';
import Button from '../components/Button/Button';
import Card from '../components/Card/Card';

export const LoginPage = () => {
  const { login, loading } = useAuth();
  const navigate = useNavigate();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm();

  const onSubmit = async (data) => {
    try {
      await login({
        email: data.email,
        password: data.password,
      });
      navigate('/onboarding');
    } catch {
      // Error toast message handled by AuthContext
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1.5rem', background: 'var(--bg-dark)' }}>
      <div style={{ width: '100%', maxWidth: '440px' }}>
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div className="sidebar-logo-icon" style={{ width: '48px', height: '48px', margin: '0 auto 1rem', fontSize: '1.25rem' }}>AI</div>
          <h1 style={{ fontFamily: 'var(--font-heading)', fontSize: '2rem', fontWeight: 800, color: 'var(--text-main)' }}>Welcome Back</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9375rem', marginTop: '0.25rem' }}>Sign in to continue your career learning journey</p>
        </div>

        <Card>
          <form onSubmit={handleSubmit(onSubmit)}>
            <Input
              label="Email Address"
              type="email"
              placeholder="you@example.com"
              icon={Mail}
              error={errors.email?.message}
              {...register('email', {
                required: 'Email address is required',
                pattern: { value: /^\S+@\S+$/i, message: 'Invalid email address format' },
              })}
            />

            <Input
              label="Password"
              type="password"
              placeholder="••••••••"
              icon={Lock}
              error={errors.password?.message}
              {...register('password', {
                required: 'Password is required',
                minLength: { value: 6, message: 'Password must be at least 6 characters' },
              })}
            />

            <Button type="submit" variant="primary" size="lg" isLoading={loading} icon={LogIn} style={{ width: '100%', marginTop: '1rem' }}>
              Sign In
            </Button>
          </form>

          <div style={{ marginTop: '1.5rem', textAlign: 'center', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
            Don't have an account yet?{' '}
            <Link to="/register" style={{ color: 'var(--primary)', fontWeight: 600, textDecoration: 'none' }}>
              Register Account
            </Link>
          </div>
        </Card>
      </div>
    </div>
  );
};

export default LoginPage;
