"use client";

import React, { useEffect, useState } from "react";

interface ToastProps {
  message: string;
  type: "success" | "error";
  onClose: () => void;
}

export default function Toast({ message, type, onClose }: ToastProps) {
  const [isHovered, setIsHovered] = useState(false);

  useEffect(() => {
    const timer = setTimeout(onClose, 4000);
    return () => clearTimeout(timer);
  }, [onClose]);

  const isSuccess = type === "success";

  // Self-contained Vanilla styles
  const containerStyle: React.CSSProperties = {
    position: "fixed",
    bottom: "24px",
    right: "24px",
    zIndex: 9999,
    display: "flex",
    alignItems: "center",
    gap: "12px",
    borderRadius: "10px",
    border: "1px solid",
    padding: "12px 18px",
    boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5)",
    backdropFilter: "blur(12px)",
    WebkitBackdropFilter: "blur(12px)",
    animation: "toastSlideIn 0.25s cubic-bezier(0.16, 1, 0.3, 1)",
    fontFamily: "var(--font-sans), sans-serif",
    backgroundColor: isSuccess ? "rgba(6, 70, 53, 0.95)" : "rgba(136, 19, 55, 0.95)",
    borderColor: isSuccess ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.3)",
    color: isSuccess ? "#d1fae5" : "#ffe4e6",
  };

  const svgStyle: React.CSSProperties = {
    width: "20px",
    height: "20px",
    minWidth: "20px",
    flexShrink: 0,
    color: isSuccess ? "#34d399" : "#fb7185",
  };

  const closeBtnStyle: React.CSSProperties = {
    background: "none",
    border: "none",
    padding: 0,
    marginLeft: "8px",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    opacity: isHovered ? 1 : 0.6,
    color: isSuccess ? "#a7f3d0" : "#fecdd3",
    transition: "opacity 0.2s ease",
  };

  const icon = isSuccess ? (
    <svg style={svgStyle} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
    </svg>
  ) : (
    <svg style={svgStyle} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
    </svg>
  );

  return (
    <div style={containerStyle}>
      {icon}
      <span style={{ fontSize: "0.9rem", fontWeight: 500, letterSpacing: "-0.01em" }}>
        {message}
      </span>
      <button 
        onClick={onClose} 
        style={closeBtnStyle}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        <svg style={{ width: "16px", height: "16px" }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>

      <style jsx global>{`
        @keyframes toastSlideIn {
          from {
            transform: translateY(1.5rem) scale(0.95);
            opacity: 0;
          }
          to {
            transform: translateY(0) scale(1);
            opacity: 1;
          }
        }
      `}</style>
    </div>
  );
}
