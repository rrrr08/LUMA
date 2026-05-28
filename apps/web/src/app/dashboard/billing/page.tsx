"use client";

import React, { useState, useEffect } from "react";
import { apiFetch } from "../../../lib/api-client";
import { useAuth } from "../../../context/AuthContext";
import Toast from "../../../components/Toast";

interface Stats {
  total_requests: number;
  requests_this_month: number;
  cache_hit_rate: number;
  avg_response_ms: number;
  crawl_success_rate: number;
  active_endpoints: number;
}

interface EndpointStat {
  endpoint_id: string;
  path: string;
  request_count: number;
  last_hit: string | null;
}

interface Invoice {
  id: string;
  invoice_number: string;
  plan: string;
  amount: number;
  status: string;
  billing_date: string;
}

interface QuotaSettings {
  email_alerts_enabled: boolean;
  slack_alerts_enabled: boolean;
  slack_webhook_url: string | null;
  threshold_percentage: number;
}

const PLAN_LIMITS = {
  free: { apis: 3, requests: 100, crawls: 20, price: 0 },
  pro: { apis: 25, requests: 50000, crawls: 1000, price: 29 },
  startup: { apis: 100, requests: 500000, crawls: 10000, price: 99 }
};

export default function BillingPage() {
  const { user, refreshUser } = useAuth();
  
  // States
  const [stats, setStats] = useState<Stats>({
    total_requests: 0,
    requests_this_month: 0,
    cache_hit_rate: 0,
    avg_response_ms: 0,
    crawl_success_rate: 1.0,
    active_endpoints: 0
  });
  
  const [endpointsStats, setEndpointsStats] = useState<EndpointStat[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [quotaSettings, setQuotaSettings] = useState<QuotaSettings>({
    email_alerts_enabled: true,
    slack_alerts_enabled: false,
    slack_webhook_url: "",
    threshold_percentage: 80
  });

  const [loading, setLoading] = useState(true);
  const [updatingPlan, setUpdatingPlan] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

  // Upgrade Modal/Promo Code States
  const [selectedUpgradePlan, setSelectedUpgradePlan] = useState<"free" | "pro" | "startup" | null>(null);
  const [promoCode, setPromoCode] = useState("");
  const [promoDiscount, setPromoDiscount] = useState<number>(0);

  // Calculator Slider State
  const [calculatorRequests, setCalculatorRequests] = useState<number>(20000);

  const activePlan = (user?.plan || "free") as "free" | "pro" | "startup";
  const currentLimits = PLAN_LIMITS[activePlan] || PLAN_LIMITS.free;
  const totalCrawls = Math.round(stats.total_requests * (1 - stats.cache_hit_rate));

  const loadAllData = async () => {
    try {
      setLoading(true);
      // Fetch summary stats
      const statsRes = await apiFetch("/v1/analytics/summary");
      if (statsRes.ok) {
        setStats(await statsRes.json());
      }
      
      // Fetch per-endpoint stats
      const perEndpointRes = await apiFetch("/v1/analytics/per-endpoint");
      if (perEndpointRes.ok) {
        setEndpointsStats(await perEndpointRes.json());
      }

      // Fetch invoices
      const invoicesRes = await apiFetch("/v1/auth/invoices");
      if (invoicesRes.ok) {
        setInvoices(await invoicesRes.json());
      }

      // Fetch notification quota settings
      const settingsRes = await apiFetch("/v1/auth/quota-settings");
      if (settingsRes.ok) {
        const data = await settingsRes.json();
        setQuotaSettings({
          email_alerts_enabled: data.email_alerts_enabled,
          slack_alerts_enabled: data.slack_alerts_enabled,
          slack_webhook_url: data.slack_webhook_url || "",
          threshold_percentage: data.threshold_percentage
        });
      }

      await refreshUser();
    } catch (err) {
      console.error("Failed to load metrics, invoices, or settings:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAllData();
  }, []);

  // Handle plan update/upgrade
  const handleConfirmUpgrade = async () => {
    if (!selectedUpgradePlan || updatingPlan) return;
    setUpdatingPlan(true);
    try {
      const res = await apiFetch("/v1/auth/plan", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          plan: selectedUpgradePlan,
          promo_code: promoCode 
        })
      });
      if (res.ok) {
        await refreshUser();
        // Reload invoices and profile
        const invoicesRes = await apiFetch("/v1/auth/invoices");
        if (invoicesRes.ok) {
          setInvoices(await invoicesRes.json());
        }
        setToast({ 
          message: `Successfully updated subscription plan to ${selectedUpgradePlan.toUpperCase()}!`, 
          type: "success" 
        });
        setSelectedUpgradePlan(null);
        setPromoCode("");
        setPromoDiscount(0);
      } else {
        const err = await res.json();
        setToast({ message: err.detail || "Failed to update plan.", type: "error" });
      }
    } catch (err) {
      setToast({ message: "Network error occurred.", type: "error" });
    } finally {
      setUpdatingPlan(false);
    }
  };

  // Handle quota alert settings save
  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingSettings(true);
    try {
      const res = await apiFetch("/v1/auth/quota-settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(quotaSettings)
      });
      if (res.ok) {
        setToast({ message: "Quota threshold notification settings updated!", type: "success" });
      } else {
        setToast({ message: "Failed to save threshold preferences.", type: "error" });
      }
    } catch (err) {
      setToast({ message: "Network error occurred.", type: "error" });
    } finally {
      setSavingSettings(false);
    }
  };

  // Handle mock receipt PDF download
  const handleDownloadInvoice = (inv: Invoice) => {
    const content = `
========================================
             PAGETOAPI PLATFORM
             OFFICIAL RECEIPT
========================================
Invoice Ref:  ${inv.invoice_number}
Billing Date: ${new Date(inv.billing_date).toLocaleDateString()}
Status:       ${inv.status.toUpperCase()}
User Account: ${user?.email || "N/A"}

----------------------------------------
Description                     Amount
----------------------------------------
Page-to-API Scraper Sub:        $${inv.amount.toFixed(2)}
Tier: ${inv.plan.toUpperCase()} Monthly Quotas
 - Active APIs: Limit ${PLAN_LIMITS[inv.plan as "pro" | "startup"]?.apis || 0}
 - Monthly Requests: Limit ${PLAN_LIMITS[inv.plan as "pro" | "startup"]?.requests.toLocaleString() || 0}

----------------------------------------
Total Paid:                     $${inv.amount.toFixed(2)} USD
----------------------------------------

Thank you for choosing PageToAPI!
For support, contact support@pagetoapi.com
========================================
`;
    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `Receipt_${inv.invoice_number}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  // Format Helper
  const formatNumber = (num: number) => num.toLocaleString();

  // Calculator Plan Matcher
  const getRecommendedCalculatorPlan = (reqs: number) => {
    if (reqs <= PLAN_LIMITS.free.requests) return "free";
    if (reqs <= PLAN_LIMITS.pro.requests) return "pro";
    return "startup";
  };
  const recommendedCalcPlan = getRecommendedCalculatorPlan(calculatorRequests);

  // Button Hover States
  const [hoveredButton, setHoveredButton] = useState<string | null>(null);

  // Validate Promo Code locally for instant UI discount reflection
  const handleApplyPromoCodeLocal = () => {
    if (promoCode.toUpperCase() === "SAVE50") {
      setPromoDiscount(50);
      setToast({ message: "Promo code SAVE50 applied! 50% discount will be reflected.", type: "success" });
    } else {
      setPromoDiscount(0);
      setToast({ message: "Invalid promo code.", type: "error" });
    }
  };

  return (
    <div style={{ maxWidth: "1000px", margin: "0 auto", padding: "1rem" }}>
      <header style={{ marginBottom: "2.5rem" }}>
        <h1 style={{ fontSize: "2.25rem", fontWeight: 700, letterSpacing: "-0.03em", marginBottom: "0.25rem" }}>
          Usage & Billing
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "1.05rem" }}>
          Monitor your workspace consumption statistics, active API loads, and subscription levels.
        </p>
      </header>

      {/* Quotas Section */}
      <section 
        style={{ 
          backgroundColor: "#11131c", 
          border: "1px solid #222533", 
          borderRadius: "16px",
          padding: "2rem",
          marginBottom: "2.5rem",
          boxShadow: "0 10px 30px rgba(0, 0, 0, 0.25)"
        }}
      >
        <h3 style={{ fontSize: "1.25rem", fontWeight: 600, color: "#fff", marginBottom: "0.25rem" }}>
          Current Quota Usage
        </h3>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", marginBottom: "2rem" }}>
          Your billing cycle resets on the 1st of every month.
        </p>

        {loading ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "2rem" }}>
            <div className="shimmer" style={{ height: "45px", borderRadius: "8px" }} />
            <div className="shimmer" style={{ height: "45px", borderRadius: "8px" }} />
            <div className="shimmer" style={{ height: "45px", borderRadius: "8px" }} />
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "2.5rem" }}>
            {/* Generated APIs */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.95rem", marginBottom: "0.75rem", color: "var(--text-primary)" }}>
                <span style={{ color: "var(--text-secondary)" }}>Generated APIs</span>
                <span style={{ fontWeight: 600 }}>{stats.active_endpoints}/{currentLimits.apis}</span>
              </div>
              <div style={{ height: "8px", backgroundColor: "#1e2130", borderRadius: "4px", overflow: "hidden" }}>
                <div 
                  style={{ 
                    width: `${Math.min(100, (stats.active_endpoints / currentLimits.apis) * 100)}%`, 
                    height: "100%", 
                    background: "linear-gradient(90deg, #6366f1, #a855f7)", 
                    borderRadius: "4px",
                    transition: "width 0.5s ease-out"
                  }} 
                />
              </div>
            </div>

            {/* API Request Volume */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.95rem", marginBottom: "0.75rem", color: "var(--text-primary)" }}>
                <span style={{ color: "var(--text-secondary)" }}>API Request Volume</span>
                <span style={{ fontWeight: 600 }}>{stats.requests_this_month}/{formatNumber(currentLimits.requests)}</span>
              </div>
              <div style={{ height: "8px", backgroundColor: "#1e2130", borderRadius: "4px", overflow: "hidden" }}>
                <div 
                  style={{ 
                    width: `${Math.min(100, (stats.requests_this_month / currentLimits.requests) * 100)}%`, 
                    height: "100%", 
                    background: "linear-gradient(90deg, #818cf8, #4f46e5)", 
                    borderRadius: "4px",
                    transition: "width 0.5s ease-out"
                  }} 
                />
              </div>
            </div>

            {/* Playwright Crawls */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.95rem", marginBottom: "0.75rem", color: "var(--text-primary)" }}>
                <span style={{ color: "var(--text-secondary)" }}>Playwright Crawls</span>
                <span style={{ fontWeight: 600 }}>{totalCrawls}/{formatNumber(currentLimits.crawls)}</span>
              </div>
              <div style={{ height: "8px", backgroundColor: "#1e2130", borderRadius: "4px", overflow: "hidden" }}>
                <div 
                  style={{ 
                    width: `${Math.min(100, (totalCrawls / currentLimits.crawls) * 100)}%`, 
                    height: "100%", 
                    background: "linear-gradient(90deg, #10b981, #06b6d4)", 
                    borderRadius: "4px",
                    transition: "width 0.5s ease-out"
                  }} 
                />
              </div>
            </div>
          </div>
        )}
      </section>

      {/* Quotas & Load Chart Section */}
      <section style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "2rem", marginBottom: "3rem" }}>
        
        {/* API Consumption Breakdown */}
        <div style={{ backgroundColor: "#11131c", border: "1px solid #222533", borderRadius: "16px", padding: "1.5rem" }}>
          <h3 style={{ fontSize: "1.15rem", fontWeight: 600, color: "#fff", marginBottom: "1.5rem" }}>
            API Consumption Breakdown
          </h3>
          
          {loading ? (
            <div className="shimmer" style={{ height: "120px", borderRadius: "8px" }} />
          ) : endpointsStats.length === 0 ? (
            <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-muted)", fontSize: "0.9rem" }}>
              No crawler requests logged yet. Active API endpoints will appear here.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
              {endpointsStats.map((item) => {
                const percentage = stats.requests_this_month > 0 
                  ? Math.round((item.request_count / stats.requests_this_month) * 100) 
                  : 0;
                return (
                  <div key={item.endpoint_id}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", marginBottom: "0.35rem" }}>
                      <code style={{ color: "var(--info)" }}>GET {item.path}</code>
                      <span style={{ color: "var(--text-secondary)" }}>
                        <strong>{item.request_count} reqs</strong> ({percentage}%)
                      </span>
                    </div>
                    <div style={{ height: "6px", backgroundColor: "#1e2130", borderRadius: "3px", overflow: "hidden" }}>
                      <div 
                        style={{ 
                          width: `${percentage}%`, 
                          height: "100%", 
                          backgroundColor: "var(--primary)", 
                          borderRadius: "3px" 
                        }} 
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Cost & Plan Calculator */}
        <div style={{ backgroundColor: "#11131c", border: "1px solid #222533", borderRadius: "16px", padding: "1.5rem", display: "flex", flexDirection: "column" }}>
          <h3 style={{ fontSize: "1.15rem", fontWeight: 600, color: "#fff", marginBottom: "1rem" }}>
            Plan Recommender
          </h3>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginBottom: "1.5rem" }}>
            Estimate your monthly crawl requests to identify the most suitable tier.
          </p>

          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.9rem", marginBottom: "0.5rem", fontWeight: 600 }}>
            <span>Monthly Queries:</span>
            <span style={{ color: "var(--primary)", fontSize: "1.1rem" }}>{formatNumber(calculatorRequests)}</span>
          </div>

          <input 
            type="range"
            min="10"
            max="600000"
            step="1000"
            value={calculatorRequests}
            onChange={(e) => setCalculatorRequests(Number(e.target.value))}
            style={{ 
              width: "100%", 
              accentColor: "var(--primary)", 
              backgroundColor: "#1e2130", 
              height: "6px", 
              borderRadius: "3px", 
              cursor: "pointer",
              marginBottom: "1.5rem"
            }}
          />

          <div style={{ marginTop: "auto", borderTop: "1px solid #1e2130", paddingTop: "1rem" }}>
            <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Recommended Subscription:</span>
            <div style={{ display: "flex", justifyItems: "center", justifyContent: "space-between", marginTop: "0.25rem" }}>
              <strong style={{ fontSize: "1.2rem", color: "#fff", textTransform: "capitalize" }}>
                {recommendedCalcPlan} Plan
              </strong>
              <strong style={{ fontSize: "1.2rem", color: "var(--success)" }}>
                ${PLAN_LIMITS[recommendedCalcPlan].price}/mo
              </strong>
            </div>
          </div>
        </div>

      </section>

      {/* Available Plans */}
      <h3 style={{ fontSize: "1.5rem", fontWeight: 600, color: "#fff", marginBottom: "1.75rem", letterSpacing: "-0.02em" }}>
        Available Plans
      </h3>
      
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "2rem", alignItems: "stretch", marginBottom: "4rem" }}>
        
        {/* Free Plan */}
        <div 
          style={{ 
            backgroundColor: "#11131c", 
            border: activePlan === "free" ? "2px solid #3b3f54" : "1px solid #222533",
            borderRadius: "16px",
            padding: "2rem",
            display: "flex",
            flexDirection: "column",
            transition: "all 0.3s ease",
            transform: activePlan === "free" ? "scale(1.02)" : "none",
            boxShadow: activePlan === "free" ? "0 10px 30px rgba(0,0,0,0.3)" : "none"
          }}
        >
          <div style={{ marginBottom: "1.5rem" }}>
            <h4 style={{ fontSize: "1.35rem", fontWeight: 600, color: "#fff", marginBottom: "0.5rem" }}>Free</h4>
            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", minHeight: "36px" }}>
              For hackers & experimenters
            </p>
          </div>

          <div style={{ marginBottom: "2rem" }}>
            <span style={{ fontSize: "2.5rem", fontWeight: 700, color: "#fff" }}>$0</span>
            <span style={{ color: "var(--text-muted)", fontSize: "1rem" }}> / mo</span>
          </div>

          <ul style={{ listStyle: "none", padding: 0, margin: "0 0 2.5rem 0", display: "flex", flexDirection: "column", gap: "1rem", flex: 1 }}>
            <li style={{ display: "flex", alignItems: "center", gap: "0.75rem", fontSize: "0.9rem", color: "var(--text-primary)" }}>
              <span style={{ color: "#10b981", fontWeight: "bold" }}>✓</span> 3 Generated Scraper APIs
            </li>
            <li style={{ display: "flex", alignItems: "center", gap: "0.75rem", fontSize: "0.9rem", color: "var(--text-primary)" }}>
              <span style={{ color: "#10b981", fontWeight: "bold" }}>✓</span> 100 requests / month
            </li>
            <li style={{ display: "flex", alignItems: "center", gap: "0.75rem", fontSize: "0.9rem", color: "var(--text-primary)" }}>
              <span style={{ color: "#10b981", fontWeight: "bold" }}>✓</span> Manual cache refresh
            </li>
            <li style={{ display: "flex", alignItems: "center", gap: "0.75rem", fontSize: "0.9rem", color: "var(--text-muted)" }}>
              <span style={{ color: "var(--text-muted)", fontWeight: "bold" }}>✗</span> Scheduled refresh tasks
            </li>
          </ul>

          <button
            onClick={() => setSelectedUpgradePlan("free")}
            disabled={activePlan === "free" || updatingPlan}
            onMouseEnter={() => activePlan !== "free" && setHoveredButton("free")}
            onMouseLeave={() => setHoveredButton(null)}
            style={{
              width: "100%",
              padding: "0.85rem",
              borderRadius: "10px",
              border: activePlan === "free" ? "1px solid #2d3142" : "1px solid #3b3f54",
              background: activePlan === "free" ? "#1e2130" : hoveredButton === "free" ? "rgba(255, 255, 255, 0.05)" : "transparent",
              color: activePlan === "free" ? "var(--text-secondary)" : "#fff",
              fontWeight: 600,
              fontSize: "0.95rem",
              cursor: activePlan === "free" ? "not-allowed" : "pointer",
              transition: "all 0.2s"
            }}
          >
            {activePlan === "free" ? "Current Plan" : "Downgrade"}
          </button>
        </div>

        {/* Pro Plan */}
        <div 
          style={{ 
            backgroundColor: "#11131c", 
            border: activePlan === "pro" ? "2px solid #818cf8" : "2px solid #3b3f66",
            borderRadius: "16px",
            padding: "2rem",
            display: "flex",
            flexDirection: "column",
            position: "relative",
            transition: "all 0.3s ease",
            transform: activePlan === "pro" ? "scale(1.04)" : "scale(1.02)",
            boxShadow: "0 15px 35px rgba(99, 102, 241, 0.15)"
          }}
        >
          <div 
            style={{ 
              position: "absolute",
              top: -2,
              left: "10%",
              right: "10%",
              height: "4px",
              background: "linear-gradient(90deg, #6366f1, #a855f7)",
              borderRadius: "0 0 4px 4px"
            }}
          />

          <div style={{ marginBottom: "1.5rem" }}>
            <h4 style={{ fontSize: "1.35rem", fontWeight: 600, color: "#818cf8", marginBottom: "0.5rem" }}>Pro</h4>
            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", minHeight: "36px" }}>
              For building data-driven products
            </p>
          </div>

          <div style={{ marginBottom: "2rem" }}>
            <span style={{ fontSize: "2.5rem", fontWeight: 700, color: "#fff" }}>$29</span>
            <span style={{ color: "var(--text-muted)", fontSize: "1rem" }}> / mo</span>
          </div>

          <ul style={{ listStyle: "none", padding: 0, margin: "0 0 2.5rem 0", display: "flex", flexDirection: "column", gap: "1rem", flex: 1 }}>
            <li style={{ display: "flex", alignItems: "center", gap: "0.75rem", fontSize: "0.9rem", color: "var(--text-primary)" }}>
              <span style={{ color: "#10b981", fontWeight: "bold" }}>✓</span> 25 Generated Scraper APIs
            </li>
            <li style={{ display: "flex", alignItems: "center", gap: "0.75rem", fontSize: "0.9rem", color: "var(--text-primary)" }}>
              <span style={{ color: "#10b981", fontWeight: "bold" }}>✓</span> 50k requests / month
            </li>
            <li style={{ display: "flex", alignItems: "center", gap: "0.75rem", fontSize: "0.9rem", color: "var(--text-primary)" }}>
              <span style={{ color: "#10b981", fontWeight: "bold" }}>✓</span> Hourly/Daily Scheduled Crawls
            </li>
            <li style={{ display: "flex", alignItems: "center", gap: "0.75rem", fontSize: "0.9rem", color: "var(--text-primary)" }}>
              <span style={{ color: "#10b981", fontWeight: "bold" }}>✓</span> Automatic Scraper Self-Repair
            </li>
            <li style={{ display: "flex", alignItems: "center", gap: "0.75rem", fontSize: "0.9rem", color: "var(--text-primary)" }}>
              <span style={{ color: "#10b981", fontWeight: "bold" }}>✓</span> Slack / Email Error alerts
            </li>
          </ul>

          {activePlan === "pro" ? (
            <button
              disabled
              style={{
                width: "100%",
                padding: "0.85rem",
                borderRadius: "10px",
                border: "1px solid #2d3142",
                background: "#1e2130",
                color: "var(--text-secondary)",
                fontWeight: 600,
                fontSize: "0.95rem",
                cursor: "not-allowed"
              }}
            >
              Current Plan
            </button>
          ) : (
            <button
              onClick={() => setSelectedUpgradePlan("pro")}
              disabled={updatingPlan}
              onMouseEnter={() => setHoveredButton("pro")}
              onMouseLeave={() => setHoveredButton(null)}
              style={{
                width: "100%",
                padding: "0.85rem",
                borderRadius: "10px",
                border: "none",
                background: "linear-gradient(135deg, #6366f1, #a855f7)",
                color: "#fff",
                fontWeight: 700,
                fontSize: "0.95rem",
                cursor: "pointer",
                boxShadow: "0 4px 15px rgba(99, 102, 241, 0.4)",
                transform: hoveredButton === "pro" ? "translateY(-2px)" : "none",
                transition: "all 0.2s"
              }}
            >
              Upgrade Workspace
            </button>
          )}
        </div>

        {/* Startup Plan */}
        <div 
          style={{ 
            backgroundColor: "#11131c", 
            border: activePlan === "startup" ? "2px solid #a855f7" : "1px solid #222533",
            borderRadius: "16px",
            padding: "2rem",
            display: "flex",
            flexDirection: "column",
            transition: "all 0.3s ease",
            transform: activePlan === "startup" ? "scale(1.02)" : "none",
            boxShadow: activePlan === "startup" ? "0 10px 30px rgba(0,0,0,0.3)" : "none"
          }}
        >
          <div style={{ marginBottom: "1.5rem" }}>
            <h4 style={{ fontSize: "1.35rem", fontWeight: 600, color: "#c084fc", marginBottom: "0.5rem" }}>Startup</h4>
            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", minHeight: "36px" }}>
              For aggregating heavy competitor data
            </p>
          </div>

          <div style={{ marginBottom: "2rem" }}>
            <span style={{ fontSize: "2.5rem", fontWeight: 700, color: "#fff" }}>$99</span>
            <span style={{ color: "var(--text-muted)", fontSize: "1rem" }}> / mo</span>
          </div>

          <ul style={{ listStyle: "none", padding: 0, margin: "0 0 2.5rem 0", display: "flex", flexDirection: "column", gap: "1rem", flex: 1 }}>
            <li style={{ display: "flex", alignItems: "center", gap: "0.75rem", fontSize: "0.9rem", color: "var(--text-primary)" }}>
              <span style={{ color: "#10b981", fontWeight: "bold" }}>✓</span> 100 Generated Scraper APIs
            </li>
            <li style={{ display: "flex", alignItems: "center", gap: "0.75rem", fontSize: "0.9rem", color: "var(--text-primary)" }}>
              <span style={{ color: "#10b981", fontWeight: "bold" }}>✓</span> 500k requests / month
            </li>
            <li style={{ display: "flex", alignItems: "center", gap: "0.75rem", fontSize: "0.9rem", color: "var(--text-primary)" }}>
              <span style={{ color: "#10b981", fontWeight: "bold" }}>✓</span> Realtime Webhook Alerts
            </li>
            <li style={{ display: "flex", alignItems: "center", gap: "0.75rem", fontSize: "0.9rem", color: "var(--text-primary)" }}>
              <span style={{ color: "#10b981", fontWeight: "bold" }}>✓</span> Dedicated Proxy IP Rotations
            </li>
            <li style={{ display: "flex", alignItems: "center", gap: "0.75rem", fontSize: "0.9rem", color: "var(--text-primary)" }}>
              <span style={{ color: "#10b981", fontWeight: "bold" }}>✓</span> Multi-member team workspace
            </li>
          </ul>

          <button
            onClick={() => setSelectedUpgradePlan("startup")}
            disabled={activePlan === "startup" || updatingPlan}
            onMouseEnter={() => activePlan !== "startup" && setHoveredButton("startup")}
            onMouseLeave={() => setHoveredButton(null)}
            style={{
              width: "100%",
              padding: "0.85rem",
              borderRadius: "10px",
              border: activePlan === "startup" ? "1px solid #2d3142" : "1px solid #3b3f54",
              background: activePlan === "startup" ? "#1e2130" : hoveredButton === "startup" ? "rgba(255, 255, 255, 0.05)" : "transparent",
              color: activePlan === "startup" ? "var(--text-secondary)" : "#fff",
              fontWeight: 600,
              fontSize: "0.95rem",
              cursor: activePlan === "startup" ? "not-allowed" : "pointer",
              transition: "all 0.2s"
            }}
          >
            {activePlan === "startup" ? "Current Plan" : "Choose Plan"}
          </button>
        </div>

      </div>

      {/* Quota Thresholds alerts and settings */}
      <section style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "2rem", marginBottom: "3rem" }}>
        
        {/* Invoices List */}
        <div style={{ backgroundColor: "#11131c", border: "1px solid #222533", borderRadius: "16px", padding: "1.5rem" }}>
          <h3 style={{ fontSize: "1.15rem", fontWeight: 600, color: "#fff", marginBottom: "1.25rem" }}>
            Invoice History
          </h3>
          {invoices.length === 0 ? (
            <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-muted)", fontSize: "0.9rem" }}>
              No payments logged. Upgrade to Pro or Startup to generate invoices.
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #1e2130", textAlign: "left", color: "var(--text-muted)" }}>
                    <th style={{ padding: "0.5rem 0.25rem" }}>Ref #</th>
                    <th>Date</th>
                    <th>Plan</th>
                    <th>Amount</th>
                    <th style={{ textAlign: "right" }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((inv) => (
                    <tr key={inv.id} style={{ borderBottom: "1px solid #1e2130", color: "var(--text-primary)" }}>
                      <td style={{ padding: "0.75rem 0.25rem", fontFamily: "var(--font-mono)", fontSize: "0.8rem", color: "var(--info)" }}>
                        {inv.invoice_number}
                      </td>
                      <td style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                        {new Date(inv.billing_date).toLocaleDateString()}
                      </td>
                      <td style={{ textTransform: "capitalize", fontSize: "0.85rem" }}>
                        {inv.plan}
                      </td>
                      <td style={{ fontWeight: 600 }}>
                        ${inv.amount.toFixed(2)}
                      </td>
                      <td style={{ textAlign: "right" }}>
                        <button
                          onClick={() => handleDownloadInvoice(inv)}
                          style={{
                            background: "transparent",
                            border: "none",
                            color: "var(--primary)",
                            cursor: "pointer",
                            fontSize: "0.85rem",
                            fontWeight: 600,
                            padding: 0
                          }}
                        >
                          📄 Download
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Quota Thresholds Config */}
        <div style={{ backgroundColor: "#11131c", border: "1px solid #222533", borderRadius: "16px", padding: "1.5rem" }}>
          <h3 style={{ fontSize: "1.15rem", fontWeight: 600, color: "#fff", marginBottom: "1rem" }}>
            Usage Notifications
          </h3>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginBottom: "1.5rem" }}>
            Get notified automatically when your monthly request volumes cross specific limit thresholds.
          </p>

          <form onSubmit={handleSaveSettings} style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "0.75rem", cursor: "pointer", fontSize: "0.9rem" }}>
              <input 
                type="checkbox"
                checked={quotaSettings.email_alerts_enabled}
                onChange={(e) => setQuotaSettings({ ...quotaSettings, email_alerts_enabled: e.target.checked })}
                style={{ width: "16px", height: "16px", accentColor: "var(--primary)" }}
              />
              <span>Send Email Alerts</span>
            </label>

            <label style={{ display: "flex", alignItems: "center", gap: "0.75rem", cursor: "pointer", fontSize: "0.9rem" }}>
              <input 
                type="checkbox"
                checked={quotaSettings.slack_alerts_enabled}
                onChange={(e) => setQuotaSettings({ ...quotaSettings, slack_alerts_enabled: e.target.checked })}
                style={{ width: "16px", height: "16px", accentColor: "var(--primary)" }}
              />
              <span>Integrate Slack Webhook</span>
            </label>

            {quotaSettings.slack_alerts_enabled && (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Webhook URL:</span>
                <input 
                  type="url"
                  placeholder="https://hooks.slack.com/services/..."
                  value={quotaSettings.slack_webhook_url || ""}
                  onChange={(e) => setQuotaSettings({ ...quotaSettings, slack_webhook_url: e.target.value })}
                  style={{
                    backgroundColor: "#1e2130",
                    border: "1px solid #3b3f54",
                    borderRadius: "6px",
                    padding: "0.5rem",
                    color: "#fff",
                    fontSize: "0.85rem",
                    width: "100%"
                  }}
                />
              </div>
            )}

            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem" }}>
                <span>Alert Threshold:</span>
                <strong style={{ color: "var(--primary)" }}>{quotaSettings.threshold_percentage}% quota usage</strong>
              </div>
              <input 
                type="range"
                min="50"
                max="100"
                step="5"
                value={quotaSettings.threshold_percentage}
                onChange={(e) => setQuotaSettings({ ...quotaSettings, threshold_percentage: Number(e.target.value) })}
                style={{ width: "100%", accentColor: "var(--primary)" }}
              />
            </div>

            <button
              type="submit"
              disabled={savingSettings}
              style={{
                width: "100%",
                padding: "0.75rem",
                borderRadius: "8px",
                border: "none",
                background: "var(--primary)",
                color: "#fff",
                fontWeight: 600,
                fontSize: "0.9rem",
                cursor: "pointer",
                marginTop: "0.5rem",
                transition: "filter 0.2s"
              }}
              onMouseEnter={(e) => e.currentTarget.style.filter = "brightness(1.15)"}
              onMouseLeave={(e) => e.currentTarget.style.filter = "none"}
            >
              {savingSettings ? "Saving Settings..." : "Save Preferences"}
            </button>
          </form>
        </div>

      </section>

      {/* Upgrade Plan Confirmation Modal */}
      {selectedUpgradePlan && (
        <div 
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0,0,0,0.8)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            backdropFilter: "blur(4px)"
          }}
        >
          <div 
            style={{
              backgroundColor: "#11131c",
              border: "1px solid #3b3f54",
              borderRadius: "16px",
              padding: "2rem",
              maxWidth: "450px",
              width: "100%",
              boxShadow: "0 20px 40px rgba(0,0,0,0.5)"
            }}
          >
            <h3 style={{ fontSize: "1.25rem", color: "#fff", fontWeight: 600, marginBottom: "0.5rem" }}>
              Upgrade to {selectedUpgradePlan.toUpperCase()} Plan
            </h3>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", marginBottom: "1.5rem" }}>
              Unlock additional scraper APIs, higher request volumes, proxy configurations, and advanced notifications.
            </p>

            {/* Price Calculations */}
            <div style={{ backgroundColor: "#1e2130", borderRadius: "10px", padding: "1rem", marginBottom: "1.5rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.95rem", marginBottom: "0.5rem" }}>
                <span>Standard Monthly Rate:</span>
                <strong>${PLAN_LIMITS[selectedUpgradePlan].price}.00</strong>
              </div>
              {promoDiscount > 0 && (
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.95rem", color: "var(--success)", marginBottom: "0.5rem" }}>
                  <span>Promo discount ({promoDiscount}%):</span>
                  <strong>-${(PLAN_LIMITS[selectedUpgradePlan].price * promoDiscount / 100).toFixed(2)}</strong>
                </div>
              )}
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "1.05rem", fontWeight: 700, borderTop: "1px solid #3b3f54", paddingTop: "0.5rem", marginTop: "0.5rem" }}>
                <span>Final Billing Amount:</span>
                <span style={{ color: "var(--success)" }}>
                  ${(PLAN_LIMITS[selectedUpgradePlan].price * (1 - promoDiscount / 100)).toFixed(2)}
                </span>
              </div>
            </div>

            {/* Promo Code Input */}
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", marginBottom: "2rem" }}>
              <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>Discount Promo Code:</span>
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <input 
                  type="text"
                  placeholder="e.g. SAVE50"
                  value={promoCode}
                  onChange={(e) => setPromoCode(e.target.value)}
                  style={{
                    flex: 1,
                    backgroundColor: "#1e2130",
                    border: "1px solid #3b3f54",
                    borderRadius: "8px",
                    padding: "0.5rem 0.75rem",
                    color: "#fff",
                    fontSize: "0.9rem"
                  }}
                />
                <button
                  type="button"
                  onClick={handleApplyPromoCodeLocal}
                  style={{
                    padding: "0.5rem 1rem",
                    backgroundColor: "#3b3f54",
                    color: "#fff",
                    border: "none",
                    borderRadius: "8px",
                    cursor: "pointer",
                    fontSize: "0.85rem",
                    fontWeight: 600
                  }}
                >
                  Apply
                </button>
              </div>
            </div>

            {/* Modal Actions */}
            <div style={{ display: "flex", gap: "1rem" }}>
              <button
                onClick={() => {
                  setSelectedUpgradePlan(null);
                  setPromoCode("");
                  setPromoDiscount(0);
                }}
                style={{
                  flex: 1,
                  padding: "0.75rem",
                  borderRadius: "8px",
                  border: "1px solid #3b3f54",
                  background: "transparent",
                  color: "#fff",
                  fontWeight: 600,
                  cursor: "pointer"
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmUpgrade}
                disabled={updatingPlan}
                style={{
                  flex: 1,
                  padding: "0.75rem",
                  borderRadius: "8px",
                  border: "none",
                  background: "linear-gradient(135deg, #6366f1, #a855f7)",
                  color: "#fff",
                  fontWeight: 700,
                  cursor: "pointer",
                  boxShadow: "0 4px 10px rgba(99, 102, 241, 0.3)"
                }}
              >
                {updatingPlan ? "Upgrading..." : "Confirm & Subscribe"}
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
