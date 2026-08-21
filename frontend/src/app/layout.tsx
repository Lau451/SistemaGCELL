import type { Metadata, Viewport } from "next";
import { Geist_Mono, Nunito_Sans, Rubik } from "next/font/google";
import "./globals.css";

const rubik = Rubik({
  variable: "--font-rubik",
  subsets: ["latin"],
});

const nunitoSans = Nunito_Sans({
  variable: "--font-nunito-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "GCELL — Fundas y accesorios para celular",
  description:
    "Catálogo de fundas y accesorios para celular. Mirá modelos, colores y precios.",
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = {
  themeColor: "#FBF2EC",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${rubik.variable} ${nunitoSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
