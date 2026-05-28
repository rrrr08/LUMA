"use client";

import React, { useState, useEffect } from "react";
import { apiFetch } from "../../../lib/api-client";
import Toast from "../../../components/Toast";

interface ApiKey {
  id: string;
  name: string;
  created_at: string;
}

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [keyName, setKeyName] = useState("");
  const [revealedKey, setRevealedKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

  const loadKeys = async () => {
    try {
      const res = await apiFetch("/v1/projects/keys");
      if (res.ok) {
        const data = await res.json();
        setKeys(data);
      }
    } catch (err) {
      console.error("Failed to load keys:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadKeys();
  }, []);

  const handleCreateKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!keyName) return;

    setErrorMsg("");
    setRevealedKey(null);

    try {
      const res = await apiFetch("/v1/projects/keys", {
        method: "POST",
        body: JSON.stringify({ name: keyName })
      });

      if (!res.ok) throw new Error("Failed to generate API Key.");

      const data = await res.json();
      setRevealedKey(data.raw_key);
      setKeyName("");
      setToast({ message: "API key generated successfully", type: "success" });
      loadKeys();
    } catch (err: any) {
      setErrorMsg(err.message || "Something went wrong.");
      setToast({ message: "Failed to generate API key", type: "error" });
    }
  };

  const handleRevokeKey = async (id: string) => {
    if (
      !confirm(
        "Are you sure you want to revoke this API key? Applications currently using this credential to request your endpoints will be blocked immediately."
      )
    ) {
      return;
    }

    try {
      const res = await apiFetch(`/v1/projects/keys/${id}`, {
        method: "DELETE"
      });

      if (res.ok) {
        setKeys(keys.filter((k) => k.id !== id));
        setToast({ message: "API Key revoked successfully", type: "success" });
      } else {
        const err = await res.json();
        setToast({ message: err.detail || "Failed to revoke API key", type: "error" });
      }
    } catch (err) {
      setToast({ message: "Network error occurred.", type: "error" });
    }
  };

  return (
    <div style={{ maxWidth: "800px", margin: "0 auto" }}>
      <header className="dashboard-header">
        <div>
          <h1>API Keys</h1>
          <p style={{ color: "var(--text-secondary)", marginTop: "0.25rem" }}>
            Create and manage access keys to authenticate your client applications requests.
          </p>
        </div>
      </header>

      {revealedKey && (
        <div className="card" style={{ borderLeft: "4px solid var(--warning)", marginBottom: "2rem", backgroundColor: "rgba(245, 158, 11, 0.05)" }}>
          <h3 style={{ color: "var(--warning)" }}>⚠️ Copy your API key</h3>
          <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", margin: "0.5rem 0 1rem" }}>
            For security reasons, we cannot display this key again. Copy it now and save it in your environment variables.
          </p>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", backgroundColor: "var(--bg-tertiary)", padding: "1rem", borderRadius: "var(--radius-md)" }}>
            <code style={{ flex: 1, color: "var(--text-primary)", fontSize: "1.1rem" }}>{revealedKey}</code>
            <button
              className="btn btn-secondary"
              style={{ padding: "0.5rem 1rem", fontSize: "0.85rem" }}
              onClick={() => {
                navigator.clipboard.writeText(revealedKey);
                setToast({ message: "API key copied to clipboard", type: "success" });
              }}
            >
              Copy
            </button>
          </div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "2rem" }}>
        {/* Keys listing */}
        <div className="card">
          <h3 style={{ marginBottom: "1.5rem" }}>Active Credentials</h3>
          {loading ? (
            <div className="shimmer" style={{ height: "40px", borderRadius: "6px" }} />
          ) : keys.length === 0 ? (
            <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem" }}>
              No active API keys created yet. Generate one on the right.
            </p>
          ) : (
            <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "1rem", padding: 0 }}>
              {keys.map((k) => (
                <li key={k.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingBottom: "1rem", borderBottom: "1px solid var(--border-color)" }}>
                  <div>
                    <h4 style={{ fontSize: "1rem" }}>{k.name}</h4>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      Created at: {new Date(k.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                    <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)", fontFamily: "var(--font-mono)" }}>
                      sk_live_...••••
                    </span>
                    <button
                      onClick={() => handleRevokeKey(k.id)}
                      style={{
                        padding: "0.3rem 0.6rem",
                        fontSize: "0.75rem",
                        background: "rgba(244, 63, 94, 0.1)",
                        border: "1px solid rgba(244, 63, 94, 0.2)",
                        color: "#f43f5e",
                        cursor: "pointer",
                        borderRadius: "var(--radius-sm)",
                        transition: "all 0.2s"
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = "#f43f5e";
                        e.currentTarget.style.color = "#ffffff";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = "rgba(244, 63, 94, 0.1)";
                        e.currentTarget.style.color = "#f43f5e";
                      }}
                    >
                      Revoke
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Create key form */}
        <div className="card">
          <h3 style={{ marginBottom: "1rem" }}>Generate New Key</h3>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", marginBottom: "1.5rem" }}>
            Give your token a descriptive name (e.g. "Staging Service", "Mobile APP Client").
          </p>

          <form onSubmit={handleCreateKey}>
            <div className="form-group">
              <label className="form-label" htmlFor="key-name">API Token Name</label>
              <input
                id="key-name"
                type="text"
                className="input-text"
                placeholder="Production Gateway"
                value={keyName}
                onChange={(e) => setKeyName(e.target.value)}
                required
              />
            </div>
            {errorMsg && <p style={{ color: "var(--error)", fontSize: "0.85rem", margin: "-0.5rem 0 1rem" }}>{errorMsg}</p>}
            <button type="submit" className="btn btn-primary" style={{ width: "100%", marginTop: "1rem" }}>
              Generate API Token
            </button>
          </form>
        </div>
      </div>

      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  );
}
