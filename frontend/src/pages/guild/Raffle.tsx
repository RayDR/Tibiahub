import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { guildApi } from '../../services/guild';
import { Loader2, Trophy, Coins, Users, Skull } from 'lucide-react';
import { useToast } from '../../context/ToastContext';

interface Participant {
    name: string;
    level: number;
    vocation: string;
    last_login: string;
}

export default function Raffle() {
    const { success, error, info } = useToast();

    // Configuration
    const [guildName, setGuildName] = useState('Bloodborne Warhowl'); // Default or user's guild
    const [activeDays, setActiveDays] = useState(10);

    // State
    const [isLoading, setIsLoading] = useState(false);
    const [participants, setParticipants] = useState<Participant[]>([]);

    // Game State
    const [round, setRound] = useState(0); // 0: Init, 1: Round 1 (Discard), 2: Round 2 (Discard), 3: Round 3 (Winner)
    const [spinning, setSpinning] = useState(false);
    const [currentName, setCurrentName] = useState('???');
    const [eliminated, setEliminated] = useState<Participant[]>([]);
    const [winner, setWinner] = useState<Participant | null>(null);

    const fetchParticipants = async () => {
        if (!guildName) return;
        setIsLoading(true);
        try {
            const data = await guildApi.getRaffleParticipants(guildName, activeDays);
            setParticipants(data);
            setRound(0);
            setEliminated([]);
            setWinner(null);
            success(`Loaded ${data.length} eligible participants!`);
        } catch (err) {
            console.error(err);
            error('Failed to load participants. Check guild name.');
        } finally {
            setIsLoading(false);
        }
    };

    const loadDemoData = () => {
        const demoNames = [
            "Eternal Oblivion", "Bubble", "Cachero", "Mateusz Dragon Wielki",
            "Smoked", "Vulfgar", "Hesperides", "Ghazbaran", "Morgaroth",
            "Ferumbras", "Orshabaal", "Apocalypse", "Infernatil", "Verminor",
            "Zulazza", "Chizzoron", "Zoralurk", "Tiquandas Revenge", "Demodras"
        ];
        // Create full participant objects
        const demoParticipants = demoNames.map(name => ({
            name,
            level: Math.floor(Math.random() * 1000) + 100,
            vocation: ['Elite Knight', 'Master Sorcerer', 'Elder Druid', 'Royal Paladin'][Math.floor(Math.random() * 4)],
            last_login: new Date().toISOString()
        }));

        setParticipants(demoParticipants);
        setRound(0);
        setEliminated([]);
        setWinner(null);
        info('Loaded Demo Data. Feel free to test the animation!');
    };

    const spin = (targetRound: number) => {
        if (participants.length === 0) return;
        setSpinning(true);
        setRound(targetRound);

        // Animation Logic
        let counter = 0;
        const maxSpins = 30 + Math.floor(Math.random() * 20); // Random duration
        const speed = 100; // ms

        const interval = setInterval(() => {
            const randomIdx = Math.floor(Math.random() * participants.length);
            setCurrentName(participants[randomIdx].name);
            counter++;

            if (counter > maxSpins) {
                clearInterval(interval);
                finishSpin(targetRound);
            }
        }, speed);
    };

    const finishSpin = (targetRound: number) => {
        setSpinning(false);
        // Select random person from remaining participants
        // Note: In real discard mode, we remove them from the array.

        // Get valid candidates (not already eliminated, not already won)
        const candidates = participants.filter(p =>
            !eliminated.find(e => e.name === p.name) &&
            (!winner || winner.name !== p.name)
        );

        if (candidates.length === 0) {
            error('No participants left!');
            return;
        }

        const selectedIdx = Math.floor(Math.random() * candidates.length);
        const selected = candidates[selectedIdx];
        setCurrentName(selected.name);

        if (targetRound === 1 || targetRound === 2) {
            // Discard
            setEliminated(prev => [...prev, selected]);
            info(`${selected.name} has been eliminated!`);
        } else {
            // Winner
            setWinner(selected);
            success(`${selected.name} WINS THE RAFFLE!`);
            // Launch confetti?
        }
    };

    return (
        <div className="min-h-screen bg-[#0d1117] text-slate-200 relative overflow-hidden">
            {/* Background Decor */}
            <div className="absolute top-0 left-0 w-full h-full pointer-events-none opacity-20 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-amber-900/40 via-slate-900 to-slate-950"></div>

            <div className="max-w-6xl mx-auto p-6 relative z-10">

                {/* Header */}
                <header className="mb-12 text-center">
                    <motion.h1
                        initial={{ y: -50, opacity: 0 }}
                        animate={{ y: 0, opacity: 1 }}
                        className="text-5xl md:text-7xl font-bold bg-clip-text text-transparent bg-gradient-to-b from-amber-300 to-amber-600 drop-shadow-sm font-cinzel"
                    >
                        GUILD RAFFLE
                    </motion.h1>
                    <p className="mt-4 text-slate-400 text-lg">Win 5,000,000 Gold! Sponsored by the Guild Bank.</p>
                </header>

                {/* Content Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

                    {/* Left: Info & Controls */}
                    <div className="space-y-6">
                        <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-6 backdrop-blur-sm">
                            <h3 className="text-xl font-semibold text-amber-500 mb-4 flex items-center gap-2">
                                <Trophy className="w-5 h-5" /> Event Details
                            </h3>
                            <div className="space-y-4 text-sm text-slate-300">
                                <p><strong>Prize:</strong> 5,000,000 Gold</p>
                                <p><strong>Draw Date:</strong> Today, 23/01/2026</p>
                                <p><strong>Rules:</strong> Active members only (last 10 days). 1 ticket per player.</p>
                                <div className="border-t border-slate-700 pt-4">
                                    <label className="block text-xs uppercase text-slate-500 mb-1">Guild Name</label>
                                    <input
                                        type="text"
                                        value={guildName}
                                        onChange={(e) => setGuildName(e.target.value)}
                                        className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100 focus:border-amber-500 transition-colors"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs uppercase text-slate-500 mb-1">Active within (days)</label>
                                    <input
                                        type="number"
                                        value={activeDays}
                                        onChange={(e) => setActiveDays(Number(e.target.value))}
                                        className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100 focus:border-amber-500 transition-colors"
                                    />
                                </div>
                                <button
                                    onClick={fetchParticipants}
                                    disabled={isLoading}
                                    className="w-full bg-amber-600 hover:bg-amber-500 text-black font-bold py-3 rounded transition-all flex justify-center items-center gap-2"
                                >
                                    {isLoading ? <Loader2 className="animate-spin" /> : <Users />}
                                    Load Participants
                                </button>
                                <button
                                    onClick={loadDemoData}
                                    className="w-full bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold py-2 rounded transition-all text-sm border border-slate-700"
                                >
                                    Try Demo Simulation
                                </button>
                                <p className="text-xs text-slate-500 italic text-center mt-2">
                                    * This tool runs locally in your browser. Refresh page to reset.
                                    To show this to others, please <strong>share your screen</strong> (Discord/Stream).
                                </p>
                            </div>
                        </div>

                        {/* Participant Stats */}
                        <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-6 backdrop-blur-sm">
                            <h3 className="text-sm font-semibold text-slate-400 uppercase mb-4">Stats</h3>
                            <div className="flex justify-between items-center text-center">
                                <div>
                                    <div className="text-2xl font-bold text-slate-100">{participants.length}</div>
                                    <div className="text-xs text-slate-500">Total</div>
                                </div>
                                <div>
                                    <div className="text-2xl font-bold text-red-500">{eliminated.length}</div>
                                    <div className="text-xs text-slate-500">Eliminated</div>
                                </div>
                                <div>
                                    <div className="text-2xl font-bold text-green-500">{participants.length - eliminated.length}</div>
                                    <div className="text-xs text-slate-500">Remaining</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Center: The Stage */}
                    <div className="lg:col-span-2 space-y-8">

                        {/* Main Display */}
                        <div className="bg-black/40 border-2 border-amber-900/50 rounded-2xl p-8 min-h-[400px] flex flex-col items-center justify-center relative overflow-hidden group">
                            <div className="absolute inset-0 bg-[url('https://tibiamaps.io/images/map-preview.png')] opacity-5 mix-blend-overlay bg-cover bg-center"></div>

                            {/* Status Text */}
                            <div className="mb-8 text-center">
                                <AnimatePresence mode='wait'>
                                    {round === 0 && <motion.div key="intro" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-2xl text-amber-200">Prepare for the Draw</motion.div>}
                                    {round === 1 && <motion.div key="r1" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-2xl text-red-400 font-bold">ROUND 1: ELIMINATION</motion.div>}
                                    {round === 2 && <motion.div key="r2" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-2xl text-red-400 font-bold">ROUND 2: ELIMINATION</motion.div>}
                                    {round === 3 && <motion.div key="r3" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-4xl text-amber-400 font-bold tracking-widest">FINAL DRAW</motion.div>}
                                </AnimatePresence>
                            </div>

                            {/* The Name Display */}
                            <motion.div
                                className={`text-5xl md:text-7xl font-bold text-center px-8 py-12 rounded-xl backdrop-blur-md border border-white/10 w-full ${winner ? 'bg-amber-500/20 text-amber-300 shadow-[0_0_50px_rgba(245,158,11,0.3)]' :
                                    spinning ? 'bg-slate-800/50 text-slate-100' : 'bg-slate-900/50 text-slate-400'
                                    }`}
                                animate={spinning ? { scale: [1, 1.02, 1] } : {}}
                                transition={{ repeat: Infinity, duration: 0.2 }}
                            >
                                {currentName}
                            </motion.div>

                            {/* Controls */}
                            <div className="mt-12 flex gap-4">
                                <button
                                    disabled={participants.length === 0 || spinning || eliminationRoundDone(1)}
                                    onClick={() => spin(1)}
                                    className={`px-6 py-3 rounded font-bold border ${round > 1 ? 'opacity-50 grayscale' : ''} ${eliminationRoundDone(1) ? 'bg-slate-800 text-slate-500 border-slate-700' : 'bg-red-900/30 border-red-500 text-red-400 hover:bg-red-900/50'}`}
                                >
                                    <span className="flex items-center gap-2"><Skull size={18} /> Discard 1</span>
                                </button>

                                <button
                                    disabled={!eliminationRoundDone(1) || spinning || eliminationRoundDone(2)}
                                    onClick={() => spin(2)}
                                    className={`px-6 py-3 rounded font-bold border ${round > 2 ? 'opacity-50 grayscale' : ''} ${eliminationRoundDone(2) ? 'bg-slate-800 text-slate-500 border-slate-700' : 'bg-red-900/30 border-red-500 text-red-400 hover:bg-red-900/50'}`}
                                >
                                    <span className="flex items-center gap-2"><Skull size={18} /> Discard 2</span>
                                </button>

                                <button
                                    disabled={!eliminationRoundDone(2) || spinning || !!winner}
                                    onClick={() => spin(3)}
                                    className={`px-8 py-3 rounded font-bold border ${winner ? 'bg-amber-600 text-black border-amber-500' : 'bg-amber-900/30 border-amber-500 text-amber-400 hover:bg-amber-900/50 hover:shadow-[0_0_20px_rgba(245,158,11,0.2)]'}`}
                                >
                                    <span className="flex items-center gap-2"><Coins size={18} /> DRAW WINNER</span>
                                </button>
                            </div>

                            {winner && (
                                <motion.div
                                    initial={{ scale: 0, rotate: -180 }}
                                    animate={{ scale: 1, rotate: 0 }}
                                    className="absolute inset-0 flex items-center justify-center bg-black/80 backdrop-blur-sm z-50 rounded-2xl"
                                >
                                    <div className="text-center p-8 bg-gradient-to-br from-amber-600 to-yellow-600 rounded-2xl shadow-2xl border-4 border-yellow-300">
                                        <Trophy className="w-24 h-24 text-yellow-100 mx-auto mb-4" />
                                        <h2 className="text-3xl font-bold text-white mb-2">WINNER!</h2>
                                        <div className="text-4xl text-black font-extrabold bg-white/20 rounded px-6 py-2 mb-4">
                                            {winner.name}
                                        </div>
                                        <p className="text-yellow-100">Congratulations! You won 5,000,000 Gold!</p>
                                        <button onClick={() => setWinner(null)} className="mt-6 text-sm underline text-white/80 hover:text-white">Close</button>
                                    </div>
                                </motion.div>
                            )}
                        </div>

                        {/* Participant List (Grid) */}
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 max-h-60 overflow-y-auto p-4 bg-slate-900/30 rounded border border-slate-800">
                            {participants.map((p, i) => {
                                const isEliminated = eliminated.find(e => e.name === p.name);
                                const isWinner = winner?.name === p.name;

                                return (
                                    <div key={i} className={`p-2 rounded text-xs truncate transition-all ${isEliminated ? 'bg-red-900/20 text-red-700 decoration-line-through' :
                                        isWinner ? 'bg-amber-500 text-black font-bold' :
                                            'bg-slate-800 text-slate-400'
                                        }`}>
                                        {p.name}
                                    </div>
                                )
                            })}
                        </div>

                    </div>
                </div>
            </div>
        </div>
    );

    function eliminationRoundDone(r: number) {
        if (r === 1) return eliminated.length >= 1;
        if (r === 2) return eliminated.length >= 2;
        return false;
    }
}
