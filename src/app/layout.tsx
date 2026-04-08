import type { Metadata } from "next"
import { Inter } from "next/font/google"
import "./globals.css"

const inter = Inter({ subsets: ["latin"] })

export const metadata: Metadata = {
  title: "BCE Lab — Blockchain Economics Research",
  description: "Institutional-grade blockchain economic research powered by AI agents",
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || "https://bcelab.xyz"),
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
    <html lang="en" className={inter.className}>
      <body className="bg-gray-950 text-gray-100 min-h-screen">{children}</body>
    </html>
  )
}
