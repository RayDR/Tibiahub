import React, { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';
import { User, authApi } from '../services/auth';
import { useNavigate } from 'react-router-dom';

interface AuthContextType {
    user: User | null;
    loading: boolean;
    login: (token: string) => Promise<void>;
    logout: () => void;
    refreshUser: () => Promise<User | null>;
    updateUser: (user: Partial<User>) => void;
    isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);
    const navigate = useNavigate();

    const fetchUser = async (): Promise<User | null> => {
        setLoading(true);

        try {
            for (let attempt = 0; attempt < 2; attempt += 1) {
                try {
                    const userData = await authApi.getMe();
                    setUser(userData);
                    return userData;
                } catch (error) {
                    const isAxiosError =
                        axios.isAxiosError(error);

                    const status = isAxiosError
                        ? error.response?.status
                        : undefined;

                    const invalidCredentials =
                        status === 401 || status === 403;

                    if (invalidCredentials) {
                        localStorage.removeItem('token');
                        setUser(null);
                        return null;
                    }

                    const transientFailure =
                        isAxiosError &&
                        (
                            !error.response ||
                            error.code === 'ECONNABORTED' ||
                            (
                                status !== undefined &&
                                status >= 500
                            )
                        );

                    if (
                        transientFailure &&
                        attempt === 0
                    ) {
                        await new Promise<void>(
                            (resolve) => {
                                window.setTimeout(
                                    resolve,
                                    400,
                                );
                            },
                        );

                        continue;
                    }

                    console.error(
                        'Temporarily unable to fetch user',
                        error,
                    );

                    // Preserve both the token and the current
                    // authenticated state for transient failures.
                    return null;
                }
            }

            return null;
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
        const profile = await fetchUser();
        if (profile?.is_superuser) {
            navigate('/admin', { replace: true });
            return;
        }
        navigate('/guild/dashboard', { replace: true });
    };

    const logout = () => {
        localStorage.removeItem('token');
        Object.keys(localStorage).forEach((key) => {
            if (key.startsWith('tibiahub:user:') || key.startsWith('tibiahub:selectedGuild')) localStorage.removeItem(key);
        });
        Object.keys(sessionStorage).forEach((key) => {
            if (key.startsWith('tibiahub:user:') || key.startsWith('tibiahub:selectedGuild')) sessionStorage.removeItem(key);
        });
        window.dispatchEvent(new Event('tibiahub:logout'));
        setUser(null);
        navigate('/login', { replace: true });
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
            refreshUser: fetchUser,
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
