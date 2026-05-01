import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { authApi } from '../../services/auth';
import { useTranslation } from 'react-i18next';
import { Users, KeyRound, ShieldAlert, Swords, Mail, CheckCircle2 } from 'lucide-react';

export default function Register() {
    const { t } = useTranslation();
    const [formData, setFormData] = useState({
        username: '',
        email: '',
        password: '',
        confirmPassword: '',
        tibia_character_name: ''
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
                tibia_character_name: formData.tibia_character_name
            });
            // Automatically redirect to login
            navigate('/login');
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Registration failed');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex items-center justify-center min-h-[calc(100vh-200px)] py-12">
            <div className="w-full max-w-lg p-8 rounded-lg bg-slate-900/90 border border-slate-700 shadow-xl backdrop-blur-sm">
                <div className="text-center mb-8">
                    <h2 className="text-3xl font-bold text-amber-500 font-serif tracking-wider">Join the Guild</h2>
                    <p className="text-slate-400 mt-2">Begin your journey with Bloodborne Warhowl</p>
                </div>

                {error && (
                    <div className="mb-6 p-4 bg-red-900/30 border border-red-700/50 rounded flex items-center gap-3 text-red-200">
                        <ShieldAlert className="w-5 h-5 flex-shrink-0" />
                        <span className="text-sm">{error}</span>
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-5">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                        <div>
                            <label className="block text-sm font-medium text-slate-300 mb-2">{t('auth.username')}</label>
                            <div className="relative">
                                <Users className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
                                <input
                                    type="text"
                                    value={formData.username}
                                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                                    className="w-full bg-slate-950 border border-slate-700 rounded-md py-2.5 pl-10 pr-4 text-slate-200 focus:outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500 transition-colors"
                                    placeholder={t('auth.username')}
                                    required
                                />
                            </div>
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-slate-300 mb-2">{t('auth.email')}</label>
                            <div className="relative">
                                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
                                <input
                                    type="email"
                                    value={formData.email}
                                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                    className="w-full bg-slate-950 border border-slate-700 rounded-md py-2.5 pl-10 pr-4 text-slate-200 focus:outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500 transition-colors"
                                    placeholder={t('auth.emailOptional')}
                                />
                            </div>
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-slate-300 mb-2">{t('auth.characterName')}</label>
                        <div className="relative">
                            <Swords className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
                            <input
                                type="text"
                                value={formData.tibia_character_name}
                                onChange={(e) => setFormData({ ...formData, tibia_character_name: e.target.value })}
                                className="w-full bg-slate-950 border border-slate-700 rounded-md py-2.5 pl-10 pr-4 text-slate-200 focus:outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500 transition-colors"
                                placeholder={t('auth.exactCharacterName')}
                                required
                            />
                        </div>
                        <p className="text-xs text-slate-500 mt-1 flex items-center gap-1">
                            <CheckCircle2 className="w-3 h-3" />
                            {t('auth.characterRequired')}
                        </p>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                        <div>
                            <label className="block text-sm font-medium text-slate-300 mb-2">{t('auth.password')}</label>
                            <div className="relative">
                                <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
                                <input
                                    type="password"
                                    value={formData.password}
                                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                                    className="w-full bg-slate-950 border border-slate-700 rounded-md py-2.5 pl-10 pr-4 text-slate-200 focus:outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500 transition-colors"
                                    placeholder="••••••••"
                                    required
                                />
                            </div>
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-slate-300 mb-2">{t('auth.confirmPassword')}</label>
                            <div className="relative">
                                <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
                                <input
                                    type="password"
                                    value={formData.confirmPassword}
                                    onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                                    className="w-full bg-slate-950 border border-slate-700 rounded-md py-2.5 pl-10 pr-4 text-slate-200 focus:outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500 transition-colors"
                                    placeholder="••••••••"
                                    required
                                />
                            </div>
                        </div>
                    </div>

                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full bg-amber-600 hover:bg-amber-500 text-white font-semibold py-3 px-4 rounded-md transition-all duration-200 shadow-lg shadow-amber-900/20 disabled:opacity-50 disabled:cursor-not-allowed mt-4"
                    >
                        {loading ? t('auth.registering') : t('auth.registerButton')}
                    </button>
                </form>

                <p className="mt-6 text-center text-slate-400 text-sm">
                    {t('auth.alreadyMember')}{' '}
                    <Link to="/login" className="text-amber-500 hover:text-amber-400 font-medium">
                        {t('auth.loginHere')}
                    </Link>
                </p>
            </div>
        </div>
    );
}
