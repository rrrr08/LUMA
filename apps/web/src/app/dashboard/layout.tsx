"use client";

import React from "react";
import SidebarNav from "../../components/SidebarNav";
import AuthGuard from "../../components/AuthGuard";
import { useAuth } from "../../context/AuthContext";

export default function DashboardLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const { user, logout } = useAuth();

  return (
    <AuthGuard>
      <div className="app-container">
        <aside className="sidebar">
          <div className="logo">
            <span>⚡</span> PageToAPI
          </div>
          <nav style={{ flex: 1 }}>
            <SidebarNav />
          </nav>
          <div style={{ padding: "0.5rem", fontSize: "0.85rem", color: "var(--text-muted)", borderTop: "1px solid var(--border-color)" }}>
            Logged in as:<br/>
            <strong style={{ color: "var(--text-secondary)", wordBreak: "break-all" }}>{user?.email || ""}</strong>
            {user?.plan && (
              <div style={{ marginTop: "0.5rem" }}>
                <span style={{
                  padding: "0.2rem 0.5rem",
                  fontSize: "0.75rem",
                  fontWeight: 700,
                  borderRadius: "4px",
                  display: "inline-block",
                  textTransform: "uppercase",
                  background: user.plan === "startup" ? "rgba(168, 85, 247, 0.15)" : user.plan === "pro" ? "rgba(99, 102, 241, 0.15)" : "rgba(255, 255, 255, 0.08)",
                  color: user.plan === "startup" ? "#c084fc" : user.plan === "pro" ? "#818cf8" : "var(--text-secondary)",
                  border: `1px solid ${user.plan === "startup" ? "rgba(168, 85, 247, 0.3)" : user.plan === "pro" ? "rgba(99, 102, 241, 0.3)" : "rgba(255, 255, 255, 0.15)"}`
                }}>
                  {user.plan} Plan
                </span>
              </div>
            )}
            <button 
              onClick={logout} 
              style={{
                marginTop: "0.5rem",
                width: "100%",
                padding: "0.35rem",
                fontSize: "0.75rem",
                background: "rgba(244, 63, 94, 0.1)",
                border: "1px solid rgba(244, 63, 94, 0.2)",
                color: "#f43f5e",
                borderRadius: "4px",
                cursor: "pointer",
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
              Sign Out
            </button>
          </div>
        </aside>
        <main className="main-content">
          {children}
        </main>
      </div>
    </AuthGuard>
  );
}
