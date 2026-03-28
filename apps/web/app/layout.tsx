import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "inVision U — приёмная кампания",
  description: "Портал абитуриента",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>
        <div className="container" style={{ padding: "28px 0 48px" }}>
          {children}
        </div>
      </body>
    </html>
  );
}
