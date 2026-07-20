import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { eventsApi } from '../services/events';
import { Loader2, Trophy, Clock, Skull, Users } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from 'react-i18next';

interface Participant {
    name: string;
    level?: number;
    vocation?: string;
}

export default function PublicRafflePage() {
    const { uuid, publicCode } = useParams();
    const { user } = useAuth();
    const { t } = useTranslation();

    const [loading, setLoading] = useState(true);
    const [eventData, setEventData] = useState<any>(null);
    const [participants, setParticipants] = useState<Participant[]>([]);
    const [winner, setWinner] = useState<Participant | null>(null);

    // Animation Stage: 'waiting', 'drawing', 'elimination1', 'elimination2', 'winner'
    const [stage, setStage] = useState<'waiting' | 'drawing' | 'elimination1' | 'elimination2' | 'winner'>('waiting');
    const [currentName, setCurrentName] = useState('...');
    const [eliminated, setEliminated] = useState<Participant[]>([]);
    const [timeLeft, setTimeLeft] = useState('');

    // Fetch initial state
    useEffect(() => {
        const init = async () => {
            try {
                if (!uuid && !publicCode) return;
                const event = publicCode ? await eventsApi.getPublicEventByCode(publicCode) : await eventsApi.getPublicEvent(uuid!);
                setEventData(event);

                // Get participants status
                const status = await eventsApi.getRaffleStatus(publicCode ? event.uuid : uuid!);
                setParticipants(status.participants);

                if (status.is_drawn && status.winner_number && status.winner_name) {
                    // Always start fresh - don't set winner yet, let animation do it
                    // Wait a bit for participants to be ready
                    setTimeout(() => {
                        if (status.participants && status.participants.length > 0) {
                            startAnimationSequence(status.winner_name);
                        } else {
                            setWinner({ name: status.winner_name });
                            setStage('winner');
                        }
                    }, 100);
                } else if (status.is_drawn) {
                    // Drawn but no winner name (excluded or error)
                    setStage('waiting');
                }
            } catch (error) {
                console.error("Error loading event", error);
            } finally {
                setLoading(false);
            }
        };
        if (uuid || publicCode) init();
    }, [uuid, publicCode]);

    // Timer & Auto-Start Logic
    useEffect(() => {
        if (!eventData || stage !== 'waiting' || winner) return;

        const interval = setInterval(async () => {
            const now = new Date();
            
            // Parse draw_date as UTC (backend returns UTC timestamps)
            const targetTime = new Date(eventData.draw_date + 'Z');

            // Re-check status
            try {
                const statusKey = publicCode ? eventData?.uuid : uuid;
                if (statusKey) {
                    const status = await eventsApi.getRaffleStatus(statusKey);
                    if (status.is_drawn && !winner) {
                        // It was drawn! Start animation sequence locally
                        setWinner({ name: status.winner_name });
                        startAnimationSequence(status.winner_name);
                        clearInterval(interval);
                    }
                }
            } catch (e) { }

            // Countdown display - update every second
            const diff = targetTime.getTime() - now.getTime();
            if (diff > 0) {
                const h = Math.floor(diff / 3600000);
                const m = Math.floor((diff % 3600000) / 60000);
                const s = Math.floor((diff % 60000) / 1000);
                setTimeLeft(`${h}h ${m}m ${s}s`);
            } else {
                setTimeLeft('Drawing...');
            }

        }, 1000);

        return () => clearInterval(interval);
    }, [eventData, stage, winner, uuid, publicCode]);

    const startAnimationSequence = async (winName: string) => {
        if (!winName || participants.length === 0) {
            setWinner({ name: winName || 'Unknown' });
            setStage('winner');
            return;
        }
        
        setStage('drawing');

        // Mock elimination of 2 random people (not the winner)
        const others = participants.filter(p => p.name !== winName);
        if (others.length < 2) {
            setWinner({ name: winName });
            setStage('winner');
            return;
        }

        const elim1 = others[Math.floor(Math.random() * others.length)];
        const others2 = others.filter(p => p.name !== elim1.name);
        const elim2 = others2[Math.floor(Math.random() * others2.length)];

        // Sequence
        // 1. Spin for Elim 1
        await spinWheel(elim1.name, 'elimination1');
        setEliminated([elim1]);
        await new Promise(r => setTimeout(r, 2000));

        // 2. Spin for Elim 2
        await spinWheel(elim2.name, 'elimination2');
        setEliminated([elim1, elim2]);
        await new Promise(r => setTimeout(r, 2000));

        // 3. Spin for Winner
        await spinWheel(winName, 'winner');
        setWinner({ name: winName });
    };

    const spinWheel = (targetName: string, targetStage: any) => {
        return new Promise<void>((resolve) => {
            setStage(targetStage);
            let counter = 0;
            const maxSpins = 30; // 3 sec
            const interval = setInterval(() => {
                const rnd = Math.floor(Math.random() * participants.length);
                setCurrentName(participants[rnd].name);
                counter++;
                if (counter > maxSpins) {
                    clearInterval(interval);
                    setCurrentName(targetName);
                    resolve();
                }
            }, 100);
        });
    };

    if (loading) return <div className="h-screen flex items-center justify-center bg-black text-white"><Loader2 className="animate-spin w-10 h-10 text-amber-500" /></div>;
    if (!eventData) return <div className="text-white text-center mt-20">{t('raffle.eventNotFound', 'Event not found')}</div>;

    return (
        <div className="min-h-screen bg-[#050505] text-slate-200 font-sans selection:bg-amber-500/30">
            {/* Header / Waiting Room */}
            <div className="max-w-7xl mx-auto p-4 sm:p-8">
                <header className="text-center mb-8">
                    <h1 className="text-4xl md:text-6xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-amber-200 to-amber-600 font-serif tracking-wider mb-2">
                        {eventData.title}
                    </h1>
                    <p className="text-amber-500/80 text-lg uppercase tracking-widest">{eventData.reward}</p>
                </header>

                {stage === 'winner' && winner ? (
                    <motion.div
                        initial={{ scale: 0.8, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        className="text-center py-20 bg-gradient-to-b from-amber-900/20 to-black rounded-3xl border border-amber-500/30 shadow-[0_0_100px_rgba(245,158,11,0.2)]"
                    >
                        <Trophy className="w-32 h-32 text-amber-400 mx-auto mb-6 animate-bounce" />
                        <h2 className="text-2xl text-amber-200 mb-2">{t('raffle.winner', 'WINNER')}</h2>
                        <div className="text-5xl md:text-7xl font-bold text-white mb-6">{winner.name}</div>
                        <p className="text-slate-400 text-lg">{t('raffle.congratsMessage', 'Congratulations! Your prize awaits.')}</p>
                        <p className="text-amber-300 text-sm mt-4 italic">{t('raffle.winnerMessage', '"Fortune favors the brave. Your name has been chosen by destiny!"')}</p>
                    </motion.div>
                ) : (
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                        {/* Left: Info */}
                        <div className="space-y-6">
                            <div className="bg-slate-900/40 border border-slate-800 p-6 rounded-2xl backdrop-blur-sm">
                                <h3 className="text-xl text-amber-500 font-bold mb-4 flex items-center gap-2">
                                    <Clock className="w-5 h-5" /> {t('raffle.status', 'Status')}
                                </h3>
                                <div className="text-3xl font-mono text-white mb-2">
                                    {stage === 'waiting' ? timeLeft || t('raffle.liveEvent', 'Live Event') : t('raffle.drawing', 'DRAWING...')}
                                </div>
                                <p className="text-sm text-slate-400">
                                    {stage === 'waiting'
                                        ? t('raffle.autoUpdate', 'The event changes will appear automatically. Sit tight!')
                                        : t('raffle.drawingProcess', 'The raffle mechanism is running...')}
                                </p>
                                {/* Admin trigger for demo/lazy - Only show for superusers */}
                                {user?.is_superuser && stage === 'waiting' && !winner && (
                                    <div className="mt-8 pt-4 border-t border-slate-800">
                                        <button
                                            onClick={() => (eventData?.uuid || uuid) && eventsApi.autoDrawRaffle((eventData?.uuid || uuid) as string)}
                                            className="text-xs text-slate-700 hover:text-slate-500 underline"
                                        >
                                            {t('raffle.devForceStart', 'dev: force start')}
                                        </button>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Center: Stage */}
                        <div className="lg:col-span-2 space-y-4">
                            {/* Participants list - always visible */}
                            <div className="bg-slate-900/20 border border-slate-800 rounded-2xl p-6">
                                <h3 className="text-slate-400 mb-4 flex items-center gap-2">
                                    <Users className="w-4 h-4" /> {t('raffle.liveParticipants', 'Participants')} ({participants.length})
                                </h3>
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 max-h-[300px] overflow-y-auto pr-2 custom-scrollbar">
                                    {participants.map((p, i) => {
                                        const isEliminated = eliminated.some(e => e.name === p.name);
                                        return (
                                            <div 
                                                key={i} 
                                                className={`flex items-center gap-2 p-2 rounded border text-xs transition-all ${
                                                    isEliminated 
                                                        ? 'bg-red-900/20 border-red-500/30 opacity-50 line-through' 
                                                        : 'bg-slate-900/50 border-slate-800/50'
                                                }`}
                                            >
                                                <span className={`w-6 h-6 flex items-center justify-center rounded-full font-mono ${
                                                    isEliminated ? 'bg-red-900/50 text-red-500' : 'bg-slate-800 text-slate-500'
                                                }`}>
                                                    {isEliminated ? '✗' : i + 1}
                                                </span>
                                                <span className={`truncate ${isEliminated ? 'text-red-400' : 'text-slate-300'}`}>
                                                    {p.name}
                                                </span>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>

                            {/* Drawing animation */}
                            {stage !== 'waiting' && (
                                <div className="bg-black border-4 border-amber-900/50 rounded-2xl p-12 min-h-[400px] flex flex-col items-center justify-center relative overflow-hidden">
                                    <div className="absolute inset-0 bg-[url('https://tibiamaps.io/images/map-preview.png')] opacity-10 bg-cover bg-center"></div>

                                    <div className="relative z-10 text-center">
                                        <h3 className="text-2xl text-amber-500 mb-8 uppercase tracking-widest font-bold">
                                            {stage.includes('elimination') ? t('raffle.eliminating', 'ELIMINATING...') : t('raffle.drawingWinner', 'DRAWING WINNER')}
                                        </h3>

                                        <div className="text-5xl md:text-7xl font-bold text-white bg-slate-900/80 px-8 py-6 rounded-xl border border-amber-500/20 shadow-2xl backdrop-blur-md">
                                            {currentName}
                                        </div>

                                        <div className="mt-12 flex justify-center gap-4">
                                            {eliminated.map((e, i) => (
                                                <motion.div
                                                    key={i}
                                                    initial={{ y: 20, opacity: 0 }}
                                                    animate={{ y: 0, opacity: 1 }}
                                                    className="bg-red-900/20 border border-red-500/30 px-4 py-2 rounded text-red-400 flex items-center gap-2"
                                                >
                                                    <Skull size={14} /> {e.name}
                                                </motion.div>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>

            <footer className="fixed bottom-0 w-full text-center p-4 text-xs text-slate-600 bg-black/80 backdrop-blur">
                {t('raffle.transparencyId', 'Transparency ID')}: {eventData.id} | {t('raffle.timestamp', 'Timestamp')}: {new Date().toISOString()}
            </footer>
        </div>
    );
}
