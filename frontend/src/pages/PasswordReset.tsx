// Password Reset Page
import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useToast } from '../context/ToastContext';
import { Shield, Loader2, CheckCircle, Mail } from 'lucide-react';
import api from '../services/api';

export default function PasswordReset() {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const toast = useToast();

    const token = searchParams.get('token');

    const [loading, setLoading] = useState(false);
    const [step, setStep] = useState<'request' | 'reset' | 'success'>(token ? 'reset' : 'request');
    const [formData, setFormData] = useState({
        email: '',
        character_name: '',
        new_password: '',
        confirm_password: '',
    });

    const handleRequestReset = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!formData.email && !formData.character_name) {
            toast.error('Please provide email or character name');
            return;
        }

        setLoading(true);
        try {
            await api.post('/password/request-reset', {
                email: formData.email || undefined,
                character_name: formData.character_name || undefined,
            });

            setStep('success');
            toast.success('If an account exists, a reset email has been sent');
        } catch (error: any) {
            console.error('Failed to request reset:', error);
            toast.error(error.response?.data?.detail || 'Failed to request password reset');
        } finally {
            setLoading(false);
        }
    };

    const handleResetPassword = async (e: React.FormEvent) => {
        e.preventDefault();

        if (formData.new_password !== formData.confirm_password) {
            toast.error('Passwords do not match');
            return;
        }

        if (formData.new_password.length < 6) {
            toast.error('Password must be at least 6 characters');
            return;
        }

        setLoading(true);
        try {
            await api.post('/password/reset-password', {
                token,
                new_password: formData.new_password,
            });

            toast.success('Password reset successfully!');
            setTimeout(() => navigate('/login'), 2000);
        } catch (error: any) {
            console.error('Failed to reset password:', error);
            toast.error(error.response?.data?.detail || 'Failed to reset password');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-surface-base flex items-center justify-center p-4">
            <div className="w-full max-w-md">
                {/* Logo/Header */}
                <div className="text-center mb-8">
                    <div className="flex items-center justify-center gap-3 mb-4">
                        <Shield className="w-10 h-10 md:w-12 md:h-12 text-primary" />
                        <h1 className="text-3xl md:text-4xl font-serif text-content-primary">TibiaHub</h1>
                    </div>
                    <p className="text-content-secondary text-sm md:text-base">
                        {step === 'request' && 'Reset Your Password'}
                        {step === 'reset' && 'Create New Password'}
                        {step === 'success' && 'Check Your Email'}
                    </p>
                </div>

                {/* Request Reset Form */}
                {step === 'request' && (
                    <div className="bg-surface-base/50 border border-line rounded-lg p-6 md:p-8">
                        <form onSubmit={handleRequestReset} className="space-y-6">
                            <div>
                                <label className="block text-sm font-medium text-content-secondary mb-2">
                                    <Mail className="w-4 h-4 inline mr-1" />
                                    Email Address
                                </label>
                                <input
                                    type="email"
                                    value={formData.email}
                                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                    className="w-full bg-surface-base border border-line rounded px-3 py-2 text-content-primary focus:outline-none focus:border-primary"
                                    placeholder="your.email@example.com"
                                />
                            </div>

                            <div className="flex items-center gap-4">
                                <div className="flex-1 border-t border-line"></div>
                                <span className="text-content-muted text-sm">OR</span>
                                <div className="flex-1 border-t border-line"></div>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-content-secondary mb-2">
                                    <Shield className="w-4 h-4 inline mr-1" />
                                    Tibia Character Name
                                </label>
                                <input
                                    type="text"
                                    value={formData.character_name}
                                    onChange={(e) => setFormData({ ...formData, character_name: e.target.value })}
                                    className="w-full bg-surface-base border border-line rounded px-3 py-2 text-content-primary focus:outline-none focus:border-primary"
                                    placeholder="Character Name"
                                />
                            </div>

                            <button
                                type="submit"
                                disabled={loading}
                                className="w-full bg-primary hover:bg-primary-hover disabled:bg-surface-raised disabled:text-content-muted text-content-on-primary font-semibold py-3 rounded-md transition-colors flex items-center justify-center gap-2"
                            >
                                {loading ? (
                                    <>
                                        <Loader2 className="w-5 h-5 animate-spin" />
                                        Sending...
                                    </>
                                ) : (
                                    'Send Reset Link'
                                )}
                            </button>

                            <div className="text-center">
                                <button
                                    type="button"
                                    onClick={() => navigate('/login')}
                                    className="text-sm text-primary hover:text-primary transition-colors"
                                >
                                    Back to Login
                                </button>
                            </div>
                        </form>
                    </div>
                )}

                {/* Reset Password Form */}
                {step === 'reset' && (
                    <div className="bg-surface-base/50 border border-line rounded-lg p-6 md:p-8">
                        <form onSubmit={handleResetPassword} className="space-y-6">
                            <div>
                                <label className="block text-sm font-medium text-content-secondary mb-2">
                                    New Password
                                </label>
                                <input
                                    type="password"
                                    value={formData.new_password}
                                    onChange={(e) => setFormData({ ...formData, new_password: e.target.value })}
                                    className="w-full bg-surface-base border border-line rounded px-3 py-2 text-content-primary focus:outline-none focus:border-primary"
                                    placeholder="At least 6 characters"
                                    required
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-content-secondary mb-2">
                                    Confirm Password
                                </label>
                                <input
                                    type="password"
                                    value={formData.confirm_password}
                                    onChange={(e) => setFormData({ ...formData, confirm_password: e.target.value })}
                                    className="w-full bg-surface-base border border-line rounded px-3 py-2 text-content-primary focus:outline-none focus:border-primary"
                                    placeholder="Repeat password"
                                    required
                                />
                            </div>

                            <button
                                type="submit"
                                disabled={loading}
                                className="w-full bg-primary hover:bg-primary-hover disabled:bg-surface-raised disabled:text-content-muted text-content-on-primary font-semibold py-3 rounded-md transition-colors flex items-center justify-center gap-2"
                            >
                                {loading ? (
                                    <>
                                        <Loader2 className="w-5 h-5 animate-spin" />
                                        Resetting...
                                    </>
                                ) : (
                                    'Reset Password'
                                )}
                            </button>
                        </form>
                    </div>
                )}

                {/* Success Message */}
                {step === 'success' && (
                    <div className="bg-surface-base/50 border border-success/50 rounded-lg p-6 md:p-8 text-center">
                        <CheckCircle className="w-16 h-16 text-success mx-auto mb-4" />
                        <h2 className="text-2xl font-semibold text-content-primary mb-2">Email Sent!</h2>
                        <p className="text-content-secondary mb-6">
                            If an account with that information exists, we've sent a password reset link to your email.
                        </p>
                        <p className="text-sm text-content-muted mb-6">
                            Please check your inbox and spam folder.
                        </p>
                        <button
                            onClick={() => navigate('/login')}
                            className="text-primary hover:text-primary transition-colors"
                        >
                            Return to Login
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}
