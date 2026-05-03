import "./globals.css";
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Sidebar } from "@/components/sidebar";
import { ChatWidget } from "@/components/chat-widget";

export const metadata: Metadata = {
  title: "SRE Agent",
  description: "Production reliability intelligence",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="h-screen overflow-hidden">
        <div className="flex h-screen">
          <Sidebar />
          <main className="scrollbar-thin relative flex flex-1 flex-col overflow-auto">
            {children}
          </main>
          <ChatWidget />
        </div>
      </body>
    </html>
  );
}
