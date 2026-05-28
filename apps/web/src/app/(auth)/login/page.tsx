"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../../../context/AuthContext";
import { apiFetch } from "../../../lib/api-client";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const { login } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await apiFetch("/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json();

      if (response.ok) {
        await login(data.access_token);
        router.push("/dashboard");
      } else {
        setError(data.detail || "Failed to authenticate. Please check your credentials.");
      }
    } catch (err) {
      setError("A network error occurred. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      minHeight: "100vh",
      backgroundColor: "#030712",
      color: "#f3f4f6",
      fontFamily: "system-ui, -apple-system, sans-serif",
      padding: "1.5rem",
      position: "relative",
      overflow: "hidden"
    }}>
      {/* Background glow decorator */}
      <div style={{
        position: "absolute",
        top: "25%",
        left: "50%",
        transform: "translate(-50%, -50%)",
        width: "400px",
        height: "400px",
        background: "radial-gradient(circle, rgba(99, 102, 241, 0.15) 0%, transparent 70%)",
        zIndex: 0,
        pointerEvents: "none"
      }} />

      <div style={{
        width: "100%",
        maxWidth: "420px",
        backgroundColor: "#111827",
        border: "1px solid #374151",
        borderRadius: "16px",
        padding: "2.5rem 2rem",
        boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
        zIndex: 1,
        backdropFilter: "blur(8px)"
      }}>
        <div style={{ textAlign: "center", marginBottom: "2.5rem" }}>
          <div style={{ fontSize: "2.5rem", marginBottom: "0.5rem" }}>⚡</div>
          <h2 style={{
            fontSize: "1.8rem",
            fontWeight: "800",
            background: "linear-gradient(135deg, #ffffff, #a855f7, #6366f1)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            margin: "0 0 0.5rem 0"
          }}>Welcome Back</h2>
          <p style={{ color: "#9ca3af", fontSize: "0.875rem", margin: 0 }}>
            Sign in to manage your agentic scraper APIs
          </p>
        </div>

        {error && (
          <div style={{
            backgroundColor: "rgba(239, 68, 68, 0.1)",
            border: "1px solid rgba(239, 68, 68, 0.25)",
            color: "#ef4444",
            borderRadius: "8px",
            padding: "0.75rem 1rem",
            fontSize: "0.85rem",
            marginBottom: "1.5rem",
            lineHeight: "1.4"
          }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            <label style={{ fontSize: "0.8rem", fontWeight: "600", color: "#9ca3af", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Email Address
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="name@company.com"
              style={{
                backgroundColor: "#1f2937",
                border: "1px solid #374151",
                borderRadius: "8px",
                padding: "0.75rem 1rem",
                color: "#ffffff",
                fontSize: "0.95rem",
                outline: "none",
                transition: "border-color 0.2s"
              }}
              onFocus={(e) => (e.target.style.borderColor = "#6366f1")}
              onBlur={(e) => (e.target.style.borderColor = "#374151")}
            />
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            <label style={{ fontSize: "0.8rem", fontWeight: "600", color: "#9ca3af", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="••••••••"
              style={{
                backgroundColor: "#1f2937",
                border: "1px solid #374151",
                borderRadius: "8px",
                padding: "0.75rem 1rem",
                color: "#ffffff",
                fontSize: "0.95rem",
                outline: "none",
                transition: "border-color 0.2s"
              }}
              onFocus={(e) => (e.target.style.borderColor = "#6366f1")}
              onBlur={(e) => (e.target.style.borderColor = "#374151")}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              marginTop: "0.5rem",
              backgroundColor: "#6366f1",
              color: "#ffffff",
              border: "none",
              borderRadius: "8px",
              padding: "0.85rem",
              fontSize: "1rem",
              fontWeight: "600",
              cursor: loading ? "not-allowed" : "pointer",
              opacity: loading ? 0.75 : 1,
              transition: "background-color 0.2s, transform 0.1s",
            }}
            onMouseEnter={(e) => {
              if (!loading) e.currentTarget.style.backgroundColor = "#4f46e5";
            }}
            onMouseLeave={(e) => {
              if (!loading) e.currentTarget.style.backgroundColor = "#6366f1";
            }}
          >
            {loading ? "Signing in..." : "Sign In"}
          </button>
        </form>

        <p style={{
          textAlign: "center",
          fontSize: "0.85rem",
          color: "#9ca3af",
          marginTop: "2rem",
          marginBottom: 0
        }}>
          Don't have an account?{" "}
          <a href="/register" style={{ color: "#818cf8", textDecoration: "none", fontWeight: "500" }}>
            Register here
          </a>
        </p>
      </div>
    </div>
  );
}
