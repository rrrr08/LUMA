"use client";

import React, { useState, useEffect } from "react";
import { apiFetch } from "../../lib/api-client";
import Toast from "../../components/Toast";

interface Project {
  id: string;
  name: string;
  status: string;
  path?: string;
  target_url?: string;
}

interface Stats {
  total_requests: number;
  requests_this_month: number;
  cache_hit_rate: number;
  avg_response_ms: number;
  crawl_success_rate: number;
  active_endpoints: number;
}

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [stats, setStats] = useState<Stats>({
    total_requests: 0,
    requests_this_month: 0,
    cache_hit_rate: 0,
    avg_response_ms: 0,
    crawl_success_rate: 1.0,
    active_endpoints: 0
  });
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

  // Load projects and stats from API
  useEffect(() => {
    async function loadData() {
      try {
        const projectsRes = await apiFetch("/v1/projects");
        if (projectsRes.ok) {
          const data = await projectsRes.json();
          setProjects(data);
        }

        const statsRes = await apiFetch("/v1/analytics/summary");
        if (statsRes.ok) {
          const statsData = await statsRes.json();
          setStats(statsData);
        }
      } catch (err) {
        console.error("Failed to load dashboard data:", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const handleDeleteProject = async (id: string) => {
    if (
      !confirm(
        "Are you sure you want to delete this project? This will permanently remove its deployed endpoint, caching setup, and generated parser code."
      )
    ) {
      return;
    }

    try {
      const response = await apiFetch(`/v1/projects/${id}`, {
        method: "DELETE"
      });

      if (response.ok) {
        setProjects(projects.filter((p) => p.id !== id));
        setToast({ message: "Project deleted successfully", type: "success" });
        
        // Refresh stats
        const statsRes = await apiFetch("/v1/analytics/summary");
        if (statsRes.ok) {
          const statsData = await statsRes.json();
          setStats(statsData);
        }
      } else {
        const err = await response.json();
        setToast({ message: err.detail || "Failed to delete project", type: "error" });
      }
    } catch {
      setToast({ message: "Network error occurred. Try again.", type: "error" });
    }
  };

  return (
    <div>
      <header className="dashboard-header">
        <div>
          <h1>Dashboard</h1>
          <p style={{ color: "var(--text-secondary)", marginTop: "0.25rem" }}>
            Overview of your active crawler-generated API endpoints.
          </p>
        </div>
        <a href="/dashboard/new" className="btn btn-primary">
          <span>+</span> Create New API
        </a>
      </header>

      {/* Metrics Row */}
      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1.5rem", marginBottom: "2.5rem" }}>
        <div className="card">
          <div className="card-title">
            <span style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>Active Endpoints</span>
            <span style={{ fontSize: "1.25rem" }}>🔌</span>
          </div>
          <h2 style={{ fontSize: "2rem", fontWeight: "700" }}>{stats.active_endpoints}</h2>
          <span style={{ fontSize: "0.8rem", color: "var(--success)" }}>● All gateway systems online</span>
        </div>
        <div className="card">
          <div className="card-title">
            <span style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>Total Requests</span>
            <span style={{ fontSize: "1.25rem" }}>📈</span>
          </div>
          <h2 style={{ fontSize: "2rem", fontWeight: "700" }}>{stats.total_requests.toLocaleString()}</h2>
          <span style={{ fontSize: "0.8rem", color: "var(--success)" }}>
            {stats.requests_this_month} requests this month
          </span>
        </div>
        <div className="card">
          <div className="card-title">
            <span style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>Crawl Success Rate</span>
            <span style={{ fontSize: "1.25rem" }}>✓</span>
          </div>
          <h2 style={{ fontSize: "2rem", fontWeight: "700" }}>
            {(stats.crawl_success_rate * 100).toFixed(1)}%
          </h2>
          <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
            Average latency: {stats.avg_response_ms.toFixed(0)}ms
          </span>
        </div>
        <div className="card">
          <div className="card-title">
            <span style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>Cache Hit Ratio</span>
            <span style={{ fontSize: "1.25rem" }}>💾</span>
          </div>
          <h2 style={{ fontSize: "2rem", fontWeight: "700" }}>
            {(stats.cache_hit_rate * 100).toFixed(1)}%
          </h2>
          <span style={{ fontSize: "0.8rem", color: "var(--primary)" }}>
            Saved {Math.round(stats.total_requests * stats.cache_hit_rate * 4.2)}k AI tokens
          </span>
        </div>
      </section>

      {/* Projects List Card */}
      <div className="card" style={{ padding: "1.5rem" }}>
        <h3 style={{ marginBottom: "1rem" }}>Your Live APIs</h3>
        {loading ? (
          <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-secondary)" }}>
            <div className="shimmer" style={{ height: "40px", borderRadius: "6px", marginBottom: "0.75rem" }}></div>
            <div className="shimmer" style={{ height: "40px", borderRadius: "6px" }}></div>
          </div>
        ) : projects.length === 0 ? (
          <div style={{ padding: "3rem", textAlign: "center", border: "1px dashed var(--border-color)", borderRadius: "var(--radius-md)" }}>
            <span style={{ fontSize: "2.5rem" }}>🕵️‍♂️</span>
            <h4 style={{ marginTop: "1rem" }}>No API endpoints found</h4>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", margin: "0.5rem 0 1.5rem" }}>
              Submit your first website URL to start generating structured endpoints.
            </p>
            <a href="/dashboard/new" className="btn btn-primary">
              Run Setup Wizard
            </a>
          </div>
        ) : (
          <div className="table-container">
            <table className="table-custom">
              <thead>
                <tr>
                  <th>API Name</th>
                  <th>Gateway Route</th>
                  <th>Crawl Target</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {projects.map((proj) => (
                  <tr key={proj.id}>
                    <td style={{ fontWeight: "600" }}>{proj.name}</td>
                    <td>
                      {proj.path ? (
                        <code style={{ color: "var(--info)", backgroundColor: "rgba(6, 182, 212, 0.08)", padding: "0.2rem 0.5rem", borderRadius: "4px" }}>
                          GET /v1/apis{proj.path}
                        </code>
                      ) : (
                        <span style={{ color: "var(--text-secondary)", fontSize: "0.85rem", fontStyle: "italic" }}>
                          Not deployed
                        </span>
                      )}
                    </td>
                    <td style={{ fontSize: "0.85rem", color: "var(--text-secondary)", maxWidth: "250px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {proj.target_url || (
                        <span style={{ color: "var(--text-secondary)", fontStyle: "italic" }}>
                          No target URL
                        </span>
                      )}
                    </td>
                    <td>
                      {proj.status === "active" && proj.path ? (
                        <span className="badge badge-success" style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem" }}>
                          <span className="pulse-indicator"></span> Active
                        </span>
                      ) : (
                        <span className="badge badge-warning" style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem", backgroundColor: "rgba(245, 158, 11, 0.1)", color: "var(--warning)", border: "1px solid rgba(245, 158, 11, 0.2)" }}>
                          Draft
                        </span>
                      )}
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: "0.5rem" }}>
                        <a href={`/dashboard/apis/${proj.id}`} className="btn btn-secondary" style={{ padding: "0.4rem 0.8rem", fontSize: "0.8rem" }}>
                          Open Explorer
                        </a>
                        <button
                          onClick={() => handleDeleteProject(proj.id)}
                          style={{
                            padding: "0.4rem 0.8rem",
                            fontSize: "0.8rem",
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
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
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
