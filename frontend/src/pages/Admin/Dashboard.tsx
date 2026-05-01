import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, Users, Database, LogOut } from 'lucide-react';

const Dashboard: React.FC = () => {
    const navigate = useNavigate();

    const handleLogout = () => {
        localStorage.removeItem('admin_token');
        navigate('/');
    };

    return (
        <div className="min-h-screen pt-24 px-4 container mx-auto">
            <div className="flex justify-between items-center mb-8">
                <h1 className="text-3xl font-serif font-bold text-white">Admin Dashboard</h1>
                <button
                    onClick={handleLogout}
                    className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors"
                >
                    <LogOut size={18} /> Logout
                </button>
            </div>

            <div className="grid md:grid-cols-3 gap-6">
                <div className="bg-slate-900 border border-slate-700 p-6 rounded-xl hover:border-amber-500/50 transition-colors cursor-pointer group">
                    <div className="bg-amber-500/10 w-12 h-12 rounded-lg flex items-center justify-center text-amber-500 mb-4 group-hover:bg-amber-500 group-hover:text-white transition-all">
                        <Database size={24} />
                    </div>
                    <h3 className="text-xl font-bold text-white mb-2">Manage Content</h3>
                    <p className="text-slate-400 text-sm">Edit creatures, zones, and loot data.</p>
                </div>

                <div className="bg-slate-900 border border-slate-700 p-6 rounded-xl hover:border-amber-500/50 transition-colors cursor-pointer group">
                    <div className="bg-emerald-500/10 w-12 h-12 rounded-lg flex items-center justify-center text-emerald-500 mb-4 group-hover:bg-emerald-500 group-hover:text-white transition-all">
                        <Users size={24} />
                    </div>
                    <h3 className="text-xl font-bold text-white mb-2">Users & Roles</h3>
                    <p className="text-slate-400 text-sm">Manage editors and permissions.</p>
                </div>

                <div className="bg-slate-900 border border-slate-700 p-6 rounded-xl hover:border-amber-500/50 transition-colors cursor-pointer group">
                    <div className="bg-purple-500/10 w-12 h-12 rounded-lg flex items-center justify-center text-purple-500 mb-4 group-hover:bg-purple-500 group-hover:text-white transition-all">
                        <Shield size={24} />
                    </div>
                    <h3 className="text-xl font-bold text-white mb-2">System Status</h3>
                    <p className="text-slate-400 text-sm">View logs and API extraction status.</p>
                </div>
            </div>
        </div>
    );
};

export default Dashboard;
