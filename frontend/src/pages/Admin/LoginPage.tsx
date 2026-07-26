import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Lock, User, Key } from "lucide-react";
import { motion } from "framer-motion";

const LoginPage: React.FC = () => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    // Simulate login for now - integrated with backend later
    if (username === "admin" && password === "admin123") {
      localStorage.setItem("admin_token", "fake-token");
      navigate("/admin/dashboard");
    } else {
      setError("Invalid credentials");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center pt-20">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="w-full max-w-md rounded-2xl bg-surface-raised p-8 shadow-sm"
      >
        <div className="flex justify-center mb-6">
          <div className="p-4 bg-surface rounded-full text-primary">
            <Lock size={32} />
          </div>
        </div>
        <h2 className="text-2xl font-bold text-center text-content-primary mb-8 font-serif">
          Admin Access
        </h2>

        {error && (
          <div className="bg-danger/10 border border-danger/20 text-danger p-3 rounded-lg mb-4 text-center text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-content-secondary text-xs uppercase font-bold mb-2">
              Username
            </label>
            <div className="relative">
              <User
                size={18}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-content-muted"
              />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full bg-surface-base border border-line rounded-xl py-3 pl-10 text-content-primary focus:border-primary outline-none transition-colors"
              />
            </div>
          </div>

          <div>
            <label className="block text-content-secondary text-xs uppercase font-bold mb-2">
              Password
            </label>
            <div className="relative">
              <Key
                size={18}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-content-muted"
              />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-surface-base border border-line rounded-xl py-3 pl-10 text-content-primary focus:border-primary outline-none transition-colors"
              />
            </div>
          </div>

          <button
            type="submit"
            className="mt-4 w-full rounded-xl bg-gradient-to-r from-primary to-primary-hover py-3 font-bold text-content-inverse transition hover:shadow-lg hover:shadow-primary/20"
          >
            Login
          </button>
        </form>
      </motion.div>
    </div>
  );
};

export default LoginPage;
