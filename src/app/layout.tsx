import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "BCE Lab — Blockchain Economics Research",
  description: "Institutional-grade blockchain economic research powered by AI agents",
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || "https://bcelab.xyz"),
  icons: {
    icon: [
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: "/apple-touch-icon.png",
  },
  openGraph: {
    title: "BCE Lab — Blockchain Economics Research",
    description: "Institutional-grade blockchain economic research powered by AI agents",
    url: "https://bcelab.xyz",
    siteName: "BCE Lab",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "BCE Lab — Blockchain Economics Research",
    description: "Institutional-grade blockchain economic research powered by AI agents",
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="bg-gray-950 text-gray-100 min-h-screen font-sans">{children}</body>
    </html>
  )
}
