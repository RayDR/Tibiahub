import React, { createContext, useContext, useState, useEffect } from 'react';
import { User, authApi } from '../services/auth';
import { useNavigate } from 'react-router-dom';

interface AuthContextType {
    user: User | null;
    loading: boolean;
    login: (token: string) => Promise<void>;
    logout: () => void;
    updateUser: (user: Partial<User>) => void;
    isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);
    const navigate = useNavigate();

    const fetchUser = async () => {
        try {
            const userData = await authApi.getMe();
            setUser(userData);
        } catch (error) {
            console.error('Failed to fetch user', error);
            localStorage.removeItem('token');
            setUser(null);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        const token = localStorage.getItem('token');
        if (token) {
            fetchUser();
        } else {
            setLoading(false);
        }
    }, []);

    const login = async (token: string) => {
        localStorage.setItem('token', token);
        await fetchUser();
        navigate('/guild/dashboard'); // Redirect to dashboard after login
    };

    const logout = () => {
        localStorage.removeItem('token');
        setUser(null);
        navigate('/');
    };

    const updateUser = (nextUser: Partial<User>) => {
        setUser((current) => current ? { ...current, ...nextUser } : current);
    };

    return (
        <AuthContext.Provider value={{
            user,
            loading,
            login,
            logout,
            updateUser,
            isAuthenticated: !!user
        }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};
