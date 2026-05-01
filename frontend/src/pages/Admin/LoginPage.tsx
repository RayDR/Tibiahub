import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Lock, User, Key } from 'lucide-react';
import { motion } from 'framer-motion';

const LoginPage: React.FC = () => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const navigate = useNavigate();

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        // Simulate login for now - integrated with backend later
        if (username === 'admin' && password === 'admin123') {
            localStorage.setItem('admin_token', 'fake-token');
            navigate('/admin/dashboard');
        } else {
            setError('Invalid credentials');
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center pt-20">
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="w-full max-w-md bg-slate-900 border border-slate-700 rounded-2xl p-8 shadow-2xl"
            >
                <div className="flex justify-center mb-6">
                    <div className="p-4 bg-slate-800 rounded-full text-amber-500">
                        <Lock size={32} />
                    </div>
                </div>
                <h2 className="text-2xl font-bold text-center text-white mb-8 font-serif">Admin Access</h2>

                {error && (
                    <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-3 rounded-lg mb-4 text-center text-sm">
                        {error}
                    </div>
                )}

                <form onSubmit={handleLogin} className="space-y-4">
                    <div>
                        <label className="block text-slate-400 text-xs uppercase font-bold mb-2">Username</label>
                        <div className="relative">
                            <User size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                            <input
                                type="text"
                                value={username}
                                onChange={e => setUsername(e.target.value)}
                                className="w-full bg-slate-950 border border-slate-800 rounded-xl py-3 pl-10 text-white focus:border-amber-500 outline-none transition-colors"
                            />
                        </div>
                    </div>

                    <div>
                        <label className="block text-slate-400 text-xs uppercase font-bold mb-2">Password</label>
                        <div className="relative">
                            <Key size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                            <input
                                type="password"
                                value={password}
                                onChange={e => setPassword(e.target.value)}
                                className="w-full bg-slate-950 border border-slate-800 rounded-xl py-3 pl-10 text-white focus:border-amber-500 outline-none transition-colors"
                            />
                        </div>
                    </div>

                    <button
                        type="submit"
                        className="w-full bg-gradient-to-r from-amber-600 to-amber-500 text-white font-bold py-3 rounded-xl hover:shadow-lg hover:shadow-amber-500/20 transition-all mt-4"
                    >
                        Login
                    </button>
                </form>
            </motion.div>
        </div>
    );
};

export default LoginPage;
