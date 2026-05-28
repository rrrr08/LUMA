"use client";

import React, { useState, useMemo, useEffect } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "../../../lib/api-client";

interface FieldDefinition {
  name: string;
  type: string;
  description: string;
  sample_value: string;
  selector_hint: string;
  confidence: number;
}

export default function NewApiWizard() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [url, setUrl] = useState("");
  const [urlTemplate, setUrlTemplate] = useState("");
  const [proxyEnabled, setProxyEnabled] = useState(false);
  const [proxyCountry, setProxyCountry] = useState("US");
  const [apiName, setApiName] = useState("");

  // Loading sub-status messages for crawl animations
  const [loadingMsg, setLoadingMsg] = useState("");

  // Scraped page meta
  const [crawlData, setCrawlData] = useState<any>(null);

  // AI analysis schema proposal
  const [proposedSchema, setProposedSchema] = useState<any>(null);

  // Active fields edited by the user
  const [schemaFields, setSchemaFields] = useState<FieldDefinition[]>([]);

  // Endpoint suffix
  const [endpointPath, setEndpointPath] = useState("");

  const [deploymentResult, setDeploymentResult] = useState<any>(null);
  const [errorMsg, setErrorMsg] = useState("");

  // Point-and-Click Selector Map states
  const [targetingFieldIndex, setTargetingFieldIndex] = useState<number | null>(null);
  const [hoveredElementIdx, setHoveredElementIdx] = useState<number | null>(null);
  const [scale, setScale] = useState({ x: 1, y: 1 });
  const [naturalSize, setNaturalSize] = useState({ width: 1280, height: 800 });

  // Flattens the DOM tree to extract list of interactive elements
  const flattenDom = (node: any, parentSelector = "", list: any[] = []): any[] => {
    if (!node || node.type !== "element" || !node.rect) return list;
    
    let currentSelector = node.tag;
    if (node.id) {
      currentSelector = `#${node.id}`;
    } else if (node.classes && node.classes.length > 0) {
      // Clean up utility or complex CSS classes
      const cleanClasses = node.classes
        .filter((c: string) => c && !c.includes(":") && !c.includes("[") && !c.includes("]") && !c.includes("/"))
        .slice(0, 2);
      if (cleanClasses.length > 0) {
        currentSelector = `${node.tag}.${cleanClasses.join(".")}`;
      }
    }
    
    const fullSelector = parentSelector ? `${parentSelector} > ${currentSelector}` : currentSelector;
    
    // Only capture items with actual visual dimensions (exclude full screen wrappers or zero size elements)
    if (node.rect.width > 2 && node.rect.height > 2 && node.rect.width < 1200 && node.rect.height < 600) {
      list.push({
        tag: node.tag,
        rect: node.rect,
        selector: fullSelector,
        text: node.text
      });
    }
    
    if (node.children) {
      for (const child of node.children) {
        flattenDom(child, fullSelector, list);
      }
    }
    return list;
  };

  const flatElements = useMemo(() => {
    return crawlData?.dom_tree ? flattenDom(crawlData.dom_tree) : [];
  }, [crawlData]);

  // Adjust coordinates scale factors on image rendering
  const handleImageLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget;
    const rect = img.getBoundingClientRect();
    setNaturalSize({ width: img.naturalWidth || 1280, height: img.naturalHeight || 800 });
    setScale({
      x: rect.width / (img.naturalWidth || 1280),
      y: rect.height / (img.naturalHeight || 800),
    });
  };

  // Recalculate scaling coordinates on window resize
  useEffect(() => {
    const handleResize = () => {
      const img = document.getElementById("scraped-screenshot-img") as HTMLImageElement;
      if (img) {
        const rect = img.getBoundingClientRect();
        setScale({
          x: rect.width / (img.naturalWidth || 1280),
          y: rect.height / (img.naturalHeight || 800),
        });
      }
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Step 1: Submit URL to Crawler Worker
  const handleStartCrawl = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url) return;

    setErrorMsg("");
    setStep(2);
    setLoadingMsg("Spinning up Playwright browser instance...");

    try {
      // Crawl target
      const crawlRes = await apiFetch("/v1/projects/crawl", {
        method: "POST",
        body: JSON.stringify({ url })
      });

      if (!crawlRes.ok) {
        const errText = await crawlRes.text();
        throw new Error(errText || "Crawling failed");
      }
      const crawlVal = await crawlRes.json();
      setCrawlData(crawlVal);

      // Prompt AI vision analysis
      setLoadingMsg("Invoking GPT-4o Vision to map structure...");
      const aiRes = await apiFetch("/v1/projects/analyze-visuals", {
        method: "POST",
        body: JSON.stringify({
          title: crawlVal.title,
          dom_tree: crawlVal.dom_tree,
          screenshot_b64: crawlVal.screenshot_preview_b64
        })
      });

      if (!aiRes.ok) {
        const errText = await aiRes.text();
        throw new Error(errText || "AI vision analysis failed");
      }
      const aiVal = await aiRes.json();
      setProposedSchema(aiVal);
      setSchemaFields(aiVal.fields || []);

      // Auto-populate default naming values
      setApiName(`${aiVal.primary_entity_name.charAt(0).toUpperCase() + aiVal.primary_entity_name.slice(1)} List API`);
      setEndpointPath(aiVal.primary_entity_name.toLowerCase().replace(/\s+/g, "-") + "-list");

      setStep(3);
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err.message || "Failed to analyze target page. Please try another URL.");
      setStep(1);
    }
  };

  // Field change updates
  const handleUpdateFieldName = (index: number, newName: string) => {
    const updated = [...schemaFields];
    updated[index].name = newName.toLowerCase().replace(/[^a-z0-9_]/g, "");
    setSchemaFields(updated);
  };

  const handleUpdateFieldType = (index: number, newType: string) => {
    const updated = [...schemaFields];
    updated[index].type = newType;
    setSchemaFields(updated);
  };

  const handleUpdateFieldSelector = (index: number, newSelector: string) => {
    const updated = [...schemaFields];
    updated[index].selector_hint = newSelector;
    setSchemaFields(updated);
  };

  const handleToggleField = (index: number) => {
    const updated = [...schemaFields];
    updated.splice(index, 1);
    setSchemaFields(updated);
  };

  const handleAddField = () => {
    const newField: FieldDefinition = {
      name: `custom_field_${schemaFields.length + 1}`,
      type: "string",
      description: "User-defined custom scraper field",
      sample_value: "N/A",
      selector_hint: ".item-element",
      confidence: 1.0
    };
    setSchemaFields([...schemaFields, newField]);
  };

  // Step 3: Confirm configuration & trigger code gen and deployment
  const handleDeploy = async () => {
    setErrorMsg("");
    setStep(4);
    setLoadingMsg("Generating custom parsing scripts...");

    try {
      // 1. Create a Project first
      const projRes = await apiFetch("/v1/projects", {
        method: "POST",
        body: JSON.stringify({ name: apiName })
      });

      if (!projRes.ok) throw new Error("Failed to create project record.");
      const project = await projRes.json();

      // 2. Format custom schema mapping for deployment
      const properties: any = {};
      schemaFields.forEach((f) => {
        properties[f.name] = {
          type: f.type,
          description: f.description,
          selector_hint: f.selector_hint
        };
      });

      const jsonSchema = {
        type: "object",
        metadata: {
          target_url: url,
          url_template: urlTemplate || null,
          proxy_enabled: proxyEnabled,
          proxy_country: proxyEnabled ? proxyCountry : null,
          page_type: proposedSchema?.page_type || "listings"
        },
        properties: {
          items: {
            type: "array",
            items: {
              type: "object",
              properties: properties
            }
          }
        }
      };

      // 3. Trigger Code Gen, Sandbox verification and live serving deploy
      setLoadingMsg("Verifying extractor code in security sandbox...");
      const deployRes = await apiFetch(`/v1/projects/${project.id}/deploy`, {
        method: "POST",
        body: JSON.stringify({
          json_schema: jsonSchema,
          endpoint_path: endpointPath
        })
      });

      if (!deployRes.ok) {
        const errDetail = await deployRes.json();
        throw new Error(errDetail.detail || "Sandbox check failed.");
      }

      const deployVal = await deployRes.json();
      setDeploymentResult(deployVal);
      setLoadingMsg("API successfully generated!");
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err.message || "Failed to generate dynamic code extraction parser.");
      setStep(3);
    }
  };

  return (
    <div style={{ maxWidth: "1200px", margin: "0 auto" }}>
      <header className="dashboard-header">
        <div>
          <h1>Create Scraper API</h1>
          <p style={{ color: "var(--text-secondary)", marginTop: "0.25rem" }}>
            Paste the URL of any public website to convert its structured layout into a dynamic REST gateway.
          </p>
        </div>
      </header>

      {/* Progress indicators */}
      <div className="wizard-steps">
        <div className={`wizard-step ${step === 1 ? "active" : ""} ${step > 1 ? "completed" : ""}`}>
          <div className="step-number">1</div>
          <span className="step-label">Specify Target</span>
        </div>
        <div className={`wizard-step ${step === 2 ? "active" : ""} ${step > 2 ? "completed" : ""}`}>
          <div className="step-number">2</div>
          <span className="step-label">Analyze Layout</span>
        </div>
        <div className={`wizard-step ${step === 3 ? "active" : ""} ${step > 3 ? "completed" : ""}`}>
          <div className="step-number">3</div>
          <span className="step-label">Design Schema</span>
        </div>
        <div className={`wizard-step ${step === 4 ? "active" : ""} ${step > 4 ? "completed" : ""}`}>
          <div className="step-number">4</div>
          <span className="step-label">Deploy Gateway</span>
        </div>
      </div>

      {errorMsg && (
        <div className="card" style={{ backgroundColor: "var(--error-glow)", borderColor: "var(--error)", color: "var(--text-primary)", marginBottom: "2rem", padding: "1rem" }}>
          <strong>⚠️ Processing Error:</strong> {errorMsg}
        </div>
      )}

      {/* Step 1: Input target page */}
      {step === 1 && (
        <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <form onSubmit={handleStartCrawl}>
            <div className="form-group">
              <label className="form-label" htmlFor="target-url">Paste Website Page Address</label>
              <input
                id="target-url"
                type="url"
                className="input-text"
                placeholder="https://example-travel-site.com/hotels/listings"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="url-template">URL Template (Optional)</label>
              <input
                id="url-template"
                type="text"
                className="input-text"
                placeholder="https://example-travel-site.com/hotels/listings?city={city}"
                value={urlTemplate}
                onChange={(e) => setUrlTemplate(e.target.value)}
              />
              <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
                Use placeholders like <code>{`{city}`}</code> to enable dynamic API Gateway parameter query compilation.
              </span>
            </div>

            <div style={{ display: "flex", gap: "2rem", flexWrap: "wrap", marginTop: "1.5rem", alignItems: "center", borderTop: "1px solid var(--border-color)", paddingTop: "1.5rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                <input
                  id="proxy-enabled"
                  type="checkbox"
                  checked={proxyEnabled}
                  onChange={(e) => setProxyEnabled(e.target.checked)}
                  style={{ width: "18px", height: "18px", accentColor: "var(--primary)" }}
                />
                <label htmlFor="proxy-enabled" style={{ fontSize: "0.95rem", fontWeight: 500, cursor: "pointer" }}>
                  Enable Proxy Rotation & Geo-Bypassing
                </label>
              </div>

              {proxyEnabled && (
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <label className="form-label" style={{ marginBottom: 0 }}>Routing Node Origin:</label>
                  <select
                    className="input-text"
                    style={{ padding: "0.4rem 0.8rem", fontSize: "0.9rem" }}
                    value={proxyCountry}
                    onChange={(e) => setProxyCountry(e.target.value)}
                  >
                    <option value="US">🇺🇸 United States</option>
                    <option value="DE">🇩🇪 Germany</option>
                    <option value="GB">🇬🇧 United Kingdom</option>
                    <option value="FR">🇫🇷 France</option>
                    <option value="JP">🇯🇵 Japan</option>
                  </select>
                </div>
              )}
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "2.5rem", borderTop: "1px solid var(--border-color)", paddingTop: "1.5rem" }}>
              <button type="submit" className="btn btn-primary">
                Crawl & Map visual structure ⚡
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Step 2: Scraping state */}
      {step === 2 && (
        <div className="card" style={{ textAlign: "center", padding: "4rem 2rem" }}>
          <div className="shimmer" style={{ width: "80px", height: "80px", borderRadius: "50%", margin: "0 auto 2rem" }} />
          <h3>AI Web Analyst at Work</h3>
          <p style={{ color: "var(--text-secondary)", marginTop: "0.5rem" }}>{loadingMsg}</p>
          <div style={{ maxWidth: "400px", margin: "2rem auto 0", height: "4px", backgroundColor: "var(--bg-tertiary)", borderRadius: "2px", overflow: "hidden" }}>
            <div className="shimmer" style={{ width: "100%", height: "100%" }} />
          </div>
        </div>
      )}

      {/* Step 3: Schema Config review */}
      {step === 3 && (
        <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "2rem", alignItems: "start" }}>
          
          {/* Point-and-Click Selector Map (Left Column) */}
          <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
              <h3 style={{ margin: 0 }}>Visual Page Selector</h3>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", minHeight: "24px" }}>
                <span style={{ fontSize: "0.85rem", fontWeight: "600", color: targetingFieldIndex !== null ? "var(--warning)" : "var(--text-secondary)" }}>
                  {targetingFieldIndex !== null 
                    ? `🎯 Targeting: Hover & click screenshot element to map CSS selector for "${schemaFields[targetingFieldIndex]?.name}"`
                    : "💡 Hover elements to see CSS selectors. Click target icon beside fields to map visually."}
                </span>
                {hoveredElementIdx !== null && flatElements[hoveredElementIdx] && (
                  <code style={{ fontSize: "0.75rem", color: "var(--primary)", backgroundColor: "var(--bg-tertiary)", padding: "0.2rem 0.5rem", borderRadius: "4px" }}>
                    {flatElements[hoveredElementIdx].selector}
                  </code>
                )}
              </div>
            </div>

            {/* Relative container wrapper */}
            <div style={{ position: "relative", width: "100%", overflow: "hidden", border: "1px solid var(--border-color)", borderRadius: "var(--radius-md)", backgroundColor: "var(--bg-primary)" }}>
              <img
                id="scraped-screenshot-img"
                src={crawlData?.screenshot_preview_b64 ? `data:image/png;base64,${crawlData.screenshot_preview_b64}` : ""}
                alt="Scraped Visual View"
                style={{ width: "100%", height: "auto", display: "block" }}
                onLoad={handleImageLoad}
              />
              
              {/* Absolutes Overlay boxes */}
              {flatElements.map((el, i) => {
                const top = el.rect.y * scale.y;
                const left = el.rect.x * scale.x;
                const width = el.rect.width * scale.x;
                const height = el.rect.height * scale.y;

                const isHovered = hoveredElementIdx === i;
                const isTargeting = targetingFieldIndex !== null;

                return (
                  <div
                    key={i}
                    style={{
                      position: "absolute",
                      top: `${top}px`,
                      left: `${left}px`,
                      width: `${width}px`,
                      height: `${height}px`,
                      border: isHovered ? "2px solid var(--primary)" : "1px solid transparent",
                      backgroundColor: isHovered ? "rgba(99, 102, 241, 0.12)" : "transparent",
                      cursor: isTargeting ? "crosshair" : "default",
                      zIndex: isHovered ? 20 : 10,
                      transition: "border 0.05s ease, background-color 0.05s ease",
                    }}
                    onMouseEnter={() => setHoveredElementIdx(i)}
                    onMouseLeave={() => setHoveredElementIdx(null)}
                    onClick={() => {
                      if (isTargeting && targetingFieldIndex !== null) {
                        handleUpdateFieldSelector(targetingFieldIndex, el.selector);
                        setTargetingFieldIndex(null);
                      }
                    }}
                  />
                );
              })}
            </div>
          </div>

          {/* Form settings & Schema List (Right Column) */}
          <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
            
            {/* Project metadata config */}
            <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
              <h3>API Gateway Settings</h3>

              <div className="form-group">
                <label className="form-label">API Project Name</label>
                <input
                  type="text"
                  className="input-text"
                  value={apiName}
                  onChange={(e) => setApiName(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Gateway Path</label>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <span style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: "0.9rem" }}>/v1/apis/</span>
                  <input
                    type="text"
                    className="input-text"
                    style={{ flex: 1, fontFamily: "var(--font-mono)" }}
                    value={endpointPath}
                    onChange={(e) => setEndpointPath(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, ""))}
                  />
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", marginTop: "1rem" }}>
                <button className="btn btn-secondary" onClick={() => setStep(1)}>
                  Back
                </button>
                <button className="btn btn-primary" onClick={handleDeploy}>
                  Deploy API Gateway 🚀
                </button>
              </div>
            </div>

            {/* Fields list */}
            <div className="card" style={{ overflowY: "auto", maxHeight: "650px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
                <h3 style={{ margin: 0 }}>Detected Data Fields</h3>
                <span className="badge badge-success">{schemaFields.length} Fields Active</span>
              </div>
              
              <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                {schemaFields.map((field, idx) => {
                  const isTargeted = targetingFieldIndex === idx;
                  return (
                    <div 
                      key={idx} 
                      style={{ 
                        padding: "1.25rem", 
                        border: isTargeted ? "2px solid var(--warning)" : "1px solid var(--border-color)", 
                        borderRadius: "var(--radius-md)", 
                        backgroundColor: "var(--bg-primary)", 
                        display: "flex", 
                        gap: "1rem", 
                        flexDirection: "column",
                        boxShadow: isTargeted ? "0 0 12px rgba(245, 158, 11, 0.15)" : "none"
                      }}
                    >
                      <div style={{ display: "flex", justifyItems: "center", justifyContent: "space-between", alignItems: "center" }}>
                        <span style={{ fontSize: "0.8rem", fontWeight: "700", color: isTargeted ? "var(--warning)" : "var(--primary)" }}>
                          FIELD #{idx + 1} {isTargeted && "(Click screenshot...)"}
                        </span>
                        <button style={{ background: "none", border: "none", color: "var(--error)", cursor: "pointer", fontSize: "0.8rem" }} onClick={() => handleToggleField(idx)}>
                          Exclude Field
                        </button>
                      </div>
                      
                      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "0.75rem" }}>
                        <div className="form-group" style={{ marginBottom: 0 }}>
                          <label style={{ fontSize: "0.75rem", color: "var(--text-secondary)", display: "block", marginBottom: "0.25rem" }}>Field Name</label>
                          <input
                            type="text"
                            className="input-text"
                            style={{ fontWeight: "600", fontSize: "0.85rem", padding: "0.4rem 0.6rem" }}
                            value={field.name}
                            onChange={(e) => handleUpdateFieldName(idx, e.target.value)}
                          />
                        </div>
                        
                        <div className="form-group" style={{ marginBottom: 0 }}>
                          <label style={{ fontSize: "0.75rem", color: "var(--text-secondary)", display: "block", marginBottom: "0.25rem" }}>Type</label>
                          <select
                            className="input-text"
                            style={{ fontSize: "0.85rem", padding: "0.4rem 0.6rem", height: "auto", display: "block", width: "100%" }}
                            value={field.type}
                            onChange={(e) => handleUpdateFieldType(idx, e.target.value)}
                          >
                            <option value="string">string</option>
                            <option value="number">number</option>
                            <option value="boolean">boolean</option>
                          </select>
                        </div>
                      </div>

                      <div className="form-group" style={{ marginBottom: 0 }}>
                        <label style={{ fontSize: "0.75rem", color: "var(--text-secondary)", display: "block", marginBottom: "0.25rem" }}>CSS Selector Hint</label>
                        <div style={{ display: "flex", gap: "0.5rem" }}>
                          <input
                            type="text"
                            className="input-text"
                            style={{ fontSize: "0.85rem", padding: "0.4rem 0.6rem", fontFamily: "var(--font-mono)", flex: 1 }}
                            value={field.selector_hint}
                            onChange={(e) => handleUpdateFieldSelector(idx, e.target.value)}
                            placeholder=".class-name or tag"
                          />
                          <button
                            type="button"
                            className={`btn ${isTargeted ? "btn-primary" : "btn-secondary"}`}
                            style={{ padding: "0.4rem 0.8rem", fontSize: "0.85rem" }}
                            onClick={() => setTargetingFieldIndex(isTargeted ? null : idx)}
                            title="Map Selector from Screenshot"
                          >
                            🎯
                          </button>
                        </div>
                      </div>

                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "var(--text-secondary)", borderTop: "1px dashed var(--border-color)", paddingTop: "0.5rem" }}>
                        <span>Sample Value: <code style={{ color: "var(--secondary)" }}>{field.sample_value}</code></span>
                        {field.confidence < 1.0 && (
                          <span style={{ color: "var(--success)" }}>{Math.round(field.confidence * 100)}% Confidence Match</span>
                        )}
                      </div>
                    </div>
                  );
                })}
                
                <button 
                  type="button"
                  className="btn btn-secondary" 
                  style={{ width: "100%", padding: "0.75rem", borderStyle: "dashed", display: "flex", justifyContent: "center", alignItems: "center", gap: "0.5rem" }}
                  onClick={handleAddField}
                >
                  <span>+</span> Add Custom Scraper Field
                </button>
              </div>
            </div>

          </div>

        </div>
      )}

      {/* Step 4: Finished deploy */}
      {step === 4 && (
        <div className="card" style={{ padding: "3rem 2rem", textAlign: "center" }}>
          <span style={{ fontSize: "4rem" }}>🎉</span>
          <h2 style={{ marginTop: "1rem" }}>Endpoint Deployed Live!</h2>
          <p style={{ color: "var(--text-secondary)", margin: "0.5rem 0 2.5rem" }}>
            The API endpoint and dynamic scraping parser are active and running.
          </p>

          <div style={{ textAlign: "left", backgroundColor: "var(--bg-tertiary)", borderRadius: "var(--radius-md)", padding: "1.5rem", border: "1px solid var(--border-color)", marginBottom: "2.5rem" }}>
            <h4 style={{ marginBottom: "1rem" }}>API Metadata Details</h4>
            <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "0.75rem", fontSize: "0.95rem", padding: 0 }}>
              <li>
                <span style={{ color: "var(--text-secondary)" }}>Gateway URL:</span>{" "}
                <code style={{ color: "var(--info)", fontFamily: "var(--font-mono)" }}>
                  {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/v1/apis{deploymentResult?.path}
                </code>
              </li>
              <li>
                <span style={{ color: "var(--text-secondary)" }}>Method:</span>{" "}
                <span className="badge badge-success">GET</span>
              </li>
              <li>
                <span style={{ color: "var(--text-secondary)" }}>Authorization Header:</span>{" "}
                <code style={{ color: "var(--secondary)" }}>X-API-KEY: [Your API Key]</code>
              </li>
            </ul>
          </div>

          <div style={{ display: "flex", gap: "1rem", justifyContent: "center" }}>
            <button className="btn btn-secondary" onClick={() => router.push("/dashboard")}>
              Go to Dashboard
            </button>
            <button className="btn btn-primary" onClick={() => router.push("/dashboard/keys")}>
              Generate API Key
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
