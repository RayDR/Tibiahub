import React, { useEffect, useState } from 'react';
import { guildApi, Recruitment } from '../../services/guild';

import { Loader2, Trophy, Sparkles } from 'lucide-react';

export default function RecruitmentPage() {

    const [recruitments, setRecruitments] = useState<Recruitment[]>([]);
    const [loading, setLoading] = useState(true);
    const [recruitName, setRecruitName] = useState('');
    const [reporting, setReporting] = useState(false);

    const loadData = async () => {
        try {
            setLoading(true);
            const data = await guildApi.getRecruitments();
            setRecruitments(data);
        } catch (error) {
            console.error("Failed to load recruitments", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadData();
    }, []);

    const handleReport = async (e: React.FormEvent) => {
        e.preventDefault();
        setReporting(true);
        try {
            await guildApi.reportRecruitment({ recruit_name: recruitName, notes: 'Recruitment Contest Entry' });
            setRecruitName('');
            loadData();
            alert("Recruitment reported! Pending admin approval.");
        } catch (error) {
            console.error("Failed to report recruitment", error);
            alert("Failed to report recruitment");
        } finally {
            setReporting(false);
        }
    };

    // Group by recruiter to show a leaderboard (client-side aggregation for simplicity)
    const leaderboard = recruitments.reduce((acc, curr) => {
        const recruiterName = curr.recruiter?.username || 'Unknown';
        if (!acc[recruiterName]) {
            acc[recruiterName] = { count: 0, pending: 0, accepted: 0 };
        }
        acc[recruiterName].count++;
        if (curr.status === 'accepted') acc[recruiterName].accepted++;
        if (curr.status === 'pending') acc[recruiterName].pending++;
        return acc;
    }, {} as Record<string, { count: number, pending: number, accepted: number }>);

    const sortedLeaderboard = Object.entries(leaderboard).sort((a, b) => b[1].accepted - a[1].accepted);

    return (
        <div className="space-y-8">
            <div className="flex items-center justify-between">
                <h1 className="text-3xl font-serif text-primary flex items-center gap-3">
                    <Trophy className="w-8 h-8 text-yellow-400 animate-pulse" />
                    Recruitment Tournament
                </h1>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* Report Form */}
                <div className="relative bg-gradient-to-br from-slate-900/80 to-red-950/20 border-2 border-yellow-500/30 rounded-lg p-6 shadow-2xl shadow-yellow-500/20 animate-border-glow">
                    <div className="absolute -top-3 -right-3 bg-yellow-500 text-slate-900 px-3 py-1 rounded-full text-xs font-bold flex items-center gap-1 shadow-lg animate-bounce">
                        <Sparkles className="w-3 h-3" />
                        ACTIVE
                    </div>
                    <h3 className="text-xl font-bold text-primary mb-4 flex items-center gap-2">
                        <Trophy className="w-5 h-5 text-yellow-400" />
                        Report New Recruit
                    </h3>
                    <p className="text-sm text-slate-300 mb-6">
                        🏆 Participating in the <span className="text-yellow-400 font-semibold">Recruitment Tournament</span>? Report your recruits here.
                        Only new members valid per the contest rules.
                    </p>

                    <form onSubmit={handleReport} className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-slate-400 mb-1">Character Name</label>
                            <input
                                type="text"
                                required
                                value={recruitName}
                                onChange={e => setRecruitName(e.target.value)}
                                className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-200 focus:border-amber-500 focus:outline-none"
                                placeholder="e.g. Eternal Oblivion"
                            />
                        </div>
                        <button
                            type="submit"
                            disabled={reporting}
                            className="w-full bg-gradient-to-r from-red-600 to-red-700 hover:from-red-500 hover:to-red-600 text-white font-bold py-3 px-4 rounded-lg transition-all duration-300 disabled:opacity-50 shadow-lg hover:shadow-red-500/50 transform hover:scale-105"
                        >
                            {reporting ? (
                                <span className="flex items-center justify-center gap-2">
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                    Reporting...
                                </span>
                            ) : (
                                <span className="flex items-center justify-center gap-2">
                                    <Trophy className="w-4 h-4" />
                                    Report Recruit
                                </span>
                            )}
                        </button>
                    </form>
                </div>

                {/* Leaderboard */}
                <div className="bg-slate-900/50 border border-red-900/30 rounded-lg p-6 shadow-lg shadow-red-950/20">
                    <h3 className="text-xl font-bold text-slate-100 mb-4 flex items-center gap-2">
                        <Trophy className="w-5 h-5 text-yellow-500" />
                        Contest Leaderboard
                    </h3>

                    {loading ? (
                        <Loader2 className="w-6 h-6 animate-spin mx-auto text-amber-500" />
                    ) : (
                        <div className="space-y-3">
                            {sortedLeaderboard.map(([name, stats], index) => (
                                <div key={name} className="flex items-center justify-between p-3 bg-slate-950/50 rounded border border-slate-800">
                                    <div className="flex items-center gap-3">
                                        <span className={`font-bold w-6 text-center ${index === 0 ? 'text-yellow-500' : index === 1 ? 'text-slate-300' : index === 2 ? 'text-amber-700' : 'text-slate-600'}`}>
                                            #{index + 1}
                                        </span>
                                        <span className="font-medium text-slate-200">{name}</span>
                                    </div>
                                    <div className="text-sm">
                                        <span className="text-green-400 font-bold">{stats.accepted} verified</span>
                                        <span className="text-slate-600 mx-2">/</span>
                                        <span className="text-slate-500">{stats.count} total</span>
                                    </div>
                                </div>
                            ))}
                            {sortedLeaderboard.length === 0 && (
                                <p className="text-slate-500 italic text-center">No recruits reported yet.</p>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
