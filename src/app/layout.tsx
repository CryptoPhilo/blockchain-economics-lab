import type { Metadata } from "next"
import { Inter } from "next/font/google"
import { buildLocalizedSiteMetadata } from "@/lib/site-metadata"
import "./globals.css"

const inter = Inter({ subsets: ["latin"] })

export const metadata: Metadata = {
  ...buildLocalizedSiteMetadata("en"),
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || "https://bcelab.xyz"),
  icons: {
    icon: [
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: "/apple-touch-icon.png",
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={inter.className}>
      <body className="bg-gray-950 text-gray-100 min-h-screen">{children}</body>
    </html>
  )
}
