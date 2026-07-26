import React from "react";
import { useNavigate } from "react-router-dom";
import { Shield, Users, Database, LogOut } from "lucide-react";

const Dashboard: React.FC = () => {
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem("admin_token");
    navigate("/");
  };

  return (
    <div className="min-h-screen pt-24 px-4 container mx-auto">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-serif font-bold text-content-primary">
          Admin Dashboard
        </h1>
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 text-content-secondary hover:text-content-primary transition-colors"
        >
          <LogOut size={18} /> Logout
        </button>
      </div>

      <div className="grid md:grid-cols-3 gap-6">
        <div className="bg-surface-base border border-line p-6 rounded-xl hover:border-primary/50 transition-colors cursor-pointer group">
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-primary-subtle text-primary transition-all group-hover:bg-primary group-hover:text-content-inverse">
            <Database size={24} />
          </div>
          <h3 className="text-xl font-bold text-content-primary mb-2">
            Manage Content
          </h3>
          <p className="text-content-secondary text-sm">
            Edit creatures, zones, and loot data.
          </p>
        </div>

        <div className="bg-surface-base border border-line p-6 rounded-xl hover:border-primary/50 transition-colors cursor-pointer group">
          <div className="bg-success/10 w-12 h-12 rounded-lg flex items-center justify-center text-success mb-4 group-hover:bg-success-hover group-hover:text-content-primary transition-all">
            <Users size={24} />
          </div>
          <h3 className="text-xl font-bold text-content-primary mb-2">
            Users & Roles
          </h3>
          <p className="text-content-secondary text-sm">
            Manage editors and permissions.
          </p>
        </div>

        <div className="bg-surface-base border border-line p-6 rounded-xl hover:border-primary/50 transition-colors cursor-pointer group">
          <div className="bg-accent/10 w-12 h-12 rounded-lg flex items-center justify-center text-accent mb-4 group-hover:bg-accent-hover group-hover:text-content-primary transition-all">
            <Shield size={24} />
          </div>
          <h3 className="text-xl font-bold text-content-primary mb-2">
            System Status
          </h3>
          <p className="text-content-secondary text-sm">
            View logs and API extraction status.
          </p>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
