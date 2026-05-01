import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { authApi } from '../../services/auth';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from 'react-i18next';
import { Users, KeyRound, ShieldAlert } from 'lucide-react';

export default function Login() {
    const { t } = useTranslation();
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const { login } = useAuth();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            const response = await authApi.login(username, password);
            await login(response.access_token);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Login failed');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex items-center justify-center min-h-[calc(100vh-200px)]">
            <div className="w-full max-w-md p-8 rounded-lg bg-slate-900/90 border border-slate-700 shadow-xl backdrop-blur-sm">
                <div className="text-center mb-8">
                    <h2 className="text-3xl font-bold text-amber-500 font-serif tracking-wider">{t('auth.guildAccess')}</h2>
                    <p className="text-slate-400 mt-2">{t('auth.enterRealm')}</p>
                </div>

                {error && (
                    <div className="mb-6 p-4 bg-red-900/30 border border-red-700/50 rounded flex items-center gap-3 text-red-200">
                        <ShieldAlert className="w-5 h-5 flex-shrink-0" />
                        <span className="text-sm">{error}</span>
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-6">
                    <div>
                        <label className="block text-sm font-medium text-slate-300 mb-2">{t('auth.username')}</label>
                        <div className="relative">
                            <Users className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
                            <input
                                type="text"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                className="w-full bg-slate-950 border border-slate-700 rounded-md py-2.5 pl-10 pr-4 text-slate-200 focus:outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500 transition-colors"
                                placeholder={t('auth.username')}
                                required
                            />
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-slate-300 mb-2">{t('auth.password')}</label>
                        <div className="relative">
                            <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
                            <input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="w-full bg-slate-950 border border-slate-700 rounded-md py-2.5 pl-10 pr-4 text-slate-200 focus:outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500 transition-colors"
                                placeholder="••••••••"
                                required
                            />
                        </div>
                    </div>

                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full bg-amber-600 hover:bg-amber-500 text-white font-semibold py-3 px-4 rounded-md transition-all duration-200 shadow-lg shadow-amber-900/20 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {loading ? t('auth.entering') : t('auth.login')}
                    </button>
                </form>

                <div className="mt-4 text-center">
                    <Link to="/reset-password" className="text-sm text-amber-500 hover:text-amber-400 font-medium">
                        Forgot Password?
                    </Link>
                </div>

                <p className="mt-6 text-center text-slate-400 text-sm">
                    {t('auth.noAccount')}{' '}
                    <Link to="/register" className="text-amber-500 hover:text-amber-400 font-medium">
                        {t('auth.joinGuild')}
                    </Link>
                </p>
            </div>
        </div>
    );
}
