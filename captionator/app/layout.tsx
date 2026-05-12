import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Captionator — Video Caption Editor",
  description: "Upload a video, draft accessible captions, preview them, and export VTT or SRT files from your browser.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
