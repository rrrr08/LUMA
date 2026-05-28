import React from "react";

export default function Home() {
  return (
    <div style={{ 
      display: "flex", 
      flexDirection: "column", 
      minHeight: "100vh",
      backgroundColor: "var(--bg-primary)",
      position: "relative",
      overflow: "hidden"
    }}>
      {/* Background Glow Blobs */}
      <div style={{
        position: "absolute",
        top: "-10%",
        left: "30%",
        width: "600px",
        height: "600px",
        background: "radial-gradient(circle, rgba(139, 92, 246, 0.08) 0%, transparent 70%)",
        zIndex: 0,
        pointerEvents: "none"
      }} />
      <div style={{
        position: "absolute",
        bottom: "10%",
        right: "-10%",
        width: "500px",
        height: "500px",
        background: "radial-gradient(circle, rgba(6, 182, 212, 0.08) 0%, transparent 70%)",
        zIndex: 0,
        pointerEvents: "none"
      }} />

      {/* Floating animation setup */}
      <style>{`
        @keyframes float {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-6px); }
        }
        @keyframes glow {
          0%, 100% { opacity: 0.8; filter: drop-shadow(0 0 15px rgba(139, 92, 246, 0.4)); }
          50% { opacity: 1; filter: drop-shadow(0 0 25px rgba(236, 72, 153, 0.6)); }
        }
      `}</style>

      {/* Premium Glassmorphic Navbar */}
      <header style={{
        zIndex: 10,
        backdropFilter: "blur(12px)",
        background: "rgba(9, 10, 15, 0.7)",
        borderBottom: "1px solid var(--border-color)",
        position: "sticky",
        top: 0
      }}>
        <div style={{
          maxWidth: "1100px",
          margin: "0 auto",
          padding: "1rem 2rem",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center"
        }}>
          <div style={{ letterSpacing: "0.1em", display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span style={{ fontSize: "1.5rem", fontWeight: "900", background: "linear-gradient(135deg, #ec4899, #8b5cf6, #3b82f6)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>▲</span> 
            <span style={{ fontSize: "1.35rem", fontWeight: "900", textTransform: "uppercase", background: "linear-gradient(135deg, #ffffff, #f472b6, #a78bfa, #60a5fa)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>PRISM</span>
          </div>

          <nav style={{ display: "flex", gap: "2rem", alignItems: "center" }}>
            <a href="#features" style={{ color: "var(--text-secondary)", fontSize: "0.9rem", fontWeight: "500" }}>Features</a>
            <a href="/dashboard/billing" style={{ color: "var(--text-secondary)", fontSize: "0.9rem", fontWeight: "500" }}>Pricing</a>
            <a href="https://github.com/rrrr08/LUMA" target="_blank" rel="noopener noreferrer" style={{ color: "var(--text-secondary)", fontSize: "0.9rem", fontWeight: "500" }}>Docs</a>
            <a href="/dashboard" className="btn btn-primary" style={{ padding: "0.5rem 1.25rem", fontSize: "0.85rem", borderRadius: "8px", background: "linear-gradient(135deg, #8b5cf6, #ec4899)" }}>
              Console Dashboard
            </a>
          </nav>
        </div>
      </header>

      {/* Hero Section */}
      <main style={{ 
        flex: 1, 
        zIndex: 1, 
        display: "flex", 
        flexDirection: "column", 
        alignItems: "center", 
        justifyContent: "center", 
        padding: "4.5rem 2rem",
        textAlign: "center" 
      }}>
        <div style={{ maxWidth: "850px", margin: "0 auto" }}>
          <span className="badge" style={{ 
            marginBottom: "1.5rem", 
            letterSpacing: "0.08em", 
            padding: "0.45rem 1rem", 
            borderRadius: "100px",
            background: "rgba(139, 92, 246, 0.12)",
            border: "1px solid rgba(139, 92, 246, 0.2)",
            color: "#a78bfa",
            fontSize: "0.8rem",
            textTransform: "uppercase",
            fontWeight: 600
          }}>
            ✦  AI-Powered Agentic Web Scraper
          </span>
          
          <h1 style={{ 
            fontSize: "4.2rem", 
            fontWeight: "950", 
            lineHeight: "1.05", 
            letterSpacing: "-0.04em",
            background: "linear-gradient(135deg, #ffffff 20%, #f472b6 50%, #a78bfa 75%, #60a5fa 100%)", 
            WebkitBackgroundClip: "text", 
            WebkitTextFillColor: "transparent", 
            marginBottom: "1.5rem" 
          }}>
            Refracting Websites<br/>
            Into Live REST APIs.
          </h1>
          
          <p style={{ 
            color: "var(--text-secondary)", 
            fontSize: "1.25rem", 
            marginBottom: "2.5rem", 
            lineHeight: "1.6",
            maxWidth: "680px",
            margin: "0 auto 2.5rem"
          }}>
            Paste any URL. Our autonomous vision agents crawl visual hierarchies, write secure sandboxed parsing pipelines, and compile low-latency, Redis-cached API gateways instantly.
          </p>

          {/* Interactive URL Starter Bar */}
          <div style={{
            background: "rgba(25, 30, 43, 0.65)",
            border: "1px solid var(--border-color)",
            borderRadius: "14px",
            padding: "0.5rem",
            display: "flex",
            gap: "0.5rem",
            maxWidth: "620px",
            margin: "0 auto 3rem",
            boxShadow: "0 10px 40px rgba(0, 0, 0, 0.5)",
            backdropFilter: "blur(8px)"
          }}>
            <input 
              type="text" 
              placeholder="https://example.com/products-list" 
              style={{
                flex: 1,
                background: "transparent",
                border: "none",
                color: "white",
                padding: "0.5rem 1rem",
                outline: "none",
                fontSize: "0.95rem"
              }}
              readOnly
            />
            <a 
              href="/dashboard/new" 
              className="btn btn-primary" 
              style={{ padding: "0.65rem 1.5rem", borderRadius: "10px", background: "linear-gradient(135deg, #8b5cf6, #ec4899)" }}
            >
              Build API Gateway
            </a>
          </div>
        </div>

        {/* Refraction Visualization Panel */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "1fr auto 1fr",
          alignItems: "center",
          gap: "2rem",
          width: "100%",
          maxWidth: "900px",
          background: "rgba(14, 17, 26, 0.65)",
          border: "1px solid var(--border-color)",
          borderRadius: "var(--radius-lg)",
          padding: "2rem",
          margin: "1.5rem auto 5.5rem",
          boxShadow: "var(--shadow)",
          backdropFilter: "blur(12px)",
          position: "relative"
        }}>
          {/* Left: Raw HTML Input */}
          <div style={{
            textAlign: "left",
            background: "#08090d",
            border: "1px solid rgba(255,255,255,0.05)",
            borderRadius: "10px",
            padding: "1rem",
            fontFamily: "var(--font-mono)",
            fontSize: "0.8rem",
            color: "var(--text-muted)",
            height: "180px",
            overflow: "hidden",
            position: "relative"
          }}>
            <div style={{ color: "#ec4899", marginBottom: "0.25rem" }}>&lt;html&gt;</div>
            <div style={{ paddingLeft: "1rem" }}>
              <div style={{ color: "#8b5cf6" }}>&lt;body&gt;</div>
              <div style={{ paddingLeft: "1rem" }}>
                <div style={{ color: "#e2e8f0" }}>&lt;h1 class="title"&gt;MacBook Pro M3&lt;/h1&gt;</div>
                <div style={{ color: "#e2e8f0" }}>&lt;span class="price"&gt;$1,999&lt;/span&gt;</div>
                <div style={{ color: "#3b82f6" }}>&lt;div class="rating"&gt;4.9 Stars&lt;/div&gt;</div>
              </div>
              <div style={{ color: "#8b5cf6" }}>&lt;/body&gt;</div>
            </div>
            <div style={{ color: "#ec4899" }}>&lt;/html&gt;</div>
            <div style={{
              position: "absolute",
              bottom: 0,
              left: 0,
              right: 0,
              height: "40px",
              background: "linear-gradient(to top, #08090d, transparent)"
            }} />
          </div>

          {/* Middle: Glowing Prism Refractor */}
          <div style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            position: "relative"
          }}>
            {/* Pulsing glow circle */}
            <div style={{
              position: "absolute",
              width: "90px",
              height: "90px",
              borderRadius: "50%",
              background: "radial-gradient(circle, rgba(139, 92, 246, 0.2) 0%, transparent 70%)",
              animation: "pulse 3s infinite"
            }} />
            
            {/* Prism Icon */}
            <span style={{
              fontSize: "3.8rem",
              zIndex: 1,
              background: "linear-gradient(135deg, #ec4899, #8b5cf6, #3b82f6, #06b6d4)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              animation: "float 4s infinite ease-in-out, glow 4s infinite ease-in-out",
              cursor: "default"
            }}>
              ▲
            </span>
            <span style={{
              fontSize: "0.7rem",
              fontWeight: 700,
              color: "var(--text-secondary)",
              marginTop: "0.75rem",
              textTransform: "uppercase",
              letterSpacing: "0.2em"
            }}>
              Refract
            </span>
          </div>

          {/* Right: Structured JSON Output */}
          <div style={{
            textAlign: "left",
            background: "#08090d",
            border: "1px solid rgba(255,255,255,0.05)",
            borderRadius: "10px",
            padding: "1rem",
            fontFamily: "var(--font-mono)",
            fontSize: "0.8rem",
            color: "#60a5fa",
            height: "180px",
            overflow: "hidden",
            position: "relative"
          }}>
            <div><span style={{ color: "#a78bfa" }}>&#123;</span></div>
            <div style={{ paddingLeft: "1.25rem" }}>
              <div><span style={{ color: "#34d399" }}>"status"</span>: <span style={{ color: "#f472b6" }}>"success"</span>,</div>
              <div><span style={{ color: "#34d399" }}>"data"</span>: <span style={{ color: "#a78bfa" }}>&#123;</span></div>
              <div style={{ paddingLeft: "1.25rem" }}>
                <div><span style={{ color: "#34d399" }}>"title"</span>: <span style={{ color: "#f472b6" }}>"MacBook Pro M3"</span>,</div>
                <div><span style={{ color: "#34d399" }}>"price"</span>: <span style={{ color: "#fb7185" }}>1999.00</span>,</div>
                <div><span style={{ color: "#34d399" }}>"rating"</span>: <span style={{ color: "#fb7185" }}>4.9</span></div>
              </div>
              <div><span style={{ color: "#a78bfa" }}>&#125;</span></div>
            </div>
            <div><span style={{ color: "#a78bfa" }}>&#125;</span></div>
          </div>
        </div>

        {/* Feature Cards Grid */}
        <section id="features" style={{ 
          display: "grid", 
          gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", 
          gap: "1.75rem", 
          width: "100%", 
          maxWidth: "1000px", 
          textAlign: "left"
        }}>
          <div className="card">
            <div style={{ 
              width: "42px", 
              height: "42px", 
              borderRadius: "10px", 
              background: "rgba(6, 182, 212, 0.1)", 
              display: "flex", 
              alignItems: "center", 
              justifyContent: "center", 
              color: "var(--info)",
              fontSize: "1.3rem",
              marginBottom: "1.25rem",
              border: "1px solid rgba(6, 182, 212, 0.2)"
            }}>
              🕸
            </div>
            <h4 style={{ fontSize: "1.1rem", marginBottom: "0.5rem", color: "var(--text-primary)" }}>1. Crawl & Render</h4>
            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", lineHeight: "1.5" }}>
              Playwright headless crawlers bypass geographical blocks, rotating residential proxies to render complex, client-side JS websites cleanly.
            </p>
          </div>
          
          <div className="card">
            <div style={{ 
              width: "42px", 
              height: "42px", 
              borderRadius: "10px", 
              background: "rgba(168, 85, 247, 0.1)", 
              display: "flex", 
              alignItems: "center", 
              justifyContent: "center", 
              color: "var(--secondary)",
              fontSize: "1.3rem",
              marginBottom: "1.25rem",
              border: "1px solid rgba(168, 85, 247, 0.2)"
            }}>
              🧠
            </div>
            <h4 style={{ fontSize: "1.1rem", marginBottom: "0.5rem", color: "var(--text-primary)" }}>2. Multimodal Mapping</h4>
            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", lineHeight: "1.5" }}>
              GPT-4o Vision processes site layout snapshots and structural DOM nodes to autonomously propose schemas and fields with confidence metrics.
            </p>
          </div>
          
          <div className="card">
            <div style={{ 
              width: "42px", 
              height: "42px", 
              borderRadius: "10px", 
              background: "rgba(99, 102, 241, 0.1)", 
              display: "flex", 
              alignItems: "center", 
              justifyContent: "center", 
              color: "var(--primary)",
              fontSize: "1.3rem",
              marginBottom: "1.25rem",
              border: "1px solid rgba(99, 102, 241, 0.2)"
            }}>
              🔒
            </div>
            <h4 style={{ fontSize: "1.1rem", marginBottom: "0.5rem", color: "var(--text-primary)" }}>3. Sandboxed Pipelines</h4>
            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", lineHeight: "1.5" }}>
              CodeGen writes custom parsing scripts, executes them in isolated timeout-bounded subprocesses after AST safety scans, and outputs JSON.
            </p>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer style={{
        borderTop: "1px solid var(--border-color)",
        padding: "2rem",
        textAlign: "center",
        fontSize: "0.85rem",
        color: "var(--text-muted)",
        zIndex: 1
      }}>
        <p>© {new Date().getFullYear()} PRISM API Inc. All rights reserved. Serverless Web Extraction Engines.</p>
      </footer>
    </div>
  );
}
