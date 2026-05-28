"use client";

import React from "react";
import { usePathname } from "next/navigation";

export default function SidebarNav() {
  const pathname = usePathname();

  const menuItems = [
    { href: "/dashboard", label: "Dashboard", icon: "📊" },
    { href: "/dashboard/new", label: "New API Wizard", icon: "✨" },
    { href: "/dashboard/keys", label: "API Keys", icon: "🔑" },
    { href: "/dashboard/billing", label: "Usage & Billing", icon: "💳" },
  ];

  return (
    <ul className="menu-list">
      {menuItems.map((item) => {
        const isActive = pathname === item.href;
        return (
          <li key={item.href}>
            <a href={item.href} className={`menu-item ${isActive ? "active" : ""}`}>
              <span>{item.icon}</span> {item.label}
            </a>
          </li>
        );
      })}
    </ul>
  );
}
