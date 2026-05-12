import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Captionator — AI Video Caption Editor",
  description: "Upload a video, transcribe it with Venice Whisper, style burned-in captions, and download a captioned WebM from your browser.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
