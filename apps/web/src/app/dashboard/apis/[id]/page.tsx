"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiFetch } from "../../../../lib/api-client";
import Toast from "../../../../components/Toast";

interface Project {
  id: string;
  name: string;
  status: string;
}

interface Endpoint {
  id: string;
  path: string;
  method: string;
  cache_ttl_sec: number;
}

interface Webhook {
  id: string;
  url: string;
  trigger_type: string;
  is_active: boolean;
}

interface GoogleSheetsConfig {
  google_sheet_url: string;
  google_sheet_sync_enabled: boolean;
}

export default function ApiExplorer() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const [activeTab, setActiveTab] = useState<"explorer" | "integrations" | "export">("explorer");

  const [project, setProject] = useState<Project | null>(null);
  const [endpoint, setEndpoint] = useState<Endpoint | null>(null);
  const [schemaSpec, setSchemaSpec] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const [apiKey, setApiKey] = useState("");
  const [queryResponse, setQueryResponse] = useState<string | null>(null);
  const [queryLoading, setQueryLoading] = useState(false);
  const [cacheStatus, setCacheStatus] = useState<string | null>(null);

  // Health log info
  const [requestCount, setRequestCount] = useState(0);
  const [lastHit, setLastHit] = useState<string | null>(null);

  // Python Code Editor states
  const [extractorCode, setExtractorCode] = useState("");
  const [testingCode, setTestingCode] = useState(false);
  const [savingCode, setSavingCode] = useState(false);

  // Webhooks & Integrations state
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [newWebhookUrl, setNewWebhookUrl] = useState("");
  const [sheetsConfig, setSheetsConfig] = useState<GoogleSheetsConfig>({
    google_sheet_url: "",
    google_sheet_sync_enabled: false
  });
  const [savingSheets, setSavingSheets] = useState(false);
  const [loadingIntegrations, setLoadingIntegrations] = useState(false);

  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const loadApiDetails = async () => {
    try {
      // Fetch project list
      const res = await apiFetch("/v1/projects");
      if (res.ok) {
        const list = await res.json();
        const found = list.find((p: any) => p.id === projectId);
        if (found) {
          setProject(found);
          if (found.path) {
            setEndpoint({
              id: `end_${found.id}`,
              path: found.path,
              method: "GET",
              cache_ttl_sec: 3600
            });

            // Fetch dynamic schema specification
            try {
              const schemaRes = await apiFetch(`/v1/projects/${projectId}/schema`);
              if (schemaRes.ok) {
                const schemaData = await schemaRes.json();
                setSchemaSpec(schemaData);
              }
            } catch (schemaErr) {
              console.error("Failed to load project schema:", schemaErr);
            }

            // Fetch health telemetry details
            try {
              const healthRes = await apiFetch("/v1/analytics/per-endpoint");
              if (healthRes.ok) {
                const healthData = await healthRes.json();
                const foundHealth = healthData.find((h: any) => h.path === found.path);
                if (foundHealth) {
                  setRequestCount(foundHealth.request_count);
                  setLastHit(foundHealth.last_hit);
                }
              }
            } catch (healthErr) {
              console.error("Failed to load health statistics:", healthErr);
            }

            // Fetch dynamic BeautifulSoup Python code
            try {
              const codeRes = await apiFetch(`/v1/projects/${projectId}/code`);
              if (codeRes.ok) {
                const codeData = await codeRes.json();
                setExtractorCode(codeData.code);
              }
            } catch (codeErr) {
              console.error("Failed to load project parser code:", codeErr);
            }
          } else {
            setEndpoint(null);
          }
        }
      }
    } catch (err) {
      console.error("Failed to load details:", err);
    } finally {
      setLoading(false);
    }
  };

  const loadIntegrations = async () => {
    setLoadingIntegrations(true);
    try {
      const webhooksRes = await apiFetch(`/v1/projects/${projectId}/webhooks`);
      if (webhooksRes.ok) {
        setWebhooks(await webhooksRes.json());
      }
      const sheetsRes = await apiFetch(`/v1/projects/${projectId}/integrations/google-sheets`);
      if (sheetsRes.ok) {
        const data = await sheetsRes.json();
        if (data) {
          setSheetsConfig({
            google_sheet_url: data.google_sheet_url || "",
            google_sheet_sync_enabled: data.google_sheet_sync_enabled || false
          });
        }
      }
    } catch (err) {
      console.error("Failed to load integrations:", err);
    } finally {
      setLoadingIntegrations(false);
    }
  };

  useEffect(() => {
    loadApiDetails();
  }, [projectId]);

  useEffect(() => {
    if (activeTab === "integrations") {
      loadIntegrations();
    }
  }, [activeTab, projectId]);

  // Execute request to the Dynamic API Gateway
  const handleTestCall = async () => {
    if (!endpoint) return;
    setQueryLoading(true);
    setQueryResponse(null);
    setCacheStatus(null);

    const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const targetUrl = `${API_BASE}/v1/apis${endpoint.path}`;

    try {
      const res = await fetch(targetUrl, {
        method: "GET",
        headers: {
          "X-API-KEY": apiKey
        }
      });

      const cacheHeader = res.headers.get("X-Cache");
      if (cacheHeader) {
        setCacheStatus(cacheHeader);
      }

      const payload = await res.json();
      setQueryResponse(JSON.stringify(payload, null, 2));

      // Refresh health stats after call
      loadApiDetails();
    } catch (err: any) {
      setQueryResponse(JSON.stringify({ error: err.message || "Failed to make call." }, null, 2));
    } finally {
      setQueryLoading(false);
    }
  };

  const handleManualRefresh = async () => {
    if (refreshing) return;
    setRefreshing(true);
    try {
      const res = await apiFetch(`/v1/projects/${projectId}/refresh`, {
        method: "POST"
      });

      if (res.ok) {
        setToast({ message: "Background scraper refresh triggered successfully", type: "success" });
      } else {
        const err = await res.json();
        setToast({ message: err.detail || "Failed to trigger refresh", type: "error" });
      }
    } catch (err) {
      setToast({ message: "Network error occurred.", type: "error" });
    } finally {
      setRefreshing(false);
    }
  };

  const handleTestCustomCode = async () => {
    setTestingCode(true);
    setQueryResponse(null);
    try {
      const res = await apiFetch(`/v1/projects/${projectId}/test-code`, {
        method: "POST",
        body: JSON.stringify({ code: extractorCode })
      });
      const data = await res.json();
      if (res.ok) {
        setQueryResponse(JSON.stringify(data.results, null, 2));
        setToast({ message: "Sandbox execution completed successfully!", type: "success" });
      } else {
        setQueryResponse(JSON.stringify(data, null, 2));
        setToast({ message: data.detail || "Sandbox test failed.", type: "error" });
      }
    } catch (err: any) {
      setToast({ message: err.message || "Failed to run sandbox test.", type: "error" });
    } finally {
      setTestingCode(false);
    }
  };

  const handleSaveCustomCode = async () => {
    setSavingCode(true);
    try {
      const res = await apiFetch(`/v1/projects/${projectId}/code`, {
        method: "PUT",
        body: JSON.stringify({ code: extractorCode })
      });
      const data = await res.json();
      if (res.ok) {
        setToast({ message: "Custom scraper code updated and deployed live!", type: "success" });
        loadApiDetails();
      } else {
        setToast({ message: data.detail || "Failed to save code.", type: "error" });
      }
    } catch (err: any) {
      setToast({ message: err.message || "Failed to save code.", type: "error" });
    } finally {
      setSavingCode(false);
    }
  };

  // Webhook actions
  const handleCreateWebhook = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWebhookUrl) return;
    try {
      const res = await apiFetch(`/v1/projects/${projectId}/webhooks`, {
        method: "POST",
        body: JSON.stringify({
          url: newWebhookUrl,
          trigger_type: "on_change",
          is_active: true
        })
      });
      if (res.ok) {
        const created = await res.json();
        setWebhooks([...webhooks, created]);
        setNewWebhookUrl("");
        setToast({ message: "Webhook target added successfully!", type: "success" });
      } else {
        const err = await res.json();
        setToast({ message: err.detail || "Failed to create webhook", type: "error" });
      }
    } catch (err) {
      setToast({ message: "Failed to connect to API", type: "error" });
    }
  };

  const handleDeleteWebhook = async (webhookId: string) => {
    try {
      const res = await apiFetch(`/v1/projects/${projectId}/webhooks/${webhookId}`, {
        method: "DELETE"
      });
      if (res.ok) {
        setWebhooks(webhooks.filter((w) => w.id !== webhookId));
        setToast({ message: "Webhook removed successfully", type: "success" });
      } else {
        setToast({ message: "Failed to remove webhook", type: "error" });
      }
    } catch (err) {
      setToast({ message: "Failed to connect to API", type: "error" });
    }
  };

  const handleToggleWebhook = async (webhook: Webhook) => {
    try {
      const res = await apiFetch(`/v1/projects/${projectId}/webhooks/${webhook.id}`, {
        method: "PUT",
        body: JSON.stringify({
          url: webhook.url,
          trigger_type: webhook.trigger_type,
          is_active: !webhook.is_active
        })
      });
      if (res.ok) {
        const updated = await res.json();
        setWebhooks(webhooks.map((w) => (w.id === webhook.id ? updated : w)));
        setToast({ message: "Webhook configuration toggled!", type: "success" });
      } else {
        setToast({ message: "Failed to update webhook status", type: "error" });
      }
    } catch (err) {
      setToast({ message: "Failed to connect to API", type: "error" });
    }
  };

  // Google Sheets sync actions
  const handleSaveSheets = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingSheets(true);
    try {
      const res = await apiFetch(`/v1/projects/${projectId}/integrations/google-sheets`, {
        method: "POST",
        body: JSON.stringify({
          google_sheet_url: sheetsConfig.google_sheet_url,
          google_sheet_sync_enabled: sheetsConfig.google_sheet_sync_enabled
        })
      });
      if (res.ok) {
        setToast({ message: "Google Sheets sync configuration saved!", type: "success" });
      } else {
        const err = await res.json();
        setToast({ message: err.detail || "Failed to update Sheets config", type: "error" });
      }
    } catch (err) {
      setToast({ message: "Failed to connect to API", type: "error" });
    } finally {
      setSavingSheets(false);
    }
  };

  // CSV Downloader
  const handleDownloadCsv = async () => {
    try {
      const res = await apiFetch(`/v1/projects/${projectId}/export/csv`);
      if (!res.ok) {
        throw new Error("Target dataset is empty or not yet generated");
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `project_${projectId}_data.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      setToast({ message: "CSV file downloaded successfully", type: "success" });
    } catch (err: any) {
      setToast({ message: err.message || "Failed to download export", type: "error" });
    }
  };

  if (loading) {
    return <div className="shimmer" style={{ height: "400px", borderRadius: "10px" }} />;
  }

  if (!project) {
    return (
      <div style={{ textAlign: "center", padding: "4rem" }}>
        <h3>Project not found</h3>
        <button className="btn btn-secondary" style={{ marginTop: "1rem" }} onClick={() => router.push("/dashboard")}>
          Back to Dashboard
        </button>
      </div>
    );
  }

  if (!endpoint) {
    return (
      <div style={{ textAlign: "center", padding: "4rem" }}>
        <h3>API Endpoint not deployed</h3>
        <p style={{ color: "var(--text-secondary)", marginTop: "0.5rem" }}>
          This project is in draft mode. Run the scraper setup wizard to configure the extraction schema and deploy your endpoint.
        </p>
        <button className="btn btn-primary" style={{ marginTop: "1.5rem" }} onClick={() => router.push("/dashboard/new")}>
          Run Setup Wizard 🚀
        </button>
      </div>
    );
  }

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const fullApiUrl = `${API_BASE}/v1/apis${endpoint.path}`;
  const curlCommand = `curl -H "X-API-KEY: ${apiKey || "[YOUR_API_KEY]"}" \\\n  "${fullApiUrl}"`;

  return (
    <div>
      <header className="dashboard-header">
        <div>
          <a href="/dashboard" style={{ color: "var(--text-secondary)", fontSize: "0.9rem", display: "flex", gap: "0.25rem", alignItems: "center", marginBottom: "0.5rem" }}>
            <span>←</span> Back to Dashboard
          </a>
          <h1>{project.name}</h1>
          <p style={{ color: "var(--text-secondary)", marginTop: "0.25rem" }}>
            API ID: <code style={{ color: "var(--secondary)" }}>{project.id}</code>
          </p>
        </div>
        <span className="badge badge-success" style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem" }}>
          <span className="pulse-indicator"></span> Live Gateway
        </span>
      </header>

      {/* Navigation Tabs */}
      <div style={{ display: "flex", gap: "1rem", borderBottom: "1px solid var(--border-color)", marginBottom: "2.5rem", paddingBottom: "0.5rem" }}>
        <button
          className={`btn ${activeTab === "explorer" ? "btn-primary" : "btn-secondary"}`}
          style={{ padding: "0.6rem 1.5rem", fontSize: "0.95rem" }}
          onClick={() => setActiveTab("explorer")}
        >
          🔍 API Explorer & Editor
        </button>
        <button
          className={`btn ${activeTab === "integrations" ? "btn-primary" : "btn-secondary"}`}
          style={{ padding: "0.6rem 1.5rem", fontSize: "0.95rem" }}
          onClick={() => setActiveTab("integrations")}
        >
          🔌 Webhooks & Sync
        </button>
        <button
          className={`btn ${activeTab === "export" ? "btn-primary" : "btn-secondary"}`}
          style={{ padding: "0.6rem 1.5rem", fontSize: "0.95rem" }}
          onClick={() => setActiveTab("export")}
        >
          📥 CSV Data Export
        </button>
      </div>

      {/* Tab: API Explorer & Editor */}
      {activeTab === "explorer" && (
        <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "2rem" }}>
          
          {/* Test Console */}
          <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
            
            {/* Endpoint Details Card */}
            <div className="card">
              <h3>Endpoint Gateway Details</h3>
              <div style={{ marginTop: "1.5rem", display: "flex", flexDirection: "column", gap: "1rem" }}>
                <div className="swagger-panel">
                  <div className="endpoint-tag endpoint-get">
                    <span className="method-badge method-get">GET</span>
                    <strong style={{ color: "var(--text-primary)" }}>{endpoint.path}</strong>
                  </div>
                </div>
                
                <div className="form-group">
                  <label className="form-label">X-API-KEY Header (Authorization)</label>
                  <input
                    type="text"
                    className="input-text"
                    style={{ fontFamily: "var(--font-mono)", fontSize: "0.85rem" }}
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="Paste your sk_live_... API credential key here"
                  />
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderTop: "1px solid var(--border-color)", paddingTop: "1rem" }}>
                  <span>Cache TTL: <strong>{endpoint.cache_ttl_sec / 60} mins</strong></span>
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    <button className="btn btn-secondary" onClick={handleManualRefresh} disabled={refreshing}>
                      {refreshing ? "Refreshing..." : "Force Crawl Refresh"}
                    </button>
                    <button className="btn btn-primary" onClick={handleTestCall} disabled={queryLoading}>
                      {queryLoading ? "Fetching..." : "Run Test Query ⚡"}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Console Output Card */}
            <div className="card" style={{ display: "flex", flexDirection: "column" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <h3>Console Output Response</h3>
                {cacheStatus && (
                  <span className="badge badge-success">
                    X-Cache: {cacheStatus}
                  </span>
                )}
              </div>
              <pre style={{
                minHeight: "200px",
                backgroundColor: "var(--bg-primary)",
                border: "1px solid var(--border-color)",
                padding: "1rem",
                borderRadius: "var(--radius-md)",
                color: "var(--text-primary)",
                fontSize: "0.85rem",
                overflow: "auto",
                maxHeight: "350px",
                whiteSpace: "pre-wrap"
              }}>
                {queryResponse || "// Click 'Run Test Query' or run advanced code sandbox tests to inspect output."}
              </pre>
            </div>

            {/* Advanced Python Code Editor Card */}
            <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ margin: 0, display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <span>🐍</span> Custom BeautifulSoup Code Editor
                </h3>
                <span className="badge badge-success" style={{ backgroundColor: "rgba(168, 85, 247, 0.12)", color: "#a855f7", border: "1px solid rgba(168, 85, 247, 0.25)" }}>
                  AST Sandbox Mode
                </span>
              </div>
              <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: 0 }}>
                Adjust or write custom Python BeautifulSoup code directly. Hit test to dry-run it inside our restricted AST-verified execution sandbox.
              </p>
              <textarea
                className="input-text"
                style={{
                  width: "100%",
                  height: "300px",
                  fontFamily: "var(--font-mono)",
                  fontSize: "0.85rem",
                  backgroundColor: "#0d0e15",
                  color: "#e2e8f0",
                  padding: "0.8rem",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--border-color)",
                  resize: "vertical"
                }}
                value={extractorCode}
                onChange={(e) => setExtractorCode(e.target.value)}
                placeholder="def extract(html_content, dom_tree): ..."
              />
              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem", borderTop: "1px solid var(--border-color)", paddingTop: "1rem" }}>
                <button 
                  className="btn btn-secondary" 
                  onClick={handleTestCustomCode} 
                  disabled={testingCode || !extractorCode}
                >
                  {testingCode ? "Testing Sandbox..." : "Run Sandbox Test ⚡"}
                </button>
                <button 
                  className="btn btn-primary" 
                  onClick={handleSaveCustomCode} 
                  disabled={savingCode || !extractorCode}
                >
                  {savingCode ? "Deploying..." : "Save & Deploy Live 🚀"}
                </button>
              </div>
            </div>

          </div>

          {/* OpenAPI specs and tools */}
          <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
            
            {/* Code snippet snippets */}
            <div className="card">
              <h3>cURL Request Snippet</h3>
              <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "0.25rem 0 1rem" }}>
                Integrate this parser into your local script environment.
              </p>
              <div style={{ position: "relative" }}>
                <pre style={{ backgroundColor: "#14161f", padding: "1rem", borderRadius: "var(--radius-md)", fontSize: "0.8rem", color: "var(--text-primary)", overflowX: "auto" }}>
                  {curlCommand}
                </pre>
                <button
                  className="btn btn-secondary"
                  style={{ position: "absolute", right: "8px", top: "8px", padding: "0.3rem 0.6rem", fontSize: "0.75rem" }}
                  onClick={() => {
                    navigator.clipboard.writeText(curlCommand);
                    setToast({ message: "cURL command copied to clipboard", type: "success" });
                  }}
                >
                  Copy
                </button>
              </div>
            </div>

            {/* Schema Explorer */}
            <div className="card">
              <h3>Response Schema specification</h3>
              <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "0.25rem 0 1rem" }}>
                OpenAPI definition showing expected payload structure.
              </p>
              <pre style={{ backgroundColor: "#14161f", padding: "1rem", borderRadius: "var(--radius-md)", fontSize: "0.8rem", color: "var(--text-secondary)", overflowX: "auto" }}>
                {schemaSpec ? JSON.stringify(schemaSpec, null, 2) : `{\n  "type": "object",\n  "properties": {\n    "data": {\n      "type": "array",\n      "items": {\n        "type": "object"\n      }\n    }\n  }\n}`}
              </pre>
            </div>

            {/* Scraper Health stats */}
            <div className="card">
              <h3>Scraper Health Logs</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "1rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.9rem" }}>
                  <span style={{ color: "var(--text-secondary)" }}>Total Request Logs</span>
                  <strong>{requestCount} hits</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.9rem" }}>
                  <span style={{ color: "var(--text-secondary)" }}>Last Endpoint Hit</span>
                  <strong>{lastHit ? new Date(lastHit).toLocaleString() : "Never hit"}</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.9rem" }}>
                  <span style={{ color: "var(--text-secondary)" }}>DOM Selector Drift</span>
                  <strong style={{ color: "var(--success)" }}>None (0% drift)</strong>
                </div>
              </div>
            </div>

          </div>

        </div>
      )}

      {/* Tab: Integrations & Webhooks */}
      {activeTab === "integrations" && (
        <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "2rem" }}>
          
          {/* Left panel: Webhooks Config */}
          <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
            <div>
              <h3>Webhooks & Data Drift Targets</h3>
              <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginTop: "0.25rem" }}>
                Configure HTTP POST destinations to notify your microservices dynamically whenever the crawled page data drifts or changes.
              </p>
            </div>

            <form onSubmit={handleCreateWebhook} style={{ display: "flex", gap: "0.75rem", alignItems: "flex-end" }}>
              <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
                <label className="form-label">Endpoint Destination URL</label>
                <input
                  type="url"
                  className="input-text"
                  placeholder="https://your-service.com/api/webhooks/scrapers"
                  value={newWebhookUrl}
                  onChange={(e) => setNewWebhookUrl(e.target.value)}
                  required
                />
              </div>
              <button type="submit" className="btn btn-primary" style={{ height: "45px" }}>
                Register Webhook
              </button>
            </form>

            <div style={{ borderTop: "1px solid var(--border-color)", paddingTop: "1rem" }}>
              <h4 style={{ marginBottom: "1rem" }}>Registered Targets</h4>
              {loadingIntegrations ? (
                <div className="shimmer" style={{ height: "100px", borderRadius: "8px" }} />
              ) : webhooks.length === 0 ? (
                <p style={{ color: "var(--text-muted)", fontSize: "0.9rem", fontStyle: "italic" }}>
                  No active webhooks registered for this project.
                </p>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  {webhooks.map((w) => (
                    <div 
                      key={w.id} 
                      style={{ 
                        display: "flex", 
                        alignItems: "center", 
                        justifyContent: "space-between", 
                        padding: "0.75rem 1rem", 
                        backgroundColor: "var(--bg-tertiary)", 
                        border: "1px solid var(--border-color)", 
                        borderRadius: "var(--radius-md)" 
                      }}
                    >
                      <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem", overflow: "hidden" }}>
                        <code style={{ fontSize: "0.85rem", color: "var(--text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {w.url}
                        </code>
                        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                          Trigger: <code>{w.trigger_type}</code>
                        </span>
                      </div>
                      
                      <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                          <input
                            type="checkbox"
                            checked={w.is_active}
                            onChange={() => handleToggleWebhook(w)}
                            style={{ cursor: "pointer", width: "16px", height: "16px", accentColor: "var(--primary)" }}
                          />
                          <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                            {w.is_active ? "Active" : "Disabled"}
                          </span>
                        </div>

                        <button 
                          onClick={() => handleDeleteWebhook(w.id)}
                          style={{ background: "none", border: "none", color: "var(--error)", cursor: "pointer", fontSize: "0.85rem" }}
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right panel: Google Sheets Config */}
          <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
            <div>
              <h3>Google Sheets Sync</h3>
              <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginTop: "0.25rem" }}>
                Simulate writing and appending scraped layout changes directly into a specified spreadsheet document.
              </p>
            </div>

            <form onSubmit={handleSaveSheets} style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Google Spreadsheet URL</label>
                <input
                  type="url"
                  className="input-text"
                  placeholder="https://docs.google.com/spreadsheets/d/..."
                  value={sheetsConfig.google_sheet_url}
                  onChange={(e) => setSheetsConfig({ ...sheetsConfig, google_sheet_url: e.target.value })}
                  required
                />
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                <input
                  id="sheets-sync-toggle"
                  type="checkbox"
                  checked={sheetsConfig.google_sheet_sync_enabled}
                  onChange={(e) => setSheetsConfig({ ...sheetsConfig, google_sheet_sync_enabled: e.target.checked })}
                  style={{ width: "18px", height: "18px", accentColor: "var(--primary)", cursor: "pointer" }}
                />
                <label htmlFor="sheets-sync-toggle" style={{ fontSize: "0.9rem", fontWeight: 500, cursor: "pointer" }}>
                  Auto-sync on Cache Refresh cycles
                </label>
              </div>

              <button 
                type="submit" 
                className="btn btn-primary" 
                style={{ width: "100%", marginTop: "1rem" }}
                disabled={savingSheets}
              >
                {savingSheets ? "Saving Config..." : "Save Integration Link"}
              </button>
            </form>
          </div>

        </div>
      )}

      {/* Tab: CSV Data Export */}
      {activeTab === "export" && (
        <div style={{ maxWidth: "700px", margin: "0 auto" }} className="card">
          <div style={{ textAlign: "center", padding: "2.5rem 1rem" }}>
            <span style={{ fontSize: "3.5rem" }}>📥</span>
            <h3 style={{ marginTop: "1.5rem" }}>Export Dataset File</h3>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem", maxWidth: "500px", margin: "0.5rem auto 2.5rem" }}>
              Download the current cached API layout dataset directly into a fully structured CSV file matching your active schema configurations.
            </p>

            <div style={{ display: "flex", justifyContent: "center", gap: "1rem" }}>
              <button 
                className="btn btn-secondary" 
                onClick={() => {
                  if (queryResponse) {
                    const blob = new Blob([queryResponse], { type: "application/json" });
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = `project_${projectId}_export.json`;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    window.URL.revokeObjectURL(url);
                    setToast({ message: "JSON file downloaded successfully", type: "success" });
                  } else {
                    setToast({ message: "Run a test query first to cache response payload", type: "error" });
                  }
                }}
              >
                Download Raw JSON
              </button>
              
              <button className="btn btn-primary" onClick={handleDownloadCsv}>
                Download Formatted CSV
              </button>
            </div>
          </div>
        </div>
      )}

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
