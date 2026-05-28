import React from "react";

export default function Home() {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "80vh", textAlign: "center", padding: "2rem" }}>
      <div style={{
        position: "absolute",
        top: "20%",
        left: "50%",
        transform: "translateX(-50%)",
        width: "350px",
        height: "350px",
        background: "radial-gradient(circle, rgba(99, 102, 241, 0.15) 0%, transparent 70%)",
        zIndex: 0,
        pointerEvents: "none"
      }} />

      <div style={{ zIndex: 1, maxWidth: "650px" }}>
        <span className="badge badge-success" style={{ marginBottom: "1.5rem", letterSpacing: "0.05em", padding: "0.4rem 0.8rem", borderRadius: "100px" }}>
          🚀 AGENTIC SCRAPER PLATFORM
        </span>
        <h1 style={{ fontSize: "3.2rem", fontWeight: "800", lineHeight: "1.15", background: "linear-gradient(135deg, #ffffff, #a855f7, #6366f1)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", marginBottom: "1rem" }}>
          Any Website.<br/>
          Instantly a REST API.
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "1.15rem", marginBottom: "2rem", lineHeight: "1.6" }}>
          Paste a URL. Our multimodal agents crawl the visual page structure, identify schemas, write safe sandboxed parser code, and deploy secure, Redis-cached API gateways in under 60 seconds.
        </p>
        <div style={{ display: "flex", gap: "1rem", justifyContent: "center" }}>
          <a href="/dashboard" className="btn btn-primary" style={{ padding: "0.85rem 2rem", fontSize: "1.05rem" }}>
            Go to Console Dashboard
          </a>
          <a href="/dashboard/new" className="btn btn-secondary" style={{ padding: "0.85rem 2rem", fontSize: "1.05rem" }}>
            Launch New API Wizard
          </a>
        </div>
      </div>

      <section style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "1.5rem", width: "100%", maxWidth: "800px", marginTop: "4.5rem", zIndex: 1 }}>
        <div className="card" style={{ padding: "1.25rem", textAlign: "left" }}>
          <h4 style={{ marginBottom: "0.5rem", color: "var(--info)" }}>1. Crawl & Render</h4>
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
            Playwright crawls javascript-rendered elements and captures visual layouts.
          </p>
        </div>
        <div className="card" style={{ padding: "1.25rem", textAlign: "left" }}>
          <h4 style={{ marginBottom: "0.5rem", color: "var(--secondary)" }}>2. Multimodal Mapping</h4>
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
            GPT-4o Vision processes screenshots + DOM trees to deduce schemas dynamically.
          </p>
        </div>
        <div className="card" style={{ padding: "1.25rem", textAlign: "left" }}>
          <h4 style={{ marginBottom: "0.5rem", color: "var(--primary)" }}>3. Sandbox Generation</h4>
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
            Engine generates clean code, runs security AST checks, and deploys.
          </p>
        </div>
      </section>
    </div>
  );
}
