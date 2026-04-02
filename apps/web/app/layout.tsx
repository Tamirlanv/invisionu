import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin", "cyrillic"],
  display: "swap",
  variable: "--font-inter",
});

const SITE_NAME = "inVision U";
const SITE_DESCRIPTION =
  "Портал приёмной кампании inVision U — подача заявки, загрузка документов и отслеживание статуса поступления.";

function siteUrl(): URL {
  const raw =
    process.env.NEXT_PUBLIC_SITE_URL ??
    process.env.APP_PUBLIC_URL ??
    (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : undefined) ??
    "http://localhost:3000";
  return new URL(raw);
}

export const viewport: Viewport = {
  themeColor: "#8BC525",
  width: "device-width",
  initialScale: 1,
};

export const metadata: Metadata = {
  metadataBase: siteUrl(),

  title: {
    default: `${SITE_NAME} — приёмная кампания`,
    template: `%s | ${SITE_NAME}`,
  },
  description: SITE_DESCRIPTION,
  applicationName: SITE_NAME,
  keywords: [
    "inVision U",
    "приёмная кампания",
    "поступление",
    "абитуриент",
    "заявка",
    "университет",
    "admissions",
  ],
  category: "education",

  icons: {
    icon: [{ url: "/assets/icons/logo.png", type: "image/png" }],
    shortcut: ["/assets/icons/logo.png"],
    apple: [{ url: "/assets/icons/logo.png" }],
  },

  manifest: "/manifest.webmanifest",

  openGraph: {
    type: "website",
    siteName: SITE_NAME,
    locale: "ru_KZ",
    title: `${SITE_NAME} — приёмная кампания`,
    description: SITE_DESCRIPTION,
    url: "/",
    images: [{ url: "/assets/icons/logo.png", width: 512, height: 512, alt: SITE_NAME }],
  },

  twitter: {
    card: "summary",
    title: `${SITE_NAME} — приёмная кампания`,
    description: SITE_DESCRIPTION,
    images: ["/assets/icons/logo.png"],
  },

  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-snippet": -1,
      "max-image-preview": "large",
      "max-video-preview": -1,
    },
  },

  alternates: {
    canonical: "/",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" className={inter.variable}>
      <body className={inter.className} style={{ margin: 0 }}>
        {children}
      </body>
    </html>
  );
}
