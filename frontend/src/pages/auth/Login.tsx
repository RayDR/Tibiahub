import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { authApi } from '../../services/auth';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from 'react-i18next';
import { Users, KeyRound, ShieldAlert } from 'lucide-react';
import AppCard from '../../components/ui/AppCard';
import AppButton from '../../components/ui/AppButton';
import { Page } from '../../components/ui';

export default function Login() {
    const { t } = useTranslation();
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const { login } = useAuth();

    const getLoginErrorMessage = (err: unknown): string => {
        if (!axios.isAxiosError(err)) {
            return 'The server is temporarily unavailable. Please try again later.';
        }

        const status = err.response?.status;
        if (err.code === 'ECONNABORTED') {
            return 'The server took too long to respond. Please try again.';
        }
        if (status === 401) {
            return 'Invalid username or password.';
        }
        if (status === 403) {
            return 'Your account is inactive. Please contact an administrator.';
        }
        if (status === 503 || status === 500) {
            return 'The server is temporarily unavailable. Please try again later.';
        }
        if (!err.response) {
            return 'The server took too long to respond. Please try again.';
        }
        return 'The server is temporarily unavailable. Please try again later.';
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            const response = await authApi.login(username, password);
            await login(response.access_token);
        } catch (err: unknown) {
            setError(getLoginErrorMessage(err));
        } finally {
            setLoading(false);
        }
    };

    return (
        <Page className="grid min-h-[70vh] place-items-center">
            <AppCard className="w-full max-w-md p-8 shadow-xl">
                <div className="text-center mb-8">
                    <h2 className="text-3xl font-bold text-primary font-serif tracking-wider">{t('auth.guildAccess')}</h2>
                    <p className="text-content-muted mt-2">{t('auth.enterRealm')}</p>
                </div>

                {error && (
                    <div className="mb-6 p-4 rounded flex items-center gap-3 border border-danger/50 bg-danger/20 text-content-primary">
                        <ShieldAlert className="w-5 h-5 flex-shrink-0" />
                        <span className="text-sm">{error}</span>
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-6">
                    <div>
                        <label className="block text-sm font-medium text-content-primary mb-2">{t('auth.username')}</label>
                        <div className="relative">
                            <Users className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-content-muted" />
                            <input
                                type="text"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                className="app-input py-2.5 pl-10 pr-4"
                                placeholder={t('auth.username')}
                                required
                            />
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-content-primary mb-2">{t('auth.password')}</label>
                        <div className="relative">
                            <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-content-muted" />
                            <input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="app-input py-2.5 pl-10 pr-4"
                                placeholder="••••••••"
                                required
                            />
                        </div>
                    </div>

                    <AppButton
                        type="submit"
                        disabled={loading}
                        className="w-full py-3 px-4 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {loading ? t('auth.entering') : t('auth.login')}
                    </AppButton>
                </form>

                <div className="mt-4 text-center">
                    <Link to="/reset-password" className="text-sm text-primary hover:text-primary-hover font-medium">
                        Forgot Password?
                    </Link>
                </div>

                <p className="mt-6 text-center text-content-muted text-sm">
                    {t('auth.noAccount')}{' '}
                    <Link to="/register" className="text-primary hover:text-primary-hover font-medium">
                        {t('auth.joinGuild')}
                    </Link>
                </p>
            </AppCard>
        </Page>
    );
}
