import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { authApi } from '../../services/auth';
import { useTranslation } from 'react-i18next';
import { Users, KeyRound, ShieldAlert, Mail } from 'lucide-react';
import AppCard from '../../components/ui/AppCard';
import AppButton from '../../components/ui/AppButton';

export default function Register() {
    const { t, i18n } = useTranslation();
    const [formData, setFormData] = useState({
        username: '',
        email: '',
        password: '',
        confirmPassword: ''
    });
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (formData.password !== formData.confirmPassword) {
            setError(t('auth.passwordsMustMatch'));
            return;
        }

        setError('');
        setLoading(true);

        try {
            await authApi.register({
                username: formData.username,
                email: formData.email,
                password: formData.password,
                locale: i18n.language.startsWith('es') ? 'es' : 'en'
            });
            // Automatically redirect to login
            navigate('/login');
        } catch (err: any) {
            setError(err.response?.data?.detail || t('auth.registerFailed'));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex items-center justify-center min-h-[calc(100vh-200px)] py-12">
            <AppCard className="w-full max-w-lg p-8 shadow-xl">
                <div className="text-center mb-8">
                    <h2 className="text-3xl font-bold text-primary font-serif tracking-wider">{t('auth.joinGuild')}</h2>
                    <p className="text-content-muted mt-2">{t('auth.beginJourney')}</p>
                </div>

                {error && (
                    <div className="mb-6 p-4 rounded flex items-center gap-3 border border-danger/50 bg-danger/20 text-content-primary">
                        <ShieldAlert className="w-5 h-5 flex-shrink-0" />
                        <span className="text-sm">{error}</span>
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-5">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                        <div>
                            <label className="block text-sm font-medium text-content-primary mb-2">{t('auth.username')}</label>
                            <div className="relative">
                                <Users className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-content-muted" />
                                <input
                                    type="text"
                                    value={formData.username}
                                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                                    className="app-input py-2.5 pl-10 pr-4"
                                    placeholder={t('auth.username')}
                                    required
                                />
                            </div>
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-content-primary mb-2">{t('auth.email')}</label>
                            <div className="relative">
                                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-content-muted" />
                                <input
                                    type="email"
                                    value={formData.email}
                                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                    className="app-input py-2.5 pl-10 pr-4"
                                    placeholder={t('auth.emailOptional')}
                                />
                            </div>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                        <div>
                            <label className="block text-sm font-medium text-content-primary mb-2">{t('auth.password')}</label>
                            <div className="relative">
                                <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-content-muted" />
                                <input
                                    type="password"
                                    value={formData.password}
                                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                                    className="app-input py-2.5 pl-10 pr-4"
                                    placeholder="••••••••"
                                    minLength={12}
                                    required
                                />
                            </div>
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-content-primary mb-2">{t('auth.confirmPassword')}</label>
                            <div className="relative">
                                <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-content-muted" />
                                <input
                                    type="password"
                                    value={formData.confirmPassword}
                                    onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                                    className="app-input py-2.5 pl-10 pr-4"
                                    placeholder="••••••••"
                                    minLength={12}
                                    required
                                />
                            </div>
                        </div>
                    </div>

                    <AppButton
                        type="submit"
                        disabled={loading}
                        className="w-full py-3 px-4 disabled:opacity-50 disabled:cursor-not-allowed mt-4"
                    >
                        {loading ? t('auth.registering') : t('auth.registerButton')}
                    </AppButton>
                </form>

                <p className="mt-6 text-center text-content-muted text-sm">
                    {t('auth.alreadyMember')}{' '}
                    <Link to="/login" className="text-primary hover:text-primary-hover font-medium">
                        {t('auth.loginHere')}
                    </Link>
                </p>
            </AppCard>
        </div>
    );
}
