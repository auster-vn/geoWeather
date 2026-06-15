import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GeoWeather Intelligence Platform - Real-time Weather GIS",
  description: "End-to-End Real-Time GIS & Weather Analytics Platform using Flink, Kafka, PostGIS, Deck.gl, and Next.js.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-theme="light" suppressHydrationWarning>
      <head>
        <link rel="icon" href="/favicon.ico" />
        {/* Restore theme before paint to avoid flash */}
        <script dangerouslySetInnerHTML={{ __html: `
          (function(){
            var t = localStorage.getItem('geoweather-theme');
            document.documentElement.setAttribute('data-theme', t === 'dark' ? 'dark' : 'light');
          })()
        `}} />
      </head>
      <body>
        {children}
      </body>
    </html>
  );
}
