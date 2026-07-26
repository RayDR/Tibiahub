import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { useConfirmation } from "../../context/ConfirmationContext";
import {
  Database,
  CheckCircle,
  AlertCircle,
  Download,
  Upload,
  Eye,
  Loader2,
  Save,
  GitBranch,
} from "lucide-react";
import axios from "axios";

interface SyncChange {
  timestamp: string;
  change_type: string;
  source_api: string;
  entity: string;
  entity_id: number;
  action: string;
  old_data?: any;
  new_data?: any;
  status: string;
  approval_required: boolean;
}

interface SyncPreview {
  status: string;
  message: string;
  backup_created: boolean;
  total_changes: number;
  pending_approvals: number;
  changes: SyncChange[];
  action_required: boolean;
}

export default function DatabaseSync() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const confirmation = useConfirmation();
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState<SyncPreview | null>(null);
  const [selectedChanges, setSelectedChanges] = useState<number[]>([]);
  const [approveAll, setApproveAll] = useState(false);
  const [showDetails, setShowDetails] = useState<number | null>(null);

  // Check permissions
  useEffect(() => {
    if (!user?.is_superuser) {
      navigate("/guild");
    }
  }, [user, navigate]);

  const handlePreviewSync = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("token");
      const response = await axios.post<SyncPreview>(
        `${import.meta.env.VITE_API_URL || "http://localhost:8001/api/v1"}/sync/preview`,
        {},
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setPreview(response.data);
      setSelectedChanges([]);
      toast.success("Preview loaded successfully");
    } catch (error) {
      console.error("Failed to preview sync:", error);
      toast.error("Failed to preview changes. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleSelectChange = (index: number) => {
    setSelectedChanges((prev) =>
      prev.includes(index) ? prev.filter((i) => i !== index) : [...prev, index],
    );
  };

  const handleSelectAll = () => {
    if (!preview) return;
    if (selectedChanges.length === preview.changes.length) {
      setSelectedChanges([]);
    } else {
      setSelectedChanges(preview.changes.map((_, i) => i));
    }
  };

  const handleApproveChanges = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("token");
      await axios.post(
        `${import.meta.env.VITE_API_URL || "http://localhost:8001/api/v1"}/sync/approve`,
        {},
        {
          params: {
            approve_all: approveAll,
            change_indices: approveAll ? undefined : selectedChanges,
          },
          headers: { Authorization: `Bearer ${token}` },
        },
      );
      toast.success("Changes approved successfully");
      setSelectedChanges([]);
    } catch (error) {
      console.error("Failed to approve changes:", error);
      toast.error("Failed to approve changes");
    } finally {
      setLoading(false);
    }
  };

  const handleApplyChanges = async () => {
    const confirmed = await confirmation.confirm(
      "Apply approved changes to database? This cannot be undone without restoring a backup.",
      { danger: true },
    );
    if (!confirmed) {
      return;
    }

    setLoading(true);
    try {
      const token = localStorage.getItem("token");
      await axios.post(
        `${import.meta.env.VITE_API_URL || "http://localhost:8001/api/v1"}/sync/apply`,
        {},
        {
          params: {
            apply_all_approved: true,
          },
          headers: { Authorization: `Bearer ${token}` },
        },
      );
      toast.success("Changes applied successfully!");
      setPreview(null);
    } catch (error) {
      console.error("Failed to apply changes:", error);
      toast.error("Failed to apply changes");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateBackup = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("token");
      const response = await axios.post(
        `${import.meta.env.VITE_API_URL || "http://localhost:8001/api/v1"}/sync/backup`,
        {},
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success(
        `Backup created: ${response.data.backup.creatures_count} creatures, ${response.data.backup.zones_count} zones`,
      );
    } catch (error) {
      console.error("Failed to create backup:", error);
      toast.error("Failed to create backup");
    } finally {
      setLoading(false);
    }
  };

  const getActionBadge = (action: string) => {
    switch (action) {
      case "create":
        return (
          <span className="px-2 py-1 bg-success/20 text-success rounded text-xs font-semibold">
            + NEW
          </span>
        );
      case "update":
        return (
          <span className="px-2 py-1 bg-primary/20 text-primary rounded text-xs font-semibold">
            ⚠ UPDATE
          </span>
        );
      case "delete":
        return (
          <span className="px-2 py-1 bg-danger/20 text-danger rounded text-xs font-semibold">
            ✕ DELETE
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-serif text-content-primary mb-2 flex items-center gap-3">
          <GitBranch className="w-10 h-10 text-primary" />
          Database Synchronization
        </h1>
        <p className="text-content-secondary">
          Sync creature data with TibiaWiki, TibiaData, and other sources
        </p>
      </div>

      {/* Main Actions */}
      <div className="grid md:grid-cols-3 gap-4 mb-8">
        <button
          onClick={handlePreviewSync}
          disabled={loading}
          className="flex items-center justify-center gap-2 bg-info hover:bg-info-hover disabled:bg-surface-raised text-content-on-primary px-6 py-3 rounded-lg transition-colors font-medium"
        >
          <Eye className="w-5 h-5" />
          {loading ? "Previewing..." : "Preview Changes"}
        </button>

        <button
          onClick={handleCreateBackup}
          disabled={loading}
          className="flex items-center justify-center gap-2 bg-success hover:bg-success-hover disabled:bg-surface-raised text-content-on-primary px-6 py-3 rounded-lg transition-colors font-medium"
        >
          <Download className="w-5 h-5" />
          Create Backup
        </button>

        <button
          disabled={loading}
          className="flex items-center justify-center gap-2 bg-accent hover:bg-accent-hover disabled:bg-surface-raised text-content-on-primary px-6 py-3 rounded-lg transition-colors font-medium"
        >
          <Upload className="w-5 h-5" />
          Restore Backup
        </button>
      </div>

      {/* Preview Results */}
      {preview && (
        <div className="space-y-6">
          {/* Summary */}
          <div className="bg-surface-base border border-line rounded-xl p-6">
            <div className="grid md:grid-cols-4 gap-4">
              <div>
                <p className="text-content-secondary text-sm mb-1">
                  Total Changes
                </p>
                <p className="text-3xl font-bold text-content-primary">
                  {preview.total_changes}
                </p>
              </div>
              <div>
                <p className="text-content-secondary text-sm mb-1">
                  Pending Approvals
                </p>
                <p className="text-3xl font-bold text-primary">
                  {preview.pending_approvals}
                </p>
              </div>
              <div>
                <p className="text-content-secondary text-sm mb-1">
                  Backup Created
                </p>
                <p className="text-3xl font-bold text-success">
                  {preview.backup_created ? "✓" : "✗"}
                </p>
              </div>
              <div>
                <p className="text-content-secondary text-sm mb-1">
                  Action Required
                </p>
                <p className="text-3xl font-bold text-danger">
                  {preview.action_required ? "⚠" : "✓"}
                </p>
              </div>
            </div>
          </div>

          {/* Selection Controls */}
          {preview.changes.length > 0 && (
            <div className="bg-surface-base border border-line rounded-xl p-4 flex items-center justify-between">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={selectedChanges.length === preview.changes.length}
                  onChange={handleSelectAll}
                  className="w-4 h-4"
                />
                <span className="text-content-secondary">
                  Select All ({selectedChanges.length}/{preview.changes.length})
                </span>
              </label>

              <div className="flex gap-2">
                <button
                  onClick={handleApproveChanges}
                  disabled={selectedChanges.length === 0 || loading}
                  className="flex items-center gap-2 bg-primary hover:bg-primary-hover disabled:bg-surface-raised text-content-on-primary px-4 py-2 rounded transition-colors"
                >
                  <CheckCircle className="w-4 h-4" />
                  Approve Selected
                </button>

                <button
                  onClick={() => setApproveAll(true)}
                  disabled={loading}
                  className="flex items-center gap-2 bg-primary hover:bg-primary-hover disabled:bg-surface-raised text-content-on-primary px-4 py-2 rounded transition-colors"
                >
                  <CheckCircle className="w-4 h-4" />
                  Approve All
                </button>

                <button
                  onClick={handleApplyChanges}
                  disabled={loading}
                  className="flex items-center gap-2 bg-success hover:bg-success-hover disabled:bg-surface-raised text-content-on-primary px-4 py-2 rounded transition-colors font-semibold"
                >
                  <Save className="w-4 h-4" />
                  Apply Changes
                </button>
              </div>
            </div>
          )}

          {/* Changes List */}
          <div className="space-y-3">
            {preview.changes.map((change, idx) => (
              <div
                key={idx}
                className="bg-surface-base border border-line rounded-lg p-4"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      checked={selectedChanges.includes(idx)}
                      onChange={() => handleSelectChange(idx)}
                      className="w-4 h-4 mt-1"
                    />
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-semibold text-content-primary">
                          {change.entity}
                        </span>
                        {getActionBadge(change.action)}
                        <span className="text-xs text-content-muted bg-surface px-2 py-1 rounded">
                          {change.source_api}
                        </span>
                      </div>
                      <p className="text-sm text-content-secondary">
                        Type: {change.change_type} | ID: {change.entity_id}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {change.approval_required && (
                      <AlertCircle className="w-5 h-5 text-primary" />
                    )}
                    <button
                      onClick={() =>
                        setShowDetails(showDetails === idx ? null : idx)
                      }
                      className="text-primary hover:text-primary"
                    >
                      {showDetails === idx ? "▼" : "▶"}
                    </button>
                  </div>
                </div>

                {/* Details */}
                {showDetails === idx && (
                  <div className="border-t border-line pt-3 mt-3">
                    {change.old_data && (
                      <div className="mb-3">
                        <p className="text-xs text-content-secondary mb-1">
                          Old Data:
                        </p>
                        <pre className="bg-surface-base p-2 rounded text-xs text-danger overflow-x-auto">
                          {JSON.stringify(change.old_data, null, 2)}
                        </pre>
                      </div>
                    )}
                    {change.new_data && (
                      <div>
                        <p className="text-xs text-content-secondary mb-1">
                          New Data:
                        </p>
                        <pre className="bg-surface-base p-2 rounded text-xs text-success overflow-x-auto">
                          {JSON.stringify(change.new_data, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {!preview && !loading && (
        <div className="text-center py-12 bg-surface-base border border-line rounded-xl">
          <Database className="w-12 h-12 text-content-muted mx-auto mb-4" />
          <p className="text-content-secondary text-lg">
            Click "Preview Changes" to start synchronization
          </p>
          <p className="text-content-muted text-sm mt-2">
            This will compare your database with external sources
          </p>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="text-center py-12 bg-surface-base border border-line rounded-xl">
          <Loader2 className="w-12 h-12 text-primary mx-auto mb-4 animate-spin" />
          <p className="text-content-secondary text-lg">
            Syncing with external APIs...
          </p>
        </div>
      )}
    </div>
  );
}
